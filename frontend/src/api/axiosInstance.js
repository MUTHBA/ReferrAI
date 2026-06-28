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
