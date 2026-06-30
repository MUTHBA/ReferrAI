// -----------------------------------------------------------------------------
// frontend/src/pages/admin/PayoutsPage.jsx
//
// Admin payout review page (WAL-006). Shows all withdrawals with a status
// filter (all / pending / approved / rejected). Pending rows get Approve and
// Reject action buttons; the action calls reviewWithdrawal() and refreshes
// the list on success. Approved/rejected rows are read-only.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { extractErrorMessage, listWithdrawals, reviewWithdrawal } from '../../api/walletApi.js'

const styles = {
  filters: { display: 'flex', gap: '8px', marginBottom: '20px' },
  filterBtn: (active) => ({
    padding: '6px 16px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    backgroundColor: active ? '#2563eb' : '#ffffff',
    color: active ? '#ffffff' : '#374151',
    cursor: 'pointer',
    fontWeight: 500,
  }),
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '2px solid #e5e7eb',
    color: '#374151',
    fontWeight: 600,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f3f4f6' },
  approveBtn: {
    padding: '5px 12px',
    borderRadius: '5px',
    border: 'none',
    backgroundColor: '#16a34a',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 500,
    marginRight: '6px',
  },
  rejectBtn: {
    padding: '5px 12px',
    borderRadius: '5px',
    border: 'none',
    backgroundColor: '#dc2626',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 500,
  },
  error: { color: '#b91c1c', fontSize: '14px', margin: '8px 0' },
  badge: (status) => ({
    padding: '2px 10px',
    borderRadius: '99px',
    fontSize: '12px',
    fontWeight: 600,
    backgroundColor:
      status === 'approved' ? '#dcfce7'
      : status === 'rejected' ? '#fee2e2'
      : '#fef9c3',
    color:
      status === 'approved' ? '#15803d'
      : status === 'rejected' ? '#b91c1c'
      : '#854d0e',
  }),
}

const FILTERS = ['all', 'pending', 'approved', 'rejected']

function fmt(amount) {
  return `$${Number(amount).toFixed(2)}`
}

export default function PayoutsPage() {
  const [withdrawals, setWithdrawals] = useState([])
  const [filter, setFilter] = useState('pending')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [acting, setActing] = useState(null)

  async function load(f) {
    setLoading(true)
    setError('')
    try {
      const data = await listWithdrawals(f === 'all' ? null : f)
      setWithdrawals(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(filter) }, [filter])

  async function handleReview(id, action) {
    setActing(id)
    setError('')
    try {
      await reviewWithdrawal(id, action, null)
      load(filter)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setActing(null)
    }
  }

  return (
    <section>
      <h1>Payouts</h1>

      <div style={styles.filters}>
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            style={styles.filterBtn(filter === f)}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {error && <p style={styles.error}>{error}</p>}

      {loading ? (
        <p>Loading…</p>
      ) : withdrawals.length === 0 ? (
        <p>No withdrawals found.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Requested</th>
              <th style={styles.th}>Amount</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {withdrawals.map((w) => (
              <tr key={w.id}>
                <td style={styles.td}>{new Date(w.requested_at).toLocaleDateString()}</td>
                <td style={styles.td}>{fmt(w.amount)}</td>
                <td style={styles.td}>
                  <span style={styles.badge(w.status)}>{w.status}</span>
                </td>
                <td style={styles.td}>
                  {w.status === 'pending' && (
                    <>
                      <button
                        type="button"
                        style={styles.approveBtn}
                        disabled={acting === w.id}
                        onClick={() => handleReview(w.id, 'approved')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        style={styles.rejectBtn}
                        disabled={acting === w.id}
                        onClick={() => handleReview(w.id, 'rejected')}
                      >
                        Reject
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
