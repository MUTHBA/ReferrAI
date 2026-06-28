// -----------------------------------------------------------------------------
// frontend/src/api/axiosInstance.js
//
// Shared axios instance for every API call in the app. The request
// interceptor attaches the stored JWT as a Bearer header automatically, so
// callers never set Authorization manually. The response interceptor
// clears the token and bounces to /login on a 401 — except for the
// login/register requests themselves, whose own 401/409 responses are
// expected failures the calling form needs to display inline, not a
// reason to force-navigate away before the error renders.
// -----------------------------------------------------------------------------

import axios from 'axios'

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
})

axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthRequest = error.config?.url?.includes('/auth/login')
      || error.config?.url?.includes('/auth/register')

    if (error.response?.status === 401 && !isAuthRequest) {
      localStorage.removeItem('access_token')
      window.location.assign('/login')
    }

    return Promise.reject(error)
  },
)

export default axiosInstance
