import { createRoot } from 'react-dom/client'

// Thứ tự quan trọng: Tailwind nạp trước, style của LiveKit nạp sau để thắng
// ở những chỗ hai bên cùng định nghĩa (button, input, ...).
import './styles.css'
import '@livekit/components-styles'

import App from './App'
import TranscribePage from './TranscribePage'

const container = document.getElementById('root')
if (!container) throw new Error('Không tìm thấy phần tử #root trong index.html')

// Định tuyến tối giản, không cần thư viện router: hai trang là hai nhánh.
// Vite dev server tự trả index.html cho mọi path nên /transcribe mở được.
const path = window.location.pathname.replace(/\/+$/, '')
const isTranscribe = path === '/transcribe'

createRoot(container).render(isTranscribe ? <TranscribePage /> : <App />)
