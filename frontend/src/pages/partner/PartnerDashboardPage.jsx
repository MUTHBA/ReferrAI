// -----------------------------------------------------------------------------
// frontend/src/pages/partner/PartnerDashboardPage.jsx
//
// Partner dashboard (RPT-005). Shows KPI cards (referral count, conversion
// count, total earnings, wallet balance) and AI score cards for quality,
// churn risk, and rank. Score cards display "Pending" until Phase 4 scoring
// runs are executed — the API returns null for these fields until then.
// This is the first page a partner sees after login (redirected from
// RegisterPage/LoginPage on successful auth).
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { getPartnerDashboard } from '../../api/dashboardApi.js'

const styles = {
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '16px',
    marginBottom: '32px',
  },
  card: {
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
  },
  cardLabel: { fontSize: '12px', color: '#6b7280', margin: '0 0 6px', fontWeight: 500 },
  cardValue: { fontSize: '28px', fontWeight: 700, margin: 0 },
  cardSub: { fontSize: '12px', color: '#9ca3af', margin: '4px 0 0' },
  aiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '16px',
    marginBottom: '32px',
  },
  aiCard: (score) => ({
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: `1px solid ${score === null ? '#e5e7eb' : score >= 70 ? '#bbf7d0' : score >= 40 ? '#fef08a' : '#fecaca'}`,
  }),
  scoreBadge: (score) => ({
    fontSize: '28px',
    fontWeight: 700,
    margin: 0,
    color: score === null ? '#9ca3af' : score >= 70 ? '#15803d' : score >= 40 ? '#854d0e' : '#b91c1c',
  }),
  sectionTitle: { fontSize: '18px', fontWeight: 700, marginBottom: '16px' },
}

function fmt(val) {
  return `$${Number(val).toFixed(2)}`
}

function ScoreCard({ label, score, description }) {
  return (
    <div style={styles.aiCard(score)}>
      <p style={styles.cardLabel}>{label}</p>
      <p style={styles.scoreBadge(score)}>
        {score !== null && score !== undefined ? `${Number(score).toFixed(0)}` : '—'}
      </p>
      <p style={styles.cardSub}>{score === null || score === undefined ? 'Pending (Phase 4)' : description}</p>
    </div>
  )
}

export default function PartnerDashboardPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getPartnerDashboard()
      .then(setData)
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading…</p>
  if (error) return <p style={{ color: '#b91c1c' }}>{error}</p>

  const { kpis, quality_score, churn_score, rank_score } = data

  return (
    <section>
      <h1>Partner Dashboard</h1>

      <div style={styles.kpiGrid}>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Referral Links & Codes</p>
          <p style={styles.cardValue}>{kpis.referral_count}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Conversions</p>
          <p style={styles.cardValue}>{kpis.conversion_count}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Total Earned</p>
          <p style={styles.cardValue}>{fmt(kpis.total_earnings)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Wallet Balance</p>
          <p style={styles.cardValue}>{fmt(kpis.wallet_balance)}</p>
        </div>
      </div>

      <h2 style={styles.sectionTitle}>AI Score Cards</h2>
      <div style={styles.aiGrid}>
        <ScoreCard
          label="Referral Quality"
          score={quality_score}
          description="Score 0–100. Higher is better."
        />
        <ScoreCard
          label="Churn Risk"
          score={churn_score}
          description="Score 0–100. Lower is better."
        />
        <ScoreCard
          label="Partner Rank Score"
          score={rank_score}
          description="Composite score 0–100."
        />
      </div>
    </section>
  )
}
