import { useEffect, useRef, useState } from 'react'
import { LiveKitRoom } from '@livekit/components-react'
import JoinScreen from './JoinScreen'
import RoomView from './RoomView'
import { requestToken, type JoinDetails } from './api'

export default function App() {
  const [details, setDetails] = useState<JoinDetails | null>(null)
  const [error, setError] = useState<string | null>(null)
  const autoJoinTried = useRef(false)
  // Rời phòng (chủ động hoặc do unmount) cũng làm LiveKit phát sinh lỗi
  // "Client initiated disconnect". Đánh dấu để không báo nhầm thành sự cố.
  const leavingRef = useRef(false)

  // Vào thẳng phòng bằng query param, tiện khi demo và khi test tự động:
  //   http://localhost:5173/?room=demo-hci&name=May-1
  useEffect(() => {
    if (autoJoinTried.current) return
    autoJoinTried.current = true

    const params = new URLSearchParams(window.location.search)
    const room = params.get('room')?.trim()
    const name = params.get('name')?.trim()
    if (!room || !name) return

    requestToken(room, name)
      .then((next) => {
        localStorage.setItem('ima.room', room)
        localStorage.setItem('ima.name', name)
        setDetails(next)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Không rõ lỗi.')
      })
  }, [])

  if (!details) {
    return (
      <JoinScreen
        error={error}
        onError={setError}
        onJoin={(next) => {
          setError(null)
          leavingRef.current = false
          setDetails(next)
        }}
      />
    )
  }

  return (
    <LiveKitRoom
      token={details.token}
      serverUrl={details.url}
      connect
      audio
      video
      data-lk-theme="default"
      className="h-full"
      onDisconnected={() => {
        leavingRef.current = true
        setDetails(null)
      }}
      onError={(err) => {
        if (leavingRef.current || err.message === 'Client initiated disconnect') return

        // Thiếu secure context là nguyên nhân hay gặp nhất, và thông báo gốc
        // của LiveKit cho trường hợp này rất khó hiểu. Nói thẳng ra.
        setError(
          window.isSecureContext
            ? `Không vào được phòng: ${err.message}`
            : 'Không lấy được micro/camera vì trang này không phải secure context. ' +
                'Mở bằng http://localhost:5173 hoặc bật cờ Chrome cho địa chỉ hiện tại.',
        )
        setDetails(null)
      }}
    >
      <RoomView room={details.room} displayName={details.display_name} />
    </LiveKitRoom>
  )
}
