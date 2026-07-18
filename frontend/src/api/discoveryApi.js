// -----------------------------------------------------------------------------
// frontend/src/api/discoveryApi.js
//
// Thin wrappers around the /admin/discovery/candidates endpoints
// (AI-DISC-002, AI-DISC-003). Both are admin-only — the backend enforces
// require_admin; the JWT is forwarded automatically via axiosInstance.
// scoreDiscoveryCandidates() accepts a JSON array of candidate objects so the
// DiscoveryPage can parse a CSV client-side and forward the result as JSON
// without needing a multipart upload endpoint.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function scoreDiscoveryCandidates(candidates) {
  const { data } = await axiosInstance.post('/admin/discovery/candidates', { candidates })
  return data
}

export async function updateDiscoveryCandidateStatus(id, newStatus) {
  const { data } = await axiosInstance.patch(`/admin/discovery/candidates/${id}`, {
    status: newStatus,
  })
  return data
}

export function extractErrorMessage(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((e) => e.msg).join(', ')
  return 'Something went wrong. Please try again.'
}
