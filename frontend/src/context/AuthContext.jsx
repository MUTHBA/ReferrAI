// -----------------------------------------------------------------------------
// frontend/src/context/AuthContext.jsx
//
// Holds the logged-in user's identity client-side. The JWT itself lives in
// localStorage (read by axiosInstance's request interceptor); this context
// just decodes it into a plain object (`sub`/`role`/`email`/`exp`) for
// components to read via useAuth(). initialUser() rehydrates that decoded
// user from localStorage on first render so a page refresh doesn't log
// the user out. decodeToken() treats an already-expired token as logged
// out. login() returns the resolved user so callers (LoginPage,
// RegisterPage) can redirect immediately instead of waiting on a re-render.
// -----------------------------------------------------------------------------

import { createContext, useContext, useMemo, useState } from 'react'

const AuthContext = createContext(null)

function decodeToken(token) {
  try {
    const payload = token.split('.')[1]
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))

    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      return null
    }

    return decoded
  } catch {
    return null
  }
}

function initialUser() {
  const token = localStorage.getItem('access_token')
  return token ? decodeToken(token) : null
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(initialUser)

  const value = useMemo(
    () => ({
      user,
      login(token, userData) {
        localStorage.setItem('access_token', token)
        const resolvedUser = userData ?? decodeToken(token)
        setUser(resolvedUser)
        return resolvedUser
      },
      logout() {
        localStorage.removeItem('access_token')
        setUser(null)
      },
    }),
    [user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
