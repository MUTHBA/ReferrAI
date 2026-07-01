// -----------------------------------------------------------------------------
// frontend/src/pages/partner/ReferralsPage.jsx
//
// Partner referral management (REF-006 + AI-QUAL-004). Three sections:
//   1. My Referral Links  — link cards with copy + QR buttons
//   2. My Referral Codes  — code cards with copy button
//   3. My Conversions     — conversion cards with AI quality score badge
//
// Quality score badges are color-coded: green ≥70, yellow 40–69, red <40,
// grey "Pending" when the background scoring task has not yet completed.
// All styles are inline — no CSS files, no new dependencies.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import ScoreBadge from '../../components/ai/ScoreBadge.jsx'
import QRCodeModal from '../../components/referrals/QRCodeModal.jsx'
import {
  createCode,
  createLink,
  extractErrorMessage,
  getMyCode,
  getMyConversions,
  getMyLinks,
} from '../../api/referrals.js'

// ---------------------------------------------------------------------------
// Styles — matches the palette and spacing used by WalletPage / ProfilePage
// ---------------------------------------------------------------------------

const styles = {
  section: { marginBottom: '40px' },

  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '16px',
  },
  sectionTitle: { fontSize: '18px', fontWeight: 700, margin: 0 },

  cardGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
  },

  linkCard: {
    flex: '1 1 300px',
    maxWidth: '460px',
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },

  codeCard: {
    flex: '1 1 200px',
    maxWidth: '280px',
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },

  conversionCard: {
    flex: '1 1 200px',
    maxWidth: '300px',
    padding: '20px',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },

  referralUrl: {
    fontFamily: 'monospace',
    fontSize: '13px',
    color: '#111827',
    wordBreak: 'break-all',
    margin: 0,
  },

  codeText: {
    fontFamily: 'monospace',
    fontSize: '22px',
    fontWeight: 700,
    letterSpacing: '0.1em',
    color: '#111827',
    margin: 0,
  },

  conversionValue: {
    fontSize: '18px',
    fontWeight: 700,
    color: '#111827',
    margin: 0,
  },

  metaText: { fontSize: '12px', color: '#6b7280', margin: 0 },

  cardActions: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' },

  cardRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  btnPrimary: {
    padding: '9px 18px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: '#2563eb',
    color: '#ffffff',
    fontWeight: 600,
    fontSize: '14px',
    cursor: 'pointer',
  },

  btnOutline: {
    padding: '6px 14px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    backgroundColor: '#ffffff',
    color: '#374151',
    fontWeight: 500,
    fontSize: '13px',
    cursor: 'pointer',
  },

  inlineForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    maxWidth: '420px',
    padding: '16px',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    backgroundColor: '#ffffff',
    marginBottom: '16px',
  },

  fieldLabel: { fontSize: '13px', color: '#6b7280', fontWeight: 500 },

  input: {
    padding: '8px 10px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '14px',
    width: '100%',
    boxSizing: 'border-box',
  },

  formActions: { display: 'flex', gap: '10px' },

  error: { color: '#b91c1c', fontSize: '14px', margin: 0 },
  empty: { color: '#6b7280', fontSize: '14px' },

  copiedLabel: {
    padding: '6px 14px',
    borderRadius: '6px',
    border: '1px solid #bbf7d0',
    backgroundColor: '#f0fdf4',
    color: '#15803d',
    fontWeight: 500,
    fontSize: '13px',
  },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function fmtCurrency(value) {
  return `$${parseFloat(value).toFixed(2)}`
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CopyButton({ text, itemId, copiedId, label, onCopy }) {
  if (copiedId === itemId) {
    return <span style={styles.copiedLabel}>Copied!</span>
  }
  return (
    <button type="button" style={styles.btnOutline} onClick={() => onCopy(text, itemId)}>
      {label ?? 'Copy'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ReferralsPage() {
  const [links, setLinks] = useState([])
  const [codes, setCodes] = useState([])
  const [conversions, setConversions] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [showLinkForm, setShowLinkForm] = useState(false)
  const [destinationUrl, setDestinationUrl] = useState('')
  const [creatingLink, setCreatingLink] = useState(false)
  const [linkError, setLinkError] = useState('')

  const [creatingCode, setCreatingCode] = useState(false)
  const [codeError, setCodeError] = useState('')

  const [copiedId, setCopiedId] = useState(null)
  const [qrData, setQrData] = useState(null)

  useEffect(() => {
    Promise.all([getMyLinks(), getMyCode(), getMyConversions()])
      .then(([l, c, convs]) => {
        setLinks(l)
        setCodes(c)
        setConversions(convs)
      })
      .catch(() => setLoadError('Failed to load referral data.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCopy(text, id) {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      // Clipboard API unavailable — fail silently
    }
  }

  async function handleCreateLink(e) {
    e.preventDefault()
    setLinkError('')
    setCreatingLink(true)
    try {
      const newLink = await createLink(destinationUrl)
      setLinks((prev) => [newLink, ...prev])
      setDestinationUrl('')
      setShowLinkForm(false)
    } catch (err) {
      setLinkError(extractErrorMessage(err))
    } finally {
      setCreatingLink(false)
    }
  }

  async function handleCreateCode() {
    setCodeError('')
    setCreatingCode(true)
    try {
      const newCode = await createCode()
      setCodes((prev) => [newCode, ...prev])
    } catch (err) {
      setCodeError(extractErrorMessage(err))
    } finally {
      setCreatingCode(false)
    }
  }

  if (loading) return <p>Loading…</p>
  if (loadError) return <p style={styles.error}>{loadError}</p>

  return (
    <section>
      <h1>Referrals</h1>

      {/* ---- Referral Links ---- */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>My Referral Links</h2>
          {!showLinkForm && (
            <button
              type="button"
              style={styles.btnPrimary}
              onClick={() => {
                setShowLinkForm(true)
                setLinkError('')
              }}
            >
              Generate New Link
            </button>
          )}
        </div>

        {showLinkForm && (
          <form style={styles.inlineForm} onSubmit={handleCreateLink}>
            <label style={styles.fieldLabel}>
              Destination URL
              <span style={{ color: '#9ca3af', fontWeight: 400 }}>
                {' '}— where visitors land after clicking your link
              </span>
            </label>
            <input
              style={styles.input}
              type="url"
              placeholder="https://example.com/landing-page"
              value={destinationUrl}
              onChange={(e) => setDestinationUrl(e.target.value)}
              required
              disabled={creatingLink}
            />
            {linkError && <p style={styles.error}>{linkError}</p>}
            <div style={styles.formActions}>
              <button type="submit" style={styles.btnPrimary} disabled={creatingLink}>
                {creatingLink ? 'Creating…' : 'Create Link'}
              </button>
              <button
                type="button"
                style={styles.btnOutline}
                disabled={creatingLink}
                onClick={() => {
                  setShowLinkForm(false)
                  setLinkError('')
                  setDestinationUrl('')
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {links.length === 0 ? (
          <p style={styles.empty}>No referral links yet. Generate one above.</p>
        ) : (
          <div style={styles.cardGrid}>
            {links.map((link) => (
              <div key={link.id} style={styles.linkCard}>
                <p style={styles.referralUrl}>{link.referral_url}</p>
                <p style={styles.metaText}>→ {link.destination_url}</p>
                <p style={styles.metaText}>Created {fmtDate(link.created_at)}</p>
                <div style={styles.cardActions}>
                  <CopyButton
                    text={link.referral_url}
                    itemId={link.id}
                    copiedId={copiedId}
                    label="Copy URL"
                    onCopy={handleCopy}
                  />
                  {link.qr_code_data && (
                    <button
                      type="button"
                      style={styles.btnOutline}
                      onClick={() => setQrData(link.qr_code_data)}
                    >
                      Show QR
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Referral Codes ---- */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>My Referral Codes</h2>
          <button
            type="button"
            style={{ ...styles.btnPrimary, opacity: creatingCode ? 0.7 : 1 }}
            onClick={handleCreateCode}
            disabled={creatingCode}
          >
            {creatingCode ? 'Generating…' : 'Generate New Code'}
          </button>
        </div>

        {codeError && <p style={{ ...styles.error, marginBottom: '12px' }}>{codeError}</p>}

        {codes.length === 0 ? (
          <p style={styles.empty}>No referral codes yet. Generate one above.</p>
        ) : (
          <div style={styles.cardGrid}>
            {codes.map((code) => (
              <div key={code.id} style={styles.codeCard}>
                <p style={styles.codeText}>{code.code}</p>
                <p style={styles.metaText}>Created {fmtDate(code.created_at)}</p>
                <div style={styles.cardActions}>
                  <CopyButton
                    text={code.code}
                    itemId={code.id}
                    copiedId={copiedId}
                    label="Copy Code"
                    onCopy={handleCopy}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- My Conversions ---- */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>My Conversions</h2>
        </div>

        {conversions.length === 0 ? (
          <p style={styles.empty}>No conversions recorded yet.</p>
        ) : (
          <div style={styles.cardGrid}>
            {conversions.map((conv) => (
              <div key={conv.id} style={styles.conversionCard}>
                <div style={styles.cardRow}>
                  <p style={styles.conversionValue}>{fmtCurrency(conv.conversion_value)}</p>
                  <ScoreBadge
                    score={conv.quality_score}
                    label="Quality"
                    explanation={conv.quality_explanation ?? null}
                  />
                </div>
                <p style={styles.metaText}>{fmtDate(conv.converted_at)}</p>
                <p style={styles.metaText}>
                  {conv.attribution_model.replace('_', ' ')}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* QR modal — rendered at page root to avoid z-index issues with cards */}
      {qrData && <QRCodeModal base64PngData={qrData} onClose={() => setQrData(null)} />}
    </section>
  )
}
