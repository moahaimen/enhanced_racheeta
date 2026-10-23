import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { initI18n } from './i18n'
// Cairo (OFL), self-hosted by Vite from node_modules: variable weight axis, Arabic + Latin subsets,
// served from our own origin (no third-party font request, CSP font-src 'self').
import '@fontsource-variable/cairo/wght.css'
import './design-system/styles/index.css'

initI18n()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
