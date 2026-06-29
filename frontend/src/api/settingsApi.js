// -----------------------------------------------------------------------------
// frontend/src/api/settingsApi.js
//
// Thin wrappers around the /settings admin endpoints. extractErrorMessage()
// normalises FastAPI's two error shapes (plain string detail or pydantic
// validation array) into one displayable string — same pattern as authApi.js.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function getSettings() {
  const { data } = await axiosInstance.get('/settings')
  return data
}

export async function updateSetting(key, value) {
  const { data } = await axiosInstance.put(`/settings/${encodeURIComponent(key)}`, { value })
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
