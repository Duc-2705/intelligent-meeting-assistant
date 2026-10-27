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
import socket
import subprocess
import unicodedata
from datetime import timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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
