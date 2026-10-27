import { createRoot } from 'react-dom/client'

// Thứ tự quan trọng: Tailwind nạp trước, style của LiveKit nạp sau để thắng
// ở những chỗ hai bên cùng định nghĩa (button, input, ...).
import './styles.css'
import '@livekit/components-styles'

import App from './App'

const container = document.getElementById('root')
if (!container) throw new Error('Không tìm thấy phần tử #root trong index.html')

createRoot(container).render(<App />)
