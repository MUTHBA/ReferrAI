// -----------------------------------------------------------------------------
// frontend/src/context/AuthContext.jsx
//
// Session state. The JWT from /auth/login is kept in localStorage and decoded
// client-side for display/routing only (sub = user id, role, email, exp) —
// the backend re-checks every request. The session ends automatically when
// the token expires. homePathFor() gives each role its landing page.
// -----------------------------------------------------------------------------

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { TOKEN_KEY } from '@/lib/api'

const AuthContext = createContext(null)

function decodeToken(token) {
  try {
    const payload = token.split('.')[1]
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    if (decoded.exp && decoded.exp * 1000 <= Date.now()) return null
    return decoded
  } catch {
    return null
  }
}

function readStoredUser() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    return token ? decodeToken(token) : null
  } catch {
    return null
  }
}

export function homePathFor(user) {
  if (!user) return '/login'
  return user.role === 'admin' ? '/admin' : '/partner'
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser)

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* storage unavailable */
    }
    setUser(null)
  }, [])

  const login = useCallback((token) => {
    localStorage.setItem(TOKEN_KEY, token)
    const decoded = decodeToken(token)
    setUser(decoded)
    return decoded
  }, [])

  // End the session exactly when the token expires.
  useEffect(() => {
    if (!user?.exp) return undefined
    const ms = user.exp * 1000 - Date.now()
    if (ms <= 0) {
      logout()
      return undefined
    }
    const timer = setTimeout(logout, Math.min(ms, 2 ** 31 - 1))
    return () => clearTimeout(timer)
  }, [user, logout])

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
