// -----------------------------------------------------------------------------
// frontend/src/App.jsx
//
// Root component mounted by main.jsx. Composes the three app-wide
// providers/routers in order: AuthProvider (so useAuth() works anywhere
// below it) wrapping BrowserRouter wrapping AppRouter (the actual route
// table). Keep this file as pure composition — route definitions belong in
// routes/AppRouter.jsx, not here.
// -----------------------------------------------------------------------------

import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import AppRouter from './routes/AppRouter.jsx'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </AuthProvider>
  )
}
