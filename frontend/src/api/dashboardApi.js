// -----------------------------------------------------------------------------
// frontend/src/api/dashboardApi.js
//
// API wrappers for the admin dashboard (RPT-001), partner dashboard (RPT-002),
// and CSV exports (RPT-003). getAdminDashboard() accepts an optional `days`
// param (default 30, max 90) to control the volume chart window.
// CSV helpers return raw Blob responses so the caller can trigger a browser
// download without the data passing through JSON serialisation.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function getAdminDashboard(days = 30) {
  const { data } = await axiosInstance.get('/dashboard/admin', { params: { days } })
  return data
}

export async function getPartnerDashboard() {
  const { data } = await axiosInstance.get('/dashboard/partner')
  return data
}

async function downloadCsv(path, filename) {
  const response = await axiosInstance.get(path, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function downloadReferralsCsv() {
  return downloadCsv('/reports/referrals.csv', 'referrals.csv')
}

export function downloadCommissionsCsv() {
  return downloadCsv('/reports/commissions.csv', 'commissions.csv')
}

export function downloadPartnersCsv() {
  return downloadCsv('/reports/partners.csv', 'partners.csv')
}
