// -----------------------------------------------------------------------------
// frontend/src/pages/partner/ProfilePage.jsx
//
// Partner's own profile page (PRT-005). Shows name, tier, and a tier progress
// bar toward the next tier's referral-count threshold. Partners can update
// their own name, business name, category, and phone — status and tier are
// admin-only fields and are not shown in the edit form here.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { extractErrorMessage, getPartner, listTiers, updateOwnProfile } from '../../api/partnerApi.js'
import { useAuth } from '../../hooks/useAuth.js'

const styles = {
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', maxWidth: '560px', marginBottom: '28px' },
  infoItem: { display: 'flex', flexDirection: 'column', gap: '2px' },
  infoLabel: { fontSize: '12px', color: '#6b7280', fontWeight: 500 },
  infoValue: { fontSize: '15px', fontWeight: 600 },
  progressWrap: { marginBottom: '28px', maxWidth: '480px' },
  progressLabel: { fontSize: '13px', color: '#374151', marginBottom: '6px' },
  progressBar: { height: '10px', backgroundColor: '#e5e7eb', borderRadius: '99px', overflow: 'hidden' },
  progressFill: (pct) => ({
    height: '100%',
    width: `${Math.min(pct, 100)}%`,
    backgroundColor: '#2563eb',
    borderRadius: '99px',
    transition: 'width 0.4s ease',
  }),
  form: { display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '400px' },
  field: { display: 'flex', flexDirection: 'column', gap: '4px' },
  label: { fontSize: '13px', color: '#6b7280', fontWeight: 500 },
  input: { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px' },
  btn: {
    padding: '9px 20px', borderRadius: '6px', border: 'none',
    backgroundColor: '#2563eb', color: '#fff', fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-start',
  },
  error: { color: '#b91c1c', fontSize: '14px' },
  success: { color: '#15803d', fontSize: '14px' },
}

export default function ProfilePage() {
  const { user } = useAuth()
  const [partner, setPartner] = useState(null)
  const [tiers, setTiers] = useState([])
  const [form, setForm] = useState({ name: '', business_name: '', category: '', phone: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (!user?.sub) return
    Promise.all([getPartner(user.sub), listTiers()])
      .then(([p, t]) => {
        setPartner(p)
        setTiers(t)
        setForm({
          name: p.name ?? '',
          business_name: p.business_name ?? '',
          category: p.category ?? '',
          phone: p.phone ?? '',
        })
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [user?.sub])

  function nextTier() {
    if (!partner || tiers.length === 0) return null
    const currentRank = tiers.find((t) => t.id === partner.tier_id)?.rank_order ?? 0
    return tiers.find((t) => t.rank_order > currentRank) ?? null
  }

  function tierProgress() {
    const next = nextTier()
    if (!next || next.min_referral_count === 0) return 100
    return Math.round((partner.total_referral_count / next.min_referral_count) * 100)
  }

  async function handleSave(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const updated = await updateOwnProfile({
        name: form.name || undefined,
        business_name: form.business_name || undefined,
        category: form.category || undefined,
        phone: form.phone || undefined,
      })
      setPartner(updated)
      setSuccess('Profile updated.')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p>Loading…</p>
  if (!partner) return <p>Profile not found.</p>

  const currentTierName = tiers.find((t) => t.id === partner.tier_id)?.name ?? 'No tier'
  const next = nextTier()
  const pct = tierProgress()

  return (
    <section>
      <h1>My Profile</h1>

      <div style={styles.infoGrid}>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>Email</span>
          <span style={styles.infoValue}>{partner.email}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>Current Tier</span>
          <span style={styles.infoValue}>{currentTierName}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>Total Referrals</span>
          <span style={styles.infoValue}>{partner.total_referral_count}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>Revenue Contributed</span>
          <span style={styles.infoValue}>${Number(partner.total_revenue_contribution).toFixed(2)}</span>
        </div>
      </div>

      {next && (
        <div style={styles.progressWrap}>
          <p style={styles.progressLabel}>
            Progress to {next.name}: {partner.total_referral_count} / {next.min_referral_count} referrals ({pct}%)
          </p>
          <div style={styles.progressBar}>
            <div style={styles.progressFill(pct)} />
          </div>
        </div>
      )}

      <h2>Edit Profile</h2>
      <form style={styles.form} onSubmit={handleSave}>
        {[['name', 'Name'], ['business_name', 'Business Name'], ['category', 'Category'], ['phone', 'Phone']].map(
          ([field, label]) => (
            <label key={field} style={styles.field}>
              <span style={styles.label}>{label}</span>
              <input
                style={styles.input}
                type="text"
                value={form[field]}
                onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))}
              />
            </label>
          ),
        )}
        {error && <p style={styles.error}>{error}</p>}
        {success && <p style={styles.success}>{success}</p>}
        <button style={styles.btn} type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </form>
    </section>
  )
}
