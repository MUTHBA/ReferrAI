// -----------------------------------------------------------------------------
// frontend/src/main.jsx
//
// React entry point — mounts the root component tree into the #root div defined
// in index.html. StrictMode wraps the entire tree to surface deprecated API
// usage and double-invoke effects during development (does nothing in production).
// Global providers (BrowserRouter, auth context, query client, theme) will be
// added here wrapping <App /> as features are built. Vite processes this file
// as the ESM entry point declared in index.html.
// -----------------------------------------------------------------------------

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
