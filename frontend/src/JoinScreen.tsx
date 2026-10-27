import { useState, type FormEvent } from 'react'
import { requestToken, type JoinDetails } from './api'

interface Props {
  onJoin: (details: JoinDetails) => void
  onError: (message: string) => void
  error: string | null
}

export default function JoinScreen({ onJoin, onError, error }: Props) {
  const [room, setRoom] = useState(() => localStorage.getItem('ima.room') ?? 'demo-hci')
  const [displayName, setDisplayName] = useState(() => localStorage.getItem('ima.name') ?? '')
  const [busy, setBusy] = useState(false)

  // Chrome chỉ cho dùng micro/camera trên secure context (https hoặc localhost).
  // Kiểm tra trước khi join để báo rõ, thay vì để LiveKit thất bại với thông báo khó hiểu.
  const isSecure = window.isSecureContext

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    onError('')
    try {
      const details = await requestToken(room.trim(), displayName.trim())
      localStorage.setItem('ima.room', room.trim())
      localStorage.setItem('ima.name', displayName.trim())
      onJoin(details)
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Không rõ lỗi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 shadow-xl"
      >
        <h1 className="text-2xl font-semibold">Intelligent Meeting Assistant</h1>
        <p className="mt-1 text-sm text-white/60">
          Prototype tuần 1 — vào phòng và kiểm tra audio/video.
        </p>

        {!isSecure && (
          <div className="mt-4 rounded-lg border border-amber-400/50 bg-amber-500/10 px-3 py-3 text-sm text-amber-100">
            <p className="font-medium">Trình duyệt sẽ chặn micro và camera ở địa chỉ này.</p>
            <p className="mt-1 text-xs leading-relaxed text-amber-200/80">
              {location.origin} không phải secure context, nên vào phòng sẽ thất bại.
              Sửa bằng một trong hai cách:
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-amber-200/80">
              <li>
                Mở bằng <code className="rounded bg-black/30 px-1">http://localhost:5173</code>{' '}
                trên chính máy đang chạy frontend
              </li>
              <li>
                Hoặc bật{' '}
                <code className="rounded bg-black/30 px-1">
                  chrome://flags/#unsafely-treat-insecure-origin-as-secure
                </code>{' '}
                và thêm <code className="rounded bg-black/30 px-1">{location.origin}</code>
              </li>
            </ul>
          </div>
        )}

        <label className="mt-6 block text-sm font-medium" htmlFor="room">
          Tên phòng
        </label>
        <input
          id="room"
          value={room}
          onChange={(e) => setRoom(e.target.value)}
          required
          maxLength={64}
          placeholder="demo-hci"
          className="mt-1 w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 outline-none focus:border-sky-400"
        />
        <p className="mt-1 text-xs text-white/50">
          Hai máy phải nhập <strong>giống hệt nhau</strong> mới vào cùng phòng.
        </p>

        <label className="mt-4 block text-sm font-medium" htmlFor="name">
          Tên hiển thị
        </label>
        <input
          id="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
          maxLength={64}
          placeholder="Ví dụ: Minh Đức"
          className="mt-1 w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 outline-none focus:border-sky-400"
        />

        {error && (
          <div className="mt-4 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-lg bg-sky-500 px-4 py-2.5 font-medium text-white transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? 'Đang vào phòng…' : 'Vào phòng'}
        </button>

        <p className="mt-4 text-xs leading-relaxed text-white/50">
          Trình duyệt sẽ hỏi quyền dùng micro và camera. Cần bật quyền thì mới nghe/nói được.
        </p>

        <p className="mt-3 border-t border-white/10 pt-3 text-center text-xs">
          <a href="/transcribe" className="text-sky-400 hover:underline">
            Phiên âm file ghi âm có sẵn →
          </a>
        </p>
      </form>
    </div>
  )
}
