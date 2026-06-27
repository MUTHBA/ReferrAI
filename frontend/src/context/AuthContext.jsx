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
        setUser(userData ?? decodeToken(token))
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
