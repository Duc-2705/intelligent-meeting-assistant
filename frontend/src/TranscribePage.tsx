import { useEffect, useRef, useState, type DragEvent } from 'react'
import { transcribeAudio, type TranscriptionResult } from './api'

const MAX_MB = 200
const AUDIO_EXT = ['.wav', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.flac', '.webm', '.mp4']

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function TranscribePage() {
  const [file, setFile] = useState<File | null>(null)
  const [vocabulary, setVocabulary] = useState(
    () => localStorage.getItem('ima.vocab') ?? 'Minh, Đức, Hoàng, Trung, LiveKit, FastAPI',
  )
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [dragging, setDragging] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)

  // Đếm thời gian trong lúc chờ, để người dùng biết hệ thống còn đang chạy.
  useEffect(() => {
    if (!busy) return
    const startedAt = Date.now()
    setElapsed(0)
    const id = setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])

  function acceptFile(candidate: File) {
    const suffix = candidate.name.slice(candidate.name.lastIndexOf('.')).toLowerCase()
    setResult(null)
    setError(null)

    if (!AUDIO_EXT.includes(suffix)) {
      setFile(null)
      setError(`Định dạng "${suffix || 'không rõ'}" không hỗ trợ. Hợp lệ: ${AUDIO_EXT.join(', ')}`)
      return
    }
    if (candidate.size > MAX_MB * 1024 * 1024) {
      setFile(null)
      setError(`File ${formatBytes(candidate.size)} vượt giới hạn ${MAX_MB} MB.`)
      return
    }
    setFile(candidate)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) acceptFile(dropped)
  }

  async function handleTranscribe() {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      localStorage.setItem('ima.vocab', vocabulary)
      const output = await transcribeAudio(file, vocabulary)
      setResult(output)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không rõ lỗi.')
    } finally {
      setBusy(false)
    }
  }

  async function copyTranscript() {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result.transcript)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Trình duyệt không cho phép truy cập clipboard. Bôi đen và copy thủ công.')
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-5 px-4 py-8">
      <header>
        <a href="/" className="text-xs text-sky-400 hover:underline">
          ← Về phòng họp
        </a>
        <h1 className="mt-2 text-2xl font-semibold">Phiên âm file ghi âm</h1>
        <p className="mt-1 text-sm text-white/60">
          Tải file audio cuộc họp lên, hệ thống chuyển thành văn bản bằng Gemini.
        </p>
      </header>

      {/* Vùng chọn file */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition ${
          dragging
            ? 'border-sky-400 bg-sky-500/10'
            : 'border-white/15 bg-white/5 hover:border-white/30'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={AUDIO_EXT.join(',')}
          className="hidden"
          onChange={(e) => {
            const picked = e.target.files?.[0]
            if (picked) acceptFile(picked)
            e.target.value = ''
          }}
        />
        {file ? (
          <div>
            <div className="text-sm font-medium text-sky-300">{file.name}</div>
            <div className="mt-1 text-xs text-white/50">{formatBytes(file.size)}</div>
            <div className="mt-2 text-xs text-white/40">Bấm để chọn file khác</div>
          </div>
        ) : (
          <div>
            <div className="text-sm text-white/80">Kéo file audio vào đây, hoặc bấm để chọn</div>
            <div className="mt-1 text-xs text-white/40">
              {AUDIO_EXT.join(' · ')} — tối đa {MAX_MB} MB
            </div>
          </div>
        )}
      </div>

      {/* Từ vựng riêng */}
      <div>
        <label className="block text-sm font-medium" htmlFor="vocab">
          Từ vựng riêng <span className="font-normal text-white/40">(tuỳ chọn)</span>
        </label>
        <input
          id="vocab"
          value={vocabulary}
          onChange={(e) => setVocabulary(e.target.value)}
          placeholder="Minh, Đức, Hoàng, Trung"
          className="mt-1 w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm outline-none focus:border-sky-400"
        />
        <p className="mt-1 text-xs text-white/50">
          Tên riêng và thuật ngữ, cách nhau bằng dấu phẩy. Giúp Gemini không viết sai tên
          thành viên — đã kiểm chứng là có tác dụng rõ rệt.
        </p>
      </div>

      <button
        type="button"
        onClick={handleTranscribe}
        disabled={!file || busy}
        className="rounded-lg bg-sky-500 px-4 py-2.5 font-medium text-white transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? `Đang phiên âm… ${elapsed.toFixed(1)}s` : 'Phiên âm'}
      </button>

      {busy && (
        <p className="text-center text-xs text-white/40">
          File dài có thể mất 10–30 giây. Đừng tải lại trang.
        </p>
      )}

      {error && (
        <div className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      {result && (
        <section className="rounded-2xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium">Kết quả</h2>
              <p className="mt-0.5 text-xs text-white/40">
                {result.filename} · {formatBytes(result.size_bytes)} ·{' '}
                {result.processing_seconds.toFixed(1)}s · {result.model}
              </p>
            </div>
            <button
              type="button"
              onClick={copyTranscript}
              className="shrink-0 rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10"
            >
              {copied ? 'Đã copy' : 'Copy'}
            </button>
          </div>

          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-white/90">
            {result.transcript}
          </p>

          {result.custom_vocabulary.length > 0 && (
            <p className="mt-3 border-t border-white/10 pt-2 text-xs text-white/40">
              Từ vựng đã dùng: {result.custom_vocabulary.join(', ')}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
