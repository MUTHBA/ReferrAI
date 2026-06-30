// -----------------------------------------------------------------------------
// frontend/src/api/authApi.js
//
// Thin wrappers around the /auth/* backend endpoints, used by LoginPage,
// RegisterPage, ForgotPasswordPage, and ResetPasswordPage. extractErrorMessage()
// normalizes FastAPI's two error shapes — a plain string `detail` (e.g.
// 401/409) or a list of pydantic validation error objects (422) — into one
// displayable string. Added forgotPassword() and resetPassword() to wire up
// the previously-unwired AUTH-004 backend endpoints to the UI.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function login(email, password) {
  const { data } = await axiosInstance.post('/auth/login', { email, password })
  return data
}

export async function register(payload) {
  const { data } = await axiosInstance.post('/auth/register', payload)
  return data
}

export async function forgotPassword(email) {
  const { data } = await axiosInstance.post('/auth/forgot-password', { email })
  return data
}

export async function resetPassword(token, newPassword) {
  const { data } = await axiosInstance.post('/auth/reset-password', {
    token,
    new_password: newPassword,
  })
  return data
}

export function extractErrorMessage(error) {
  const detail = error.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail.map((entry) => entry.msg).join(', ')
  }

  return 'Something went wrong. Please try again.'
}
