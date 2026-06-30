// -----------------------------------------------------------------------------
// frontend/src/api/partnerApi.js
//
// Thin wrappers around the /partners and /tiers endpoints. listPartners(),
// getPartner(), and updatePartner() are admin-only. updateOwnProfile() is
// partner-only (/me/partner). listTiers() is admin-only and backs the tier
// selector in the partner detail form.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function listPartners() {
  const { data } = await axiosInstance.get('/partners')
  return data
}

export async function getPartner(id) {
  const { data } = await axiosInstance.get(`/partners/${id}`)
  return data
}

export async function updatePartner(id, payload) {
  const { data } = await axiosInstance.patch(`/partners/${id}`, payload)
  return data
}

export async function updateOwnProfile(payload) {
  const { data } = await axiosInstance.patch('/me/partner', payload)
  return data
}

export async function listTiers() {
  const { data } = await axiosInstance.get('/tiers')
  return data
}

export function extractErrorMessage(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((e) => e.msg).join(', ')
  return 'Something went wrong. Please try again.'
}
