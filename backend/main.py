"""Intelligent Meeting Assistant — Backend prototype (Tuần 1).

Phạm vi: chỉ đủ để hai máy vào cùng một phòng LiveKit và nói/nghe được.

Nguyên tắc bảo mật (theo mục 9 của kế hoạch):
  - API secret của LiveKit chỉ nằm ở backend, không bao giờ gửi ra frontend.
  - Frontend chỉ nhận join token đã ký, có hạn và bị giới hạn trong 1 phòng.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import unicodedata
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel, Field

load_dotenv()

# --- Cấu hình -------------------------------------------------------------


def detect_lan_ip() -> str:
    """Đoán IP LAN của máy này để máy thứ hai kết nối tới.

    Không gửi packet nào cả — chỉ hỏi OS xem route ra ngoài đi qua interface nào.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def detect_tailscale_ip() -> str | None:
    """Địa chỉ Tailscale của máy này, nếu có.

    Ưu tiên Tailscale vì nó hoạt động cả khi hai máy khác mạng và không cần
    đụng tới firewall. Phải khớp với node_ip mà scripts/start-livekit.ps1 chọn,
    nếu không browser sẽ kết nối tới một địa chỉ không có media nào cả.
    """
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    first_line = result.stdout.strip().splitlines()
    return first_line[0].strip() if first_line else None


def detect_livekit_host() -> str:
    return detect_tailscale_ip() or detect_lan_ip()


# Mặc định là khóa dev, phải khớp với livekit/livekit.yaml.example.
# Production: đặt qua biến môi trường, không để trong mã nguồn.
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "devsecretdevsecretdevsecretdevsecret")
LIVEKIT_URL = os.getenv("LIVEKIT_URL") or f"ws://{detect_livekit_host()}:7880"
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "6"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# --- Cấu hình Gemini (Tuần 2: phiên âm file audio) ------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "gemini-3.5-transcribe")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))

# Định dạng Gemini Files API chấp nhận cho audio.
_AUDIO_SUFFIXES = {
    ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac",
    ".webm", ".mp4", ".mpeg", ".mpga", ".aiff", ".aif",
}

# RoomServiceClient nói HTTP, còn browser nói WebSocket.
LIVEKIT_HTTP_URL = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")

app = FastAPI(title="Intelligent Meeting Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Model ----------------------------------------------------------------


class TokenRequest(BaseModel):
    room: str = Field(..., description="Tên phòng, ví dụ: demo-hci")
    display_name: str = Field(..., description="Tên hiển thị của người tham gia")


class TokenResponse(BaseModel):
    token: str
    url: str
    room: str
    identity: str
    display_name: str


class Participant(BaseModel):
    identity: str
    name: str
    joined_at: int
    is_publisher: bool
    # Số track đã publish. Có mặt trong phòng chưa chắc đã có tiếng/hình,
    # nên đây mới là bằng chứng media thật sự chảy.
    audio_tracks: int
    video_tracks: int


class TranscriptionResult(BaseModel):
    transcript: str
    model: str
    filename: str
    size_bytes: int
    processing_seconds: float
    custom_vocabulary: list[str]


# --- Helper ---------------------------------------------------------------

_UNSAFE = re.compile(r"[\\/\x00-\x1f]")

# "Đ"/"đ" không tách được bằng NFKD nên phải thay tay, nếu không "Đức" thành "uc".
_VIETNAMESE_D = str.maketrans({"đ": "d", "Đ": "D"})


def _clean_room(room: str) -> str:
    room = _UNSAFE.sub("", room).strip()
    if not room:
        raise HTTPException(status_code=400, detail="Tên phòng không được để trống.")
    if len(room) > 64:
        raise HTTPException(status_code=400, detail="Tên phòng tối đa 64 ký tự.")
    return room


def _clean_display_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên hiển thị không được để trống.")
    return name[:64]


def _make_identity(display_name: str) -> str:
    """Sinh identity duy nhất cho mỗi lần join.

    LiveKit sẽ ngắt kết nối người cũ nếu có người mới join trùng identity,
    nên nếu hai máy cùng nhập "Minh" mà dùng chung identity thì một máy sẽ bị đá ra.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", display_name.translate(_VIETNAMESE_D))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "guest"
    return f"{slug}-{secrets.token_hex(3)}"


# --- Endpoint -------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "livekit_url": LIVEKIT_URL}


@app.post("/api/token", response_model=TokenResponse)
async def create_token(body: TokenRequest) -> TokenResponse:
    """Cấp join token cho một người vào một phòng."""
    room = _clean_room(body.room)
    display_name = _clean_display_name(body.display_name)
    identity = _make_identity(display_name)

    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(display_name)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_ttl(timedelta(hours=TOKEN_TTL_HOURS))
        .to_jwt()
    )

    return TokenResponse(
        token=token,
        url=LIVEKIT_URL,
        room=room,
        identity=identity,
        display_name=display_name,
    )


@app.get("/api/rooms/{room}/participants", response_model=list[Participant])
async def list_participants(room: str) -> list[Participant]:
    """Ai đang trong phòng — dùng để kiểm chứng máy thứ hai đã vào thật chưa."""
    room = _clean_room(room)
    client = api.LiveKitAPI(LIVEKIT_HTTP_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        result = await client.room.list_participants(api.ListParticipantsRequest(room=room))
    except Exception as exc:  # noqa: BLE001 — prototype: trả lỗi thô cho dễ debug
        raise HTTPException(
            status_code=502,
            detail=f"Không gọi được LiveKit tại {LIVEKIT_HTTP_URL}: {exc}",
        ) from exc
    finally:
        await client.aclose()

    return [
        Participant(
            identity=p.identity,
            name=p.name,
            joined_at=p.joined_at,
            is_publisher=p.is_publisher,
            audio_tracks=sum(1 for t in p.tracks if t.type == api.TrackType.AUDIO),
            video_tracks=sum(1 for t in p.tracks if t.type == api.TrackType.VIDEO),
        )
        for p in result.participants
    ]


# --- Phiên âm file audio (Tuần 2) -----------------------------------------


def _wait_until_active(client, uploaded, timeout_seconds: float = 120.0):
    """Chờ Gemini xử lý xong file vừa upload.

    Gọi phiên âm ngay sau khi upload sẽ nhận về 0 token với file lớn, vì file
    còn ở trạng thái PROCESSING. Lỗi này rất khó đoán vì API vẫn trả status
    "completed" — chỉ có số token bằng 0 mới tố cáo.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        state = str(getattr(uploaded, "state", ""))
        if state.endswith("ACTIVE"):
            return uploaded
        if state.endswith("FAILED"):
            raise HTTPException(
                status_code=502,
                detail="Gemini không xử lý được file này (trạng thái FAILED).",
            )
        if time.monotonic() > deadline:
            raise HTTPException(
                status_code=504,
                detail="Gemini xử lý file quá lâu. Thử lại hoặc dùng file nhỏ hơn.",
            )
        time.sleep(0.5)
        uploaded = client.files.get(name=uploaded.name)


def _audio_mime_for(mime_type: str | None) -> str:
    """Ép mime của container video về dạng audio tương ứng.

    Gemini gắn mime theo nội dung, nên file .mp4 thành "video/mp4". Model phiên
    âm chỉ đọc được audio: gửi video/mp4 cho ra 1 token và transcript rỗng,
    trong khi audio/mp4 đọc đúng track tiếng (100 token với cùng file đó).
    """
    mime = mime_type or "audio/mp4"
    if mime.startswith("video/"):
        return "audio/" + mime.split("/", 1)[1]
    return mime


@app.post("/api/transcribe", response_model=TranscriptionResult)
def transcribe_audio(
    file: UploadFile = File(..., description="File audio cần phiên âm"),
    custom_vocabulary: str = Form(
        "", description="Tên riêng / thuật ngữ, cách nhau bằng dấu phẩy"
    ),
) -> TranscriptionResult:
    """Phiên âm một file audio bằng Gemini.

    Cố ý là `def` chứ không phải `async def`: SDK google-genai là đồng bộ.
    FastAPI sẽ chạy hàm này trong threadpool nên không chặn event loop —
    nếu để `async def`, cả server sẽ đứng im trong lúc chờ Gemini trả lời.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Chưa cấu hình GEMINI_API_KEY. Thêm vào backend/.env rồi khởi động lại.",
        )

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _AUDIO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng '{suffix or '(không rõ)'}' không được hỗ trợ. "
            f"Hợp lệ: {', '.join(sorted(_AUDIO_SUFFIXES))}",
        )

    vocabulary = [term.strip() for term in custom_vocabulary.split(",") if term.strip()]

    started = time.perf_counter()
    tmp_path: str | None = None
    client = None
    uploaded = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        size = os.path.getsize(tmp_path)
        if size == 0:
            raise HTTPException(status_code=400, detail="File rỗng.")
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File lớn hơn giới hạn {MAX_UPLOAD_MB} MB.",
            )

        # Import muộn: thiếu SDK thì các endpoint meeting vẫn chạy bình thường.
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        uploaded = client.files.upload(file=tmp_path)
        uploaded = _wait_until_active(client, uploaded)

        transcription_config: dict = {"language_codes": []}
        if vocabulary:
            # custom_vocabulary KHÔNG dùng chung được với diarization hay
            # timestamp — Gemini sẽ từ chối request nếu gộp cả hai.
            transcription_config["custom_vocabulary"] = vocabulary

        interaction = client.interactions.create(
            model=TRANSCRIBE_MODEL,
            input=[
                {
                    "type": "audio",
                    "uri": uploaded.uri,
                    "mime_type": _audio_mime_for(uploaded.mime_type),
                }
            ],
            generation_config={"transcription_config": transcription_config},
        )

        transcript = (interaction.output_text or "").strip()
        if not transcript:
            # Phân biệt hai nguyên nhân rất khác nhau, vì cách xử lý khác nhau.
            usage = interaction.model_dump().get("usage") or {}
            input_tokens = usage.get("total_input_tokens", 0) or 0
            if input_tokens < 10:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Gemini không đọc được âm thanh nào từ file này "
                        f"({input_tokens} token). File có thể không có track tiếng, "
                        "hoặc dùng codec không hỗ trợ. Thử chuyển sang WAV hoặc MP3."
                    ),
                )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Gemini đã đọc được {input_tokens} token âm thanh nhưng không "
                    "tìm thấy tiếng nói. Kiểm tra lại bản ghi: micro có bật không, "
                    "âm lượng có quá nhỏ không."
                ),
            )

        return TranscriptionResult(
            transcript=transcript,
            model=TRANSCRIBE_MODEL,
            filename=file.filename or f"audio{suffix}",
            size_bytes=size,
            processing_seconds=round(time.perf_counter() - started, 2),
            custom_vocabulary=vocabulary,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — prototype: trả lỗi thô cho dễ debug
        message = str(exc)
        lowered = message.lower()
        if "quota" in lowered or "rate limit" in lowered or "429" in lowered:
            raise HTTPException(
                status_code=429,
                detail="Vượt hạn mức Gemini (free tier khoảng 20 request/ngày). "
                f"Chi tiết: {message}",
            ) from exc
        raise HTTPException(status_code=502, detail=f"Gemini trả lỗi: {message}") from exc
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        if client is not None and uploaded is not None:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:  # noqa: BLE001 — file tự hết hạn sau 48h
                pass
