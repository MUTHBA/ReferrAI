import axiosInstance from './axiosInstance.js'

export async function login(email, password) {
  const { data } = await axiosInstance.post('/auth/login', { email, password })
  return data
}

export async function register(payload) {
  const { data } = await axiosInstance.post('/auth/register', payload)
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
