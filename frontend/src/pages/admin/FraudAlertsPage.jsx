// -----------------------------------------------------------------------------
// frontend/src/pages/admin/FraudAlertsPage.jsx
//
// Admin fraud flag review queue (AI-FRD-007). Shows all fraud flags with a
// status filter (all / pending_review / confirmed / dismissed). Pending rows
// get Confirm and Dismiss action buttons; reviewed rows are read-only.
// Each row surfaces the AI explanation via ExplanationTooltip so the admin
// can see what triggered the flag (triggered_rules from FraudRuleEngine +
// contributing_factors from the Isolation Forest score).
// Follows the same pattern as PayoutsPage.jsx (inline styles, no third-party
// UI components).
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import ExplanationTooltip from '../../components/common/ExplanationTooltip.jsx'
import { extractErrorMessage, listFraudFlags, reviewFraudFlag } from '../../api/fraudApi.js'

const styles = {
  filters: { display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' },
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
  td: { padding: '10px 12px', borderBottom: '1px solid #f3f4f6', verticalAlign: 'middle' },
  confirmBtn: {
    padding: '5px 12px',
    borderRadius: '5px',
    border: 'none',
    backgroundColor: '#dc2626',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 500,
    marginRight: '6px',
  },
  dismissBtn: {
    padding: '5px 12px',
    borderRadius: '5px',
    border: 'none',
    backgroundColor: '#6b7280',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 500,
  },
  error: { color: '#b91c1c', fontSize: '14px', margin: '8px 0' },
  badge: (s) => ({
    padding: '2px 10px',
    borderRadius: '99px',
    fontSize: '12px',
    fontWeight: 600,
    backgroundColor:
      s === 'confirmed' ? '#fee2e2'
      : s === 'dismissed' ? '#f3f4f6'
      : '#fef9c3',
    color:
      s === 'confirmed' ? '#b91c1c'
      : s === 'dismissed' ? '#6b7280'
      : '#854d0e',
  }),
  score: (v) => ({
    fontWeight: 600,
    color: v >= 70 ? '#b91c1c' : v >= 40 ? '#d97706' : '#15803d',
  }),
}

const FILTERS = [
  { label: 'All', value: null },
  { label: 'Pending', value: 'pending_review' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Dismissed', value: 'dismissed' },
]

function triggeredRules(flag) {
  const rules = flag.contributing_factors?.triggered_rules
  if (!rules || rules.length === 0) return null
  return rules.map((r) => r.replace(/_/g, ' ')).join(', ')
}

export default function FraudAlertsPage() {
  const [flags, setFlags] = useState([])
  const [filter, setFilter] = useState('pending_review')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [acting, setActing] = useState(null)

  async function load(f) {
    setLoading(true)
    setError('')
    try {
      const data = await listFraudFlags(f)
      setFlags(data)
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
      await reviewFraudFlag(id, action)
      load(filter)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setActing(null)
    }
  }

  return (
    <section>
      <h1>Fraud Alerts</h1>

      <div style={styles.filters}>
        {FILTERS.map((f) => (
          <button
            key={String(f.value)}
            type="button"
            style={styles.filterBtn(filter === f.value)}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <p style={styles.error}>{error}</p>}

      {loading ? (
        <p>Loading…</p>
      ) : flags.length === 0 ? (
        <p>No fraud flags found.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Partner</th>
              <th style={styles.th}>Fraud Score</th>
              <th style={styles.th}>Triggered Rules</th>
              <th style={styles.th}>Explanation</th>
              <th style={styles.th}>Flagged</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {flags.map((flag) => (
              <tr key={flag.id}>
                <td style={styles.td}>{flag.partner_name}</td>
                <td style={styles.td}>
                  <span style={styles.score(flag.score)}>{flag.score.toFixed(1)}</span>
                </td>
                <td style={styles.td}>
                  {triggeredRules(flag) ?? <span style={{ color: '#9ca3af' }}>—</span>}
                </td>
                <td style={styles.td}>
                  <ExplanationTooltip explanation={flag.explanation} label="Why?" />
                </td>
                <td style={styles.td}>{new Date(flag.created_at).toLocaleDateString()}</td>
                <td style={styles.td}>
                  <span style={styles.badge(flag.status)}>
                    {flag.status === 'pending_review' ? 'pending' : flag.status}
                  </span>
                </td>
                <td style={styles.td}>
                  {flag.status === 'pending_review' && (
                    <>
                      <button
                        type="button"
                        style={styles.confirmBtn}
                        disabled={acting === flag.id}
                        onClick={() => handleReview(flag.id, 'confirmed')}
                      >
                        Confirm
                      </button>
                      <button
                        type="button"
                        style={styles.dismissBtn}
                        disabled={acting === flag.id}
                        onClick={() => handleReview(flag.id, 'dismissed')}
                      >
                        Dismiss
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
