import {
  ConnectionStateToast,
  ControlBar,
  GridLayout,
  ParticipantTile,
  RoomAudioRenderer,
  useConnectionState,
  useParticipants,
  useTracks,
} from '@livekit/components-react'
import { ConnectionState, Track } from 'livekit-client'

interface Props {
  room: string
  displayName: string
}

const STATE_LABEL: Record<string, string> = {
  [ConnectionState.Connecting]: 'đang kết nối…',
  [ConnectionState.Connected]: 'đã kết nối',
  [ConnectionState.Reconnecting]: 'đang kết nối lại…',
  [ConnectionState.Disconnected]: 'đã ngắt kết nối',
}

/**
 * Giao diện phòng họp.
 *
 * Cố ý ghép từ các component rời thay vì dùng prefab <VideoConference />, để
 * thanh điều khiển chỉ có mic / camera / rời phòng — đúng phạm vi MVP tuần 1.
 * (Prefab có sẵn chat và chia sẻ màn hình, là phần mở rộng.)
 *
 * <RoomAudioRenderer /> là thứ thực sự phát tiếng của người khác ra loa.
 * Thiếu nó thì vẫn thấy hình nhưng không nghe được gì.
 */
export default function RoomView({ room, displayName }: Props) {
  const participants = useParticipants()
  const connectionState = useConnectionState()

  const tracks = useTracks([{ source: Track.Source.Camera, withPlaceholder: true }], {
    onlySubscribed: false,
  })

  return (
    <div className="flex h-full flex-col bg-[#0b0d12]">
      <header className="flex items-start justify-between gap-4 border-b border-white/10 px-4 py-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">
            Phòng: <span className="text-sky-300">{room}</span>
          </div>
          <div className="truncate text-xs text-white/50">
            {displayName} · {STATE_LABEL[connectionState] ?? connectionState}
          </div>
        </div>
        <div className="shrink-0 text-right text-xs">
          <div className="text-white/70">{participants.length} người trong phòng</div>
          <div className="max-w-[22rem] truncate text-white/40">
            {participants.map((p) => p.name || p.identity).join(', ')}
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        <GridLayout tracks={tracks} className="h-full">
          <ParticipantTile />
        </GridLayout>
      </main>

      <footer className="flex justify-center border-t border-white/10 px-4 py-3">
        <ControlBar
          variation="verbose"
          controls={{
            microphone: true,
            camera: true,
            screenShare: false,
            chat: false,
            leave: true,
          }}
        />
      </footer>

      <RoomAudioRenderer />
      <ConnectionStateToast />
    </div>
  )
}
