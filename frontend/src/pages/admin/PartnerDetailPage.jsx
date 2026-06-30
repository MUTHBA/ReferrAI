// -----------------------------------------------------------------------------
// frontend/src/pages/admin/PartnerDetailPage.jsx
//
// Admin partner detail page (PRT-004). Shows a single partner's full profile
// with an inline edit form — admins can update status and tier_id in addition
// to name/contact fields. Reads the partner ID from the URL param (:partnerId).
// AI score cards are placeholders (Phase 4 will populate them).
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  extractErrorMessage,
  getPartner,
  listTiers,
  updatePartner,
} from '../../api/partnerApi.js'

const styles = {
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', maxWidth: '640px' },
  field: { display: 'flex', flexDirection: 'column', gap: '4px' },
  label: { fontSize: '13px', color: '#6b7280', fontWeight: 500 },
  input: { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px' },
  select: { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px' },
  actions: { marginTop: '20px', display: 'flex', gap: '10px' },
  saveBtn: {
    padding: '9px 20px', borderRadius: '6px', border: 'none',
    backgroundColor: '#2563eb', color: '#fff', fontWeight: 600, cursor: 'pointer',
  },
  error: { color: '#b91c1c', fontSize: '14px', marginTop: '8px' },
  success: { color: '#15803d', fontSize: '14px', marginTop: '8px' },
  statCards: { display: 'flex', gap: '16px', marginBottom: '28px', flexWrap: 'wrap' },
  card: {
    flex: '1 1 140px', padding: '16px', borderRadius: '8px',
    backgroundColor: '#ffffff', border: '1px solid #e5e7eb',
  },
  cardLabel: { fontSize: '12px', color: '#6b7280', margin: '0 0 4px' },
  cardValue: { fontSize: '22px', fontWeight: 700, margin: 0 },
}

const STATUS_OPTIONS = ['active', 'suspended', 'pending']

export default function PartnerDetailPage() {
  const { partnerId } = useParams()
  const [partner, setPartner] = useState(null)
  const [tiers, setTiers] = useState([])
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    Promise.all([getPartner(partnerId), listTiers()])
      .then(([p, t]) => {
        setPartner(p)
        setTiers(t)
        setForm({
          name: p.name,
          business_name: p.business_name ?? '',
          category: p.category ?? '',
          phone: p.phone ?? '',
          status: p.status,
          tier_id: p.tier_id ?? '',
        })
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [partnerId])

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  async function handleSave(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const payload = {
        name: form.name || undefined,
        business_name: form.business_name || undefined,
        category: form.category || undefined,
        phone: form.phone || undefined,
        status: form.status || undefined,
        tier_id: form.tier_id || undefined,
      }
      const updated = await updatePartner(partnerId, payload)
      setPartner(updated)
      setSuccess('Partner updated.')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p>Loading…</p>
  if (!partner) return <p>Partner not found.</p>

  return (
    <section>
      <h1>{partner.name}</h1>
      <p style={{ color: '#6b7280', marginTop: 0 }}>{partner.email}</p>

      <div style={styles.statCards}>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Referrals</p>
          <p style={styles.cardValue}>{partner.total_referral_count}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Revenue</p>
          <p style={styles.cardValue}>${Number(partner.total_revenue_contribution).toFixed(2)}</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Quality Score</p>
          <p style={styles.cardValue}>—</p>
        </div>
        <div style={styles.card}>
          <p style={styles.cardLabel}>Churn Risk</p>
          <p style={styles.cardValue}>—</p>
        </div>
      </div>

      <h2>Edit Profile</h2>
      <form onSubmit={handleSave}>
        <div style={styles.grid}>
          <label style={styles.field}>
            <span style={styles.label}>Name</span>
            <input style={styles.input} name="name" value={form.name} onChange={handleChange} />
          </label>
          <label style={styles.field}>
            <span style={styles.label}>Business Name</span>
            <input style={styles.input} name="business_name" value={form.business_name} onChange={handleChange} />
          </label>
          <label style={styles.field}>
            <span style={styles.label}>Category</span>
            <input style={styles.input} name="category" value={form.category} onChange={handleChange} />
          </label>
          <label style={styles.field}>
            <span style={styles.label}>Phone</span>
            <input style={styles.input} name="phone" value={form.phone} onChange={handleChange} />
          </label>
          <label style={styles.field}>
            <span style={styles.label}>Status</span>
            <select style={styles.select} name="status" value={form.status} onChange={handleChange}>
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label style={styles.field}>
            <span style={styles.label}>Tier</span>
            <select style={styles.select} name="tier_id" value={form.tier_id} onChange={handleChange}>
              <option value="">— no tier —</option>
              {tiers.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
        </div>
        {error && <p style={styles.error}>{error}</p>}
        {success && <p style={styles.success}>{success}</p>}
        <div style={styles.actions}>
          <button style={styles.saveBtn} type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </form>
    </section>
  )
}
