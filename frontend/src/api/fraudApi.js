// -----------------------------------------------------------------------------
// frontend/src/api/fraudApi.js
//
// Thin wrappers around the /fraud-flags backend endpoints (AI-FRD-005/007).
// listFraudFlags() and reviewFraudFlag() are admin-only — the backend enforces
// require_admin; the frontend simply passes the stored JWT on every request via
// the Axios interceptor in axiosInstance.js.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function listFraudFlags(flagStatus) {
  // Always pass ?status= so the route default (pending_review) never fires
  // unexpectedly. Pass "all" to disable server-side filtering.
  const params = { status: flagStatus ?? 'all' }
  const { data } = await axiosInstance.get('/fraud-flags', { params })
  return data
}

export async function reviewFraudFlag(id, action) {
  const { data } = await axiosInstance.patch(`/fraud-flags/${id}`, { status: action })
  return data
}

export function extractErrorMessage(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((e) => e.msg).join(', ')
  return 'Something went wrong. Please try again.'
}
