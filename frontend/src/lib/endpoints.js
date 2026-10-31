// -----------------------------------------------------------------------------
// frontend/src/lib/endpoints.js
//
// Every backend call the pages make, in one place, grouped by area. Each
// function returns the response body. Pages use these through TanStack Query
// (useQuery / useMutation); query keys live next to the calls in `keys`.
// -----------------------------------------------------------------------------

import { api } from './api'

const get = (url, params) => api.get(url, { params }).then((r) => r.data)
const post = (url, body) => api.post(url, body).then((r) => r.data)
const patch = (url, body) => api.patch(url, body).then((r) => r.data)
const put = (url, body) => api.put(url, body).then((r) => r.data)
const del = (url) => api.delete(url).then((r) => r.data)

/** Drop empty filter values so they don't end up as ?status=&search= */
function clean(params) {
  return Object.fromEntries(Object.entries(params || {}).filter(([, v]) => v !== '' && v !== null && v !== undefined))
}

// ----------------------------------------------------------------- account --
export const account = {
  me: () => get('/auth/me'),
  changePassword: (current_password, new_password) => post('/auth/change-password', { current_password, new_password }),
}

// ----------------------------------------------------------------- partner --
export const partnerApi = {
  dashboard: (days) => get('/dashboard/partner', { days }),
  profile: () => get('/me/partner'),
  updateProfile: (body) => patch('/me/partner', body),
  links: () => get('/referrals/links'),
  createLink: (destination_url) => post('/referrals/links', { destination_url }),
  codes: () => get('/referrals/codes'),
  createCode: () => post('/referrals/codes'),
  conversions: (params) => get('/referrals/conversions', clean(params)),
  commissions: (params) => get('/me/commissions', clean(params)),
  wallet: () => get('/wallet'),
  transactions: () => get('/wallet/transactions'),
  withdrawals: () => get('/me/withdrawals'),
  requestWithdrawal: (amount) => post('/withdrawals', { amount }),
  tiers: () => get('/tiers'),
}

// ------------------------------------------------------------------- admin --
export const adminApi = {
  dashboard: (days) => get('/dashboard/admin', { days }),

  partners: (params) => get('/partners', clean(params)),
  partner: (id) => get(`/partners/${id}`),
  partnerDashboard: (id, days = 30) => get(`/partners/${id}/dashboard`, { days }),
  partnerConversions: (id, params) => get(`/partners/${id}/conversions`, clean(params)),
  updatePartner: (id, body) => patch(`/partners/${id}`, body),

  withdrawals: (params) => get('/withdrawals', clean(params)),
  reviewWithdrawal: (id, status, notes) => patch(`/withdrawals/${id}`, { status, notes: notes || null }),
  markPaid: (id, notes) => api.post(`/withdrawals/${id}/paid`, { notes: notes || null }).then((r) => r.data),

  commissions: (params) => get('/commissions', clean(params)),
  reverseCommission: (id, reason) => post(`/commissions/${id}/reverse`, { reason: reason || null }),

  recordSale: (body) => post('/referrals/conversions', body),

  tiers: () => get('/tiers'),
  createTier: (body) => post('/tiers', body),
  updateTier: (id, body) => patch(`/tiers/${id}`, body),
  deleteTier: (id) => del(`/tiers/${id}`),

  settings: () => get('/settings'),
  settingsSchema: () => get('/settings/schema'),
  updateSetting: (key, value) => put(`/settings/${key}`, { value }),

  models: () => get('/admin/ai/models'),
  train: (models) => post('/admin/ai/train', { models }),
  runChurn: () => post('/admin/run-churn-scoring'),
  runRanking: () => post('/admin/run-ranking'),

  fraudFlags: (status) => get('/fraud-flags', clean({ status })),
  reviewFraudFlag: (id, status, notes) => patch(`/fraud-flags/${id}`, { status, notes: notes || null }),

  partnerScores: (score_type) => get('/ai-scores', { score_type }),
  /** Latest score row, or null when the entity has never been scored (404). */
  score: (entityId, score_type) =>
    get(`/ai-scores/${entityId}`, { score_type }).catch((e) => {
      if (e.response?.status === 404) return null
      throw e
    }),

  candidates: (status) => get('/admin/discovery/candidates', clean({ status })),
  scoreCandidates: (candidates) => post('/admin/discovery/candidates', { candidates }),
  updateCandidate: (id, status) => patch(`/admin/discovery/candidates/${id}`, { status }),

  auditLogs: (params) => get('/audit-logs', clean(params)),
  auditActions: () => get('/audit-logs/actions'),
}

/** Download one of the admin CSV reports (needs the auth header, so not a plain link). */
export async function downloadReport(name) {
  const response = await api.get(`/reports/${name}.csv`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `referrai-${name}-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Build a CSV in the browser from rows already on screen. */
export function downloadCsv(filename, rows) {
  if (!rows.length) return
  const headers = Object.keys(rows[0])
  const escape = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [headers.join(','), ...rows.map((r) => headers.map((h) => escape(r[h])).join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Public referral URL as visitors should see it (served by the same host as the app). */
export function referralUrl(slug) {
  return `${window.location.origin}/r/${slug}`
}
