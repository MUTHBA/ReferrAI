// -----------------------------------------------------------------------------
// frontend/src/api/referrals.js
//
// Thin wrappers around the partner referral endpoints. getMyLinks() and
// getMyCode() fetch the authenticated partner's existing links and codes.
// createLink() and createCode() call the POST endpoints that generate a new
// slug/QR or alphanumeric code server-side. extractErrorMessage() normalises
// FastAPI's two error shapes (plain string or pydantic validation array)
// into one displayable string — same pattern used by authApi.js.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function getMyLinks() {
  const { data } = await axiosInstance.get('/referrals/links')
  return data
}

export async function getMyCode() {
  const { data } = await axiosInstance.get('/referrals/codes')
  return data
}

export async function createLink(destinationUrl) {
  const { data } = await axiosInstance.post('/referrals/links', {
    destination_url: destinationUrl,
  })
  return data
}

export async function createCode() {
  const { data } = await axiosInstance.post('/referrals/codes')
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
