// -----------------------------------------------------------------------------
// frontend/src/pages/admin/AdminDashboardPage.jsx
//
// Admin dashboard (RPT-004). Displays KPI cards (conversions, active partners,
// total commission, pending payouts, fraud alerts), a 30-day click/conversion
// volume chart rendered as inline SVG (no external chart library), and CSV
// export buttons for referrals, commissions, and partners. The volume chart
// fills in zero-data days automatically from the API response, so the line
// is always continuous across the full date window.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import {
  downloadCommissionsCsv,
  downloadPartnersCsv,
  downloadReferralsCsv,
  getAdminDashboard,
} from '../../api/dashboardApi.js'

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
  cardSub: { fontSize: '13px', color: '#6b7280', margin: '4px 0 0' },
  section: { marginBottom: '32px' },
  sectionTitle: { fontSize: '18px', fontWeight: 700, marginBottom: '16px' },
  chartWrap: { backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '16px' },
  exportRow: { display: 'flex', gap: '10px', flexWrap: 'wrap' },
  exportBtn: {
    padding: '8px 18px', borderRadius: '6px', border: '1px solid #d1d5db',
    backgroundColor: '#ffffff', cursor: 'pointer', fontWeight: 500, fontSize: '14px',
  },
  alert: (n) => ({
    display: 'inline-block', padding: '2px 10px', borderRadius: '99px',
    backgroundColor: n > 0 ? '#fee2e2' : '#f3f4f6',
    color: n > 0 ? '#b91c1c' : '#374151',
    fontWeight: 700, fontSize: '28px',
  }),
}

function fmt(val) {
  return `$${Number(val).toFixed(2)}`
}

function VolumeChart({ data }) {
  if (!data || data.length === 0) return <p style={{ color: '#9ca3af' }}>No data yet.</p>

  const maxClicks = Math.max(...data.map((d) => d.clicks), 1)
  const W = 700
  const H = 180
  const PAD = { top: 10, right: 10, bottom: 30, left: 40 }
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const n = data.length

  const xOf = (i) => PAD.left + (i / (n - 1)) * innerW
  const yOf = (v) => PAD.top + innerH - (v / maxClicks) * innerH

  const clicksPath = data
    .map((d, i) => `${i === 0 ? 'M' : 'L'}${xOf(i).toFixed(1)},${yOf(d.clicks).toFixed(1)}`)
    .join(' ')

  const convsPath = data
    .map((d, i) => `${i === 0 ? 'M' : 'L'}${xOf(i).toFixed(1)},${yOf(d.conversions).toFixed(1)}`)
    .join(' ')

  const tickStep = Math.ceil(n / 6)
  const labelTicks = data.filter((_, i) => i % tickStep === 0 || i === n - 1)

  return (
    <div style={styles.chartWrap}>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', fontSize: '13px' }}>
        <span><svg width="12" height="4" style={{ verticalAlign: 'middle' }}><line x1="0" y1="2" x2="12" y2="2" stroke="#2563eb" strokeWidth="2" /></svg> Clicks</span>
        <span><svg width="12" height="4" style={{ verticalAlign: 'middle' }}><line x1="0" y1="2" x2="12" y2="2" stroke="#16a34a" strokeWidth="2" strokeDasharray="4 2" /></svg> Conversions</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = PAD.top + innerH * (1 - t)
          return (
            <g key={t}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#f3f4f6" strokeWidth="1" />
              <text x={PAD.left - 4} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">
                {Math.round(maxClicks * t)}
              </text>
            </g>
          )
        })}
        <path d={clicksPath} fill="none" stroke="#2563eb" strokeWidth="2" strokeLinejoin="round" />
        <path d={convsPath} fill="none" stroke="#16a34a" strokeWidth="2" strokeDasharray="5 3" strokeLinejoin="round" />
        {labelTicks.map((d) => {
          const i = data.indexOf(d)
          const label = new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          return (
            <text key={d.date} x={xOf(i)} y={H - 4} textAnchor="middle" fontSize="10" fill="#9ca3af">
              {label}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

export default function AdminDashboardPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getAdminDashboard()
      .then(setData)
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading…</p>
  if (error) return <p style={{ color: '#b91c1c' }}>{error}</p>

  const { kpis, volume_chart } = data

  return (
    <section>
      <h1>Admin Dashboard</h1>

      <div style={styles.kpiGrid}>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Total Conversions</p>
          <p style={styles.cardValue}>{kpis.total_conversions}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Active Partners</p>
          <p style={styles.cardValue}>{kpis.active_partners}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Total Commission</p>
          <p style={styles.cardValue}>{fmt(kpis.total_commission)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Pending Payouts</p>
          <p style={styles.cardValue}>{kpis.pending_payout_count}</p>
          <p style={styles.cardSub}>{fmt(kpis.pending_payout_amount)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Fraud Alerts</p>
          <p style={styles.alert(kpis.fraud_alert_count)}>{kpis.fraud_alert_count}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Churn Alerts</p>
          <p style={styles.cardValue}>{kpis.churn_alert_count}</p>
          <p style={styles.cardSub}>Phase 4 pending</p>
        </div>
      </div>

      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Referral Volume (last 30 days)</h2>
        <VolumeChart data={volume_chart} />
      </div>

      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Export Data</h2>
        <div style={styles.exportRow}>
          <button type="button" style={styles.exportBtn} onClick={downloadReferralsCsv}>
            Download referrals.csv
          </button>
          <button type="button" style={styles.exportBtn} onClick={downloadCommissionsCsv}>
            Download commissions.csv
          </button>
          <button type="button" style={styles.exportBtn} onClick={downloadPartnersCsv}>
            Download partners.csv
          </button>
        </div>
      </div>
    </section>
  )
}
