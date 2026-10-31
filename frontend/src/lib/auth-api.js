// -----------------------------------------------------------------------------
// frontend/src/lib/auth-api.js
//
// Calls for the auth endpoints (/api/v1/auth/*). Public sign-up only creates
// partner accounts; admins are created with the backend CLI.
// -----------------------------------------------------------------------------

import { api } from './api'

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  return data // { access_token, token_type }
}

export async function registerPartner({ name, email, password }) {
  const { data } = await api.post('/auth/register', { name, email, password, role: 'partner' })
  return data
}

export async function requestPasswordReset(email) {
  const { data } = await api.post('/auth/forgot-password', { email })
  return data
}

export async function resetPassword(token, newPassword) {
  const { data } = await api.post('/auth/reset-password', { token, new_password: newPassword })
  return data
}
