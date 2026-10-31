// -----------------------------------------------------------------------------
// frontend/src/lib/api.js
//
// The one HTTP client for the backend. Adds the bearer token from storage to
// every request; on a 401 from anything except the auth endpoints it clears
// the session and sends the user to /login. errorMessage() turns any FastAPI
// error (string detail or a validation list) into one readable sentence.
// -----------------------------------------------------------------------------

import axios from 'axios'

export const TOKEN_KEY = 'access_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    if (error.response?.status === 401 && !url.startsWith('/auth/')) {
      localStorage.removeItem(TOKEN_KEY)
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

const FIELD_NAMES = { new_password: 'Password', password: 'Password', email: 'Email', name: 'Name' }

export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error?.response) return 'Cannot reach the server. Check your connection and try again.'
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = d.loc?.[d.loc.length - 1]
        const msg = (d.msg || '').replace(/^Value error, /, '')
        return field && FIELD_NAMES[field] ? `${FIELD_NAMES[field]}: ${msg.toLowerCase()}` : msg
      })
      .join('. ')
  }
  return fallback
}
