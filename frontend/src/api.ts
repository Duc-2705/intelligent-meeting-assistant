/** Lớp gọi API backend. Frontend không bao giờ giữ LiveKit API secret. */

export interface JoinDetails {
  token: string
  url: string
  room: string
  identity: string
  display_name: string
}

export interface Participant {
  identity: string
  name: string
  joined_at: number
  is_publisher: boolean
}

// Mặc định để trống -> gọi đường dẫn tương đối, Vite dev server proxy sang backend.
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function readError(res: Response): Promise<string> {
  const body = await res.json().catch(() => null)
  if (body && typeof body.detail === 'string') return body.detail
  return `Máy chủ trả về lỗi ${res.status}.`
}

export async function requestToken(room: string, displayName: string): Promise<JoinDetails> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room, display_name: displayName }),
    })
  } catch {
    throw new Error(
      'Không gọi được backend. Kiểm tra backend đã chạy chưa (scripts/start-backend.ps1).',
    )
  }

  if (!res.ok) throw new Error(await readError(res))
  return (await res.json()) as JoinDetails
}

export async function fetchParticipants(room: string): Promise<Participant[]> {
  const res = await fetch(`${API_BASE}/api/rooms/${encodeURIComponent(room)}/participants`)
  if (!res.ok) throw new Error(await readError(res))
  return (await res.json()) as Participant[]
}

export interface TranscriptionResult {
  transcript: string
  model: string
  filename: string
  size_bytes: number
  processing_seconds: number
  custom_vocabulary: string[]
}

export async function transcribeAudio(
  file: File,
  customVocabulary: string,
): Promise<TranscriptionResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('custom_vocabulary', customVocabulary)

  let res: Response
  try {
    // Không đặt Content-Type: trình duyệt phải tự sinh boundary cho multipart.
    res = await fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: form })
  } catch {
    throw new Error(
      'Không gọi được backend. Kiểm tra backend đã chạy chưa (scripts/start-backend.ps1).',
    )
  }

  if (!res.ok) throw new Error(await readError(res))
  return (await res.json()) as TranscriptionResult
}
