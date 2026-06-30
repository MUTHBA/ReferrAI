// -----------------------------------------------------------------------------
// frontend/src/pages/admin/PartnersPage.jsx
//
// Admin partner list page (PRT-004). Shows all partners in a sortable table
// with their status, tier, referral count, and revenue. Clicking a row
// navigates to the partner detail page (/admin/partners/:id). Status badges
// are colour-coded: active=green, suspended=red, pending=yellow.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { extractErrorMessage, listPartners } from '../../api/partnerApi.js'

const styles = {
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '2px solid #e5e7eb',
    color: '#374151',
    fontWeight: 600,
    cursor: 'pointer',
    userSelect: 'none',
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f3f4f6' },
  row: { cursor: 'pointer' },
  error: { color: '#b91c1c', fontSize: '14px' },
  badge: (status) => ({
    padding: '2px 10px',
    borderRadius: '99px',
    fontSize: '12px',
    fontWeight: 600,
    backgroundColor:
      status === 'active' ? '#dcfce7' : status === 'suspended' ? '#fee2e2' : '#fef9c3',
    color:
      status === 'active' ? '#15803d' : status === 'suspended' ? '#b91c1c' : '#854d0e',
  }),
}

export default function PartnersPage() {
  const [partners, setPartners] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    listPartners()
      .then(setPartners)
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading…</p>

  return (
    <section>
      <h1>Partners</h1>
      {error && <p style={styles.error}>{error}</p>}
      {partners.length === 0 ? (
        <p>No partners yet.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Email</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Referrals</th>
              <th style={styles.th}>Revenue</th>
              <th style={styles.th}>Joined</th>
            </tr>
          </thead>
          <tbody>
            {partners.map((p) => (
              <tr
                key={p.id}
                style={styles.row}
                onClick={() => navigate(`/admin/partners/${p.id}`)}
              >
                <td style={styles.td}>{p.name}</td>
                <td style={styles.td}>{p.email}</td>
                <td style={styles.td}>
                  <span style={styles.badge(p.status)}>{p.status}</span>
                </td>
                <td style={styles.td}>{p.total_referral_count}</td>
                <td style={styles.td}>${Number(p.total_revenue_contribution).toFixed(2)}</td>
                <td style={styles.td}>{new Date(p.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
