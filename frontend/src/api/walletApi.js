// -----------------------------------------------------------------------------
// frontend/src/api/walletApi.js
//
// Thin wrappers around the /wallet and /withdrawals backend endpoints.
// getWallet() and getTransactions() are partner-only; listWithdrawals() and
// reviewWithdrawal() are admin-only. requestWithdrawal() is called from
// the partner wallet page withdrawal form.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

export async function getWallet() {
  const { data } = await axiosInstance.get('/wallet')
  return data
}

export async function getTransactions() {
  const { data } = await axiosInstance.get('/wallet/transactions')
  return data
}

export async function requestWithdrawal(amount) {
  const { data } = await axiosInstance.post('/withdrawals', { amount })
  return data
}

export async function listWithdrawals(withdrawalStatus) {
  const params = withdrawalStatus ? { status: withdrawalStatus } : {}
  const { data } = await axiosInstance.get('/withdrawals', { params })
  return data
}

export async function reviewWithdrawal(id, withdrawalStatus, notes) {
  const { data } = await axiosInstance.patch(`/withdrawals/${id}`, {
    status: withdrawalStatus,
    notes: notes ?? null,
  })
  return data
}

export function extractErrorMessage(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((e) => e.msg).join(', ')
  return 'Something went wrong. Please try again.'
}
