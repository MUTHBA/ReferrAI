// -----------------------------------------------------------------------------
// frontend/src/routes/AdminRoute.jsx
//
// Route guard wrapped around the /admin/* route group in AppRouter. Reads
// the decoded JWT from useAuth(): no user → redirect to /login; logged in
// but role isn't "admin" → redirect to /partner instead of showing a 403
// page. Renders <Outlet/> (continuing to AdminLayout + the actual page)
// only once both checks pass. This is a client-side UX guard only — real
// enforcement happens server-side via require_admin.
// -----------------------------------------------------------------------------

import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.js'

export default function AdminRoute() {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.role !== 'admin') {
    return <Navigate to="/partner" replace />
  }

  return <Outlet />
}
