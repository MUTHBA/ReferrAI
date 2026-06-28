// -----------------------------------------------------------------------------
// frontend/src/routes/PartnerRoute.jsx
//
// Route guard wrapped around the /partner/* route group in AppRouter.
// Mirrors AdminRoute: no user → /login; logged in but role isn't "partner"
// → redirect to /admin instead of a 403 page. This is a client-side UX
// guard only — real enforcement happens server-side via require_partner.
// -----------------------------------------------------------------------------

import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.js'

export default function PartnerRoute() {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.role !== 'partner') {
    return <Navigate to="/admin" replace />
  }

  return <Outlet />
}
