# Intelligent Meeting Assistant — Prototype Tuần 1

Prototype tối thiểu để kiểm chứng mốc Tuần 1 của kế hoạch:

> Tạo phòng LiveKit thử nghiệm; hai máy có thể tham gia cùng phòng, nghe và nói được.

Phạm vi cố ý bó hẹp: **chỉ meeting cơ bản** (vào phòng, bật/tắt mic, bật/tắt camera, rời phòng).
Chưa có transcript, summary, task extraction, chat — đó là Tuần 2–5.

---

## 1. Kiến trúc

```
Trình duyệt (React + Vite)  ──HTTP──>  Backend (FastAPI)  ──>  sinh join token
          │
          └──WebSocket + WebRTC──>  LiveKit server  <── media audio/video
```

| Thành phần | Vai trò | Cổng |
|---|---|---|
| `livekit/livekit-server.exe` | Media server: signaling + truyền audio/video | 7880 TCP (HTTP/WS), 7881 TCP, 7882–7892 UDP |
| `backend/` | Cấp join token; giữ API secret | 8000 TCP |
| `frontend/` | Giao diện vào phòng | 5173 TCP |

**Vì sao cần backend riêng để cấp token:** API secret của LiveKit không được lộ ra
trình duyệt. Trình duyệt chỉ nhận join token đã ký, có hạn 6 giờ và bị giới hạn
trong đúng một phòng (mục 9 của kế hoạch).

---

## 2. Chuẩn bị (chỉ làm một lần)

Cần: **Node.js 20+**, **Python 3.11+**.

### 2.1. Tải LiveKit server

Binary không nằm trong repo (nặng ~55MB). Tải bản Windows amd64 mới nhất:

```powershell
$asset = (Invoke-RestMethod "https://api.github.com/repos/livekit/livekit/releases/latest").assets |
         Where-Object { $_.name -like "*windows_amd64.zip" } | Select-Object -First 1
Invoke-WebRequest $asset.browser_download_url -OutFile livekit.zip
Expand-Archive livekit.zip -DestinationPath livekit -Force
Remove-Item livekit.zip
```

Kiểm tra: `.\livekit\livekit-server.exe --version`

Nếu lệnh trên lỗi, tải tay tại <https://github.com/livekit/livekit/releases>
(bản `windows_amd64`), giải nén `livekit-server.exe` vào thư mục `livekit/`.

### 2.2. Cài dependencies

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Frontend
cd ..\frontend
npm install
```

---

## 3. Chạy

Cách nhanh nhất — mở cả ba service, mỗi cái một cửa sổ:

```powershell
.\scripts\start-all.ps1
```

Hoặc chạy riêng từng cái trong ba terminal:

```powershell
.\scripts\start-livekit.ps1     # in ra node_ip — đọc dòng này
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1
```

Mở `http://localhost:5173`, nhập **tên phòng** và **tên hiển thị**, bấm **Vào phòng**.

Vào thẳng không cần điền form:

```
http://localhost:5173/?room=demo-hci&name=May-1
```

### Địa chỉ mạng được chọn tự động

`start-livekit.ps1` chọn `node_ip` theo thứ tự: **IP Tailscale** → **IP LAN**.
Backend dò độc lập nhưng theo đúng thứ tự đó, nên hai bên luôn khớp.

`node_ip` là địa chỉ LiveKit quảng bá cho trình duyệt để truyền media. **Nếu sai,
hai máy vẫn "vào phòng" được nhưng không nghe/thấy gì** — đây là lỗi hay gặp nhất.

Ghi đè khi cần:

```powershell
.\scripts\start-livekit.ps1 -NodeIp 192.168.8.104
```

rồi đặt `LIVEKIT_URL=ws://192.168.8.104:7880` trong `backend/.env`.

---

## 4. Test hai máy

### Cách A — Tailscale (đang dùng)

Không cần đụng firewall. Cả hai máy phải đăng nhập cùng một tailnet.

**Máy 1 (máy chủ)** — chạy `.\scripts\start-all.ps1`, đọc `node_ip` in ra.

**Máy 2** — mở trình duyệt tới `http://<node_ip>:5173`.

> **Quan trọng:** `http://<ip>` **không phải** secure context, nên Chrome sẽ chặn
> micro/camera. Phải chọn một trong hai cách:

**Cách A1 — mở khoá origin cho Chrome (không cần cài gì thêm):**

1. Vào `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Bật, nhập `http://100.82.57.5:5173`, khởi động lại Chrome
3. Mở lại `http://100.82.57.5:5173`

**Cách A2 — chạy Vite riêng trên máy 2 (cần Node trên máy 2, không cần flag):**

```powershell
cd frontend
npm install
.\..\scripts\start-frontend.ps1 -ProxyTarget http://100.82.57.5:8000
```

Rồi mở `http://localhost:5173`. `localhost` là secure context nên không cần flag.

### Cách B — LAN nội bộ

```powershell
# Trên máy chủ, chạy PowerShell bằng quyền Administrator:
.\scripts\open-firewall.ps1
```

Rồi chạy với `-NodeIp <ip-lan>`, đặt `LIVEKIT_URL` tương ứng trong `backend/.env`,
và trên máy 2 vẫn phải xử lý secure context như Cách A1/A2.

### Kiểm chứng máy 2 đã vào thật

Mở trên máy 1:

```
http://localhost:8000/api/rooms/demo-hci/participants
```

Phải thấy hai phần tử, mỗi phần tử có `audio_tracks: 1` và `video_tracks: 1`.
Nếu thấy một → máy 2 chưa vào phòng.
Nếu thấy hai mà track bằng 0 → đã vào nhưng chưa publish được media.
Nếu thấy hai, track đủ, mà vẫn không nghe nhau → sai `node_ip`, hoặc micro bị mute.

### Kiểm chứng tự động, không cần hai máy

Chạy được ngay trên một máy, dùng hai Chrome headless với micro/camera giả:

```powershell
.\scripts\verify-two-clients.ps1
```

Script tự mở hai client, chờ chúng vào phòng, rồi hỏi backend xem ai đang ở trong.
In ra `PASS` khi cả hai đã publish đủ audio và video.

Cái này chứng minh toàn bộ đường đi: token → signaling → WebRTC → publish media.
Nó **không** chứng minh loa và micro thật hoạt động — việc đó vẫn cần bài test
hai máy ở trên.

---

## 5. API

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/health` | Kiểm tra backend sống, xem `livekit_url` đang dùng |
| `POST` | `/api/token` | Cấp join token. Body: `{"room": "...", "display_name": "..."}` |
| `GET` | `/api/rooms/{room}/participants` | Ai đang trong phòng — dùng để kiểm chứng |
| `POST` | `/api/transcribe` | Phiên âm file audio (multipart: `file`, `custom_vocabulary`) |

### Phiên âm file ghi âm

Mở <http://localhost:5173/transcribe>, hoặc bấm "Phiên âm file ghi âm có sẵn" ở màn hình vào phòng.

Kéo file audio vào, nhập danh sách tên riêng, bấm **Phiên âm**. Transcript hiện ra sau
khoảng 5–30 giây tuỳ độ dài file.

Cần `GEMINI_API_KEY` trong `backend/.env`, lấy miễn phí tại
<https://aistudio.google.com/apikey>.

**Vì sao có ô "Từ vựng riêng":** đây không phải tính năng phụ. Khi thử với audio
mẫu, "Minh" bị nhận thành "Manuel" và "Duc" thành "Duke". Thêm tên vào
`custom_vocabulary` thì sửa được hoàn toàn, và còn nhanh hơn. Với đồ án này,
transcript sạch tên người là điều kiện để Tuần 3 gán đúng `assignee` cho task.

**Ràng buộc cần nhớ:** `custom_vocabulary` **không dùng chung được** với
diarization (biết ai nói) hay word-level timestamps trong cùng một request — Gemini
sẽ từ chối. Phải chọn một. Hiện tại code đang chọn `custom_vocabulary`.

**File `.mp4`:** Gemini gắn mime theo nội dung nên file mp4 thành `video/mp4`, mà
model phiên âm chỉ đọc được audio — gửi nguyên `video/mp4` cho ra 1 token và
transcript rỗng. Backend tự ép sang `audio/mp4` trước khi gọi, nên cứ upload mp4
bình thường. Lần upload đầu có thể mất vài giây chờ Gemini xử lý; backend đã tự chờ.

**Giới hạn free tier:** khoảng 5 request/phút và 20 request/ngày. Audio tối đa
1 giờ mỗi request; giảm còn 30 phút nếu bật diarization hoặc timestamps.
Audio gửi ở free tier **được Google dùng để cải thiện sản phẩm** — phải nêu rõ
điều này trong form consent, và buổi demo nên dùng audio giả lập.

Xem thử nhanh tại `http://localhost:8000/docs`.

`identity` được sinh ngẫu nhiên mỗi lần join (`minh-duc-f52e0f`). **Cố ý:** LiveKit
ngắt kết nối người cũ nếu có người mới join trùng identity, nên nếu hai máy cùng
nhập "Minh Đức" mà dùng chung identity thì một máy sẽ bị đá ra.

---

## 6. Lỗi hay gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Vào phòng được, thấy tên nhau, **không nghe/thấy gì** | `node_ip` sai — LiveKit quảng bá địa chỉ máy kia không tới được | Chạy lại `start-livekit.ps1` với `-NodeIp` đúng; kiểm tra `LIVEKIT_URL` trong `backend/.env` khớp |
| Trình duyệt không hỏi quyền mic/camera | Trang không phải secure context | Dùng Cách A1 hoặc A2 ở mục 4 |
| `secret is too short` khi khởi động LiveKit | LiveKit 1.13+ yêu cầu secret ≥ 32 ký tự | Giữ nguyên secret trong `livekit.yaml.example` |
| `could not parse config: control characters` | File YAML bị ghi kèm BOM | `start-livekit.ps1` đã ghi UTF-8 không BOM; đừng sửa file bằng `Set-Content -Encoding utf8` |
| Một máy bị đá ra khi máy kia vào | Trùng `identity` | Đã xử lý ở backend; nếu tự sửa thì nhớ giữ identity duy nhất |
| Nghe thấy tiếng vọng | Hai máy chung một phòng, loa hắt vào micro | Dùng tai nghe |
| Phiên âm báo *"đọc được N token nhưng không tìm thấy tiếng nói"* | File có track âm thanh nhưng im lặng hoặc chỉ có nhạc | Kiểm tra micro lúc ghi âm. Đây là lỗi hay gặp nhất với bản ghi màn hình |
| Phiên âm báo *"không đọc được âm thanh nào"* (0 token) | File không có track tiếng, hoặc codec không hỗ trợ | Chuyển sang WAV/MP3 bằng công cụ khác rồi thử lại |
| `listen tcp 7881: bind` | Còn LiveKit cũ đang chạy | `Get-Process livekit-server \| Stop-Process -Force` |

**Lưu ý về script `.ps1`:** Windows PowerShell 5.1 đọc file `.ps1` không có BOM
theo bảng mã ANSI, nên **giữ các file trong `scripts/` chỉ chứa ký tự ASCII**.
Chèn tiếng Việt có dấu vào đó sẽ bị lỗi font khi chạy.

---

## 7. Đã kiểm chứng tới đâu

Đã chạy thật và xác nhận:

- `npm run build` và `tsc --noEmit` sạch
- `/api/health`, `/api/token`, `/api/rooms/{room}/participants` trả kết quả đúng
- Token giải mã ra đúng grants: `roomJoin`, `room=demo-hci`, `canPublish`, `canSubscribe`, hạn 6 giờ
- LiveKit, backend đều với tới được qua địa chỉ Tailscale `100.82.57.5` (cổng 7880, 7881, 8000)
- Frontend phục vụ được và proxy `/api/*` sang backend thông
- **Hai client vào cùng một phòng và mỗi client publish đủ 1 track audio + 1 track video**
  (`scripts/verify-two-clients.ps1`, dùng Chrome headless với thiết bị giả)
- **Luồng upload → phiên âm → hiển thị chạy trọn vẹn trên trình duyệt thật**
  (điều khiển Chrome qua DevTools Protocol: nạp file, bấm nút, đọc transcript từ DOM)
- `custom_vocabulary` sửa được lỗi sai tên riêng, và làm request nhanh hơn

**Chưa kiểm chứng:**

- Âm thanh và hình ảnh thật giữa hai máy có micro/loa riêng. Phần mềm đã đúng tới hết
  đường truyền media, nhưng còn phụ thuộc micro/loa và quyền trình duyệt trên từng máy.
- **Chất lượng phiên âm tiếng Việt.** Toàn bộ test dùng giọng TTS tiếng Anh có sẵn của
  Windows. Tiếng Việt phải đo riêng bằng bộ audio tham chiếu và tính WER — đây là việc
  của Tuần 2, chưa làm.

---

## 8. Bước tiếp theo

Đã xong phần khó nhất của Tuần 2: upload file và gọi STT. Còn lại:

- **Đo WER trên tiếng Việt** — chuẩn bị 3–5 audio mẫu có transcript tham chiếu
- **Lưu transcript theo `meeting_id`** — hiện kết quả chỉ trả về, chưa ghi vào database
- **Chốt `custom_vocabulary` hay diarization** — quyết định này đổi schema bảng `transcripts`
- Summary và task extraction theo JSON schema

Lưu ý từ kế hoạch: audio trong phòng họp **không tự động** thành đầu vào của AI.
Cần chọn một đường thu audio được phép (xử lý bản ghi sau cuộc họp, hoặc lấy
recording từ media server).
