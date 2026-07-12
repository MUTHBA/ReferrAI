// -----------------------------------------------------------------------------
// frontend/src/pages/admin/PartnersPage.jsx
//
// Admin partner list page (PRT-004). Shows all partners in a sortable table
// with their status, tier, referral count, and revenue. Clicking a row
// navigates to the partner detail page (/admin/partners/:id). Status badges
// are colour-coded: active=green, suspended=red, pending=yellow.
// Added AI-RANK-002/003: "Sort by Rank" toggle and "Run Ranking" button that
// calls POST /admin/run-ranking; rank column shows composite score 0–100.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { extractErrorMessage, listPartners, runRanking } from '../../api/partnerApi.js'

const styles = {
  toolbar: { display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' },
  btn: (active) => ({
    padding: '7px 16px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    backgroundColor: active ? '#1d4ed8' : '#ffffff',
    color: active ? '#ffffff' : '#374151',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '14px',
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
  row: { cursor: 'pointer' },
  error: { color: '#b91c1c', fontSize: '14px' },
  success: { color: '#15803d', fontSize: '14px' },
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
  rankBadge: (score) => ({
    display: 'inline-block',
    minWidth: '44px',
    textAlign: 'center',
    padding: '2px 8px',
    borderRadius: '99px',
    fontSize: '12px',
    fontWeight: 700,
    backgroundColor: score === null ? '#f3f4f6' : score >= 70 ? '#dcfce7' : score >= 40 ? '#fef9c3' : '#fee2e2',
    color: score === null ? '#9ca3af' : score >= 70 ? '#15803d' : score >= 40 ? '#854d0e' : '#b91c1c',
  }),
}

export default function PartnersPage() {
  const [partners, setPartners] = useState([])
  const [loading, setLoading] = useState(true)
  const [sortByRank, setSortByRank] = useState(false)
  const [rankRunning, setRankRunning] = useState(false)
  const [rankMsg, setRankMsg] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  function fetchPartners(ranked) {
    setLoading(true)
    setError('')
    listPartners(ranked ? { sort: 'rank' } : {})
      .then(setPartners)
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchPartners(sortByRank)
  }, [sortByRank])

  async function handleRunRanking() {
    setRankRunning(true)
    setRankMsg('')
    try {
      const result = await runRanking()
      setRankMsg(`Ranking complete — ${result.partners_scored} partner(s) scored.`)
      fetchPartners(sortByRank)
    } catch {
      setRankMsg('Ranking failed. Check backend logs.')
    } finally {
      setRankRunning(false)
    }
  }

  if (loading) return <p>Loading…</p>

  return (
    <section>
      <h1>Partners</h1>
      <div style={styles.toolbar}>
        <button type="button" style={styles.btn(false)} onClick={() => setSortByRank(false)} disabled={!sortByRank}>
          Default order
        </button>
        <button type="button" style={styles.btn(sortByRank)} onClick={() => setSortByRank(true)} disabled={sortByRank}>
          Sort by Rank
        </button>
        <button type="button" style={styles.btn(false)} onClick={handleRunRanking} disabled={rankRunning}>
          {rankRunning ? 'Running…' : 'Run Ranking'}
        </button>
        {rankMsg && <span style={rankMsg.includes('failed') ? styles.error : styles.success}>{rankMsg}</span>}
      </div>
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
              <th style={styles.th}>Rank Score</th>
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
                <td style={styles.td}>
                  <span style={styles.rankBadge(p.rank_score)}>
                    {p.rank_score !== null && p.rank_score !== undefined
                      ? Number(p.rank_score).toFixed(1)
                      : '—'}
                  </span>
                </td>
                <td style={styles.td}>{new Date(p.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
