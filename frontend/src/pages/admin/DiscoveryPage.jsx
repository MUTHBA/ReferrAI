// -----------------------------------------------------------------------------
// frontend/src/pages/admin/DiscoveryPage.jsx
//
// AI Partner Discovery UI (AI-DISC-002, AI-DISC-003). Replaces the placeholder.
// The admin uploads a CSV file (columns: business_name, category, description,
// city, country) — the file is parsed client-side and submitted as a JSON array
// to POST /admin/discovery/candidates. Results are displayed in a ranked table
// with: potential score (colour-coded), category/geo sub-scores surfaced via
// ExplanationTooltip, and Invite/Dismiss action buttons that call
// PATCH /admin/discovery/candidates/{id}.
// CSV parsing is done without an external library — quotes and commas are handled
// by a hand-rolled tokeniser that covers all common CSV dialects.
// -----------------------------------------------------------------------------

import { useRef, useState } from 'react'
import ExplanationTooltip from '../../components/common/ExplanationTooltip.jsx'
import {
  extractErrorMessage,
  scoreDiscoveryCandidates,
  updateDiscoveryCandidateStatus,
} from '../../api/discoveryApi.js'

// ---------------------------------------------------------------------------
// CSV parsing (no external dependency)
// ---------------------------------------------------------------------------

function parseCSVLine(line) {
  const values = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (ch === ',' && !inQuotes) {
      values.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  values.push(current.trim())
  return values
}

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) return []
  const header = parseCSVLine(lines[0]).map((h) => h.toLowerCase().replace(/\s+/g, '_'))
  return lines.slice(1).map((line) => {
    const vals = parseCSVLine(line)
    return Object.fromEntries(header.map((h, i) => [h, vals[i] ?? '']))
  })
}

// ---------------------------------------------------------------------------
// Score factor rendering (for ExplanationTooltip)
// ---------------------------------------------------------------------------

function formatFactors(factors) {
  if (!factors) return null
  const pct = (v) => `${(Number(v) * 100).toFixed(0)}%`
  return [
    `Semantic similarity: ${pct(factors.similarity)}`,
    `Category match: ${pct(factors.category_match)}`,
    `Geographic fit: ${pct(factors.geographic)}`,
  ].join('\n')
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = {
  uploadBox: {
    border: '2px dashed #d1d5db',
    borderRadius: '8px',
    padding: '24px',
    textAlign: 'center',
    marginBottom: '24px',
    backgroundColor: '#f9fafb',
  },
  fileInput: { display: 'none' },
  uploadBtn: {
    padding: '8px 20px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    backgroundColor: '#ffffff',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '14px',
    marginRight: '10px',
  },
  submitBtn: {
    padding: '8px 20px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: '#2563eb',
    color: '#ffffff',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '14px',
  },
  hintText: { fontSize: '12px', color: '#6b7280', marginTop: '8px' },
  error: { color: '#b91c1c', fontSize: '14px', margin: '8px 0' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '14px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '2px solid #e5e7eb',
    color: '#374151',
    fontWeight: 600,
  },
  td: { padding: '10px 12px', borderBottom: '1px solid #f3f4f6', verticalAlign: 'middle' },
  scoreBadge: (score) => ({
    display: 'inline-block',
    minWidth: '48px',
    textAlign: 'center',
    padding: '3px 10px',
    borderRadius: '99px',
    fontSize: '13px',
    fontWeight: 700,
    backgroundColor:
      score === null ? '#f3f4f6'
      : score >= 70 ? '#dcfce7'
      : score >= 40 ? '#fef9c3'
      : '#fee2e2',
    color:
      score === null ? '#9ca3af'
      : score >= 70 ? '#15803d'
      : score >= 40 ? '#854d0e'
      : '#b91c1c',
  }),
  statusBadge: (s) => ({
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: '99px',
    fontSize: '12px',
    fontWeight: 600,
    backgroundColor:
      s === 'invited' ? '#dcfce7'
      : s === 'dismissed' ? '#f3f4f6'
      : s === 'reviewed' ? '#ede9fe'
      : '#fef9c3',
    color:
      s === 'invited' ? '#15803d'
      : s === 'dismissed' ? '#6b7280'
      : s === 'reviewed' ? '#5b21b6'
      : '#854d0e',
  }),
  actionBtn: (variant) => ({
    padding: '4px 12px',
    borderRadius: '5px',
    border: 'none',
    backgroundColor: variant === 'invite' ? '#16a34a' : '#6b7280',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '13px',
    marginRight: '6px',
  }),
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DiscoveryPage() {
  const [candidates, setCandidates] = useState([])
  const [fileName, setFileName] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState(null)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    setFileName(file.name)
    setError('')
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const parsed = parseCSV(ev.target.result)
        setCandidates(parsed)
      } catch {
        setError('Could not parse CSV. Check the file format.')
      }
    }
    reader.readAsText(file)
  }

  async function handleSubmit() {
    if (candidates.length === 0) {
      setError('No candidates to score. Upload a CSV first.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await scoreDiscoveryCandidates(candidates)
      setResults(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleAction(id, newStatus) {
    setActing(id)
    setError('')
    try {
      const updated = await updateDiscoveryCandidateStatus(id, newStatus)
      setResults((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r))
      )
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setActing(null)
    }
  }

  return (
    <section>
      <h1>Partner Discovery</h1>

      <div style={styles.uploadBox}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={styles.fileInput}
          onChange={handleFileChange}
        />
        <button
          type="button"
          style={styles.uploadBtn}
          onClick={() => fileInputRef.current?.click()}
        >
          {fileName ? `📄 ${fileName}` : 'Choose CSV file'}
        </button>
        <button
          type="button"
          style={styles.submitBtn}
          disabled={loading || candidates.length === 0}
          onClick={handleSubmit}
        >
          {loading ? 'Scoring…' : `Score ${candidates.length > 0 ? `${candidates.length} ` : ''}Candidates`}
        </button>
        <p style={styles.hintText}>
          CSV columns: <strong>business_name, category, description, city, country</strong>
        </p>
      </div>

      {error && <p style={styles.error}>{error}</p>}

      {results.length > 0 && (
        <>
          <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '16px' }}>
            Results — {results.length} candidate{results.length !== 1 ? 's' : ''} ranked by fit score
          </h2>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>#</th>
                <th style={styles.th}>Business Name</th>
                <th style={styles.th}>Category</th>
                <th style={styles.th}>Location</th>
                <th style={styles.th}>Potential Score</th>
                <th style={styles.th}>Score Factors</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => {
                const geo = r.geographic_data ?? {}
                const location = [geo.city, geo.country].filter(Boolean).join(', ') || '—'
                const factorText = formatFactors(r.score_factors)
                return (
                  <tr key={r.id}>
                    <td style={styles.td}>{idx + 1}</td>
                    <td style={styles.td}><strong>{r.candidate_name}</strong></td>
                    <td style={styles.td}>{r.business_category || '—'}</td>
                    <td style={styles.td}>{location}</td>
                    <td style={styles.td}>
                      <span style={styles.scoreBadge(r.potential_score)}>
                        {r.potential_score !== null && r.potential_score !== undefined
                          ? Number(r.potential_score).toFixed(1)
                          : '—'}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <ExplanationTooltip explanation={factorText} label="Factors" />
                    </td>
                    <td style={styles.td}>
                      <span style={styles.statusBadge(r.status)}>{r.status}</span>
                    </td>
                    <td style={styles.td}>
                      {r.status === 'new' || r.status === 'reviewed' ? (
                        <>
                          <button
                            type="button"
                            style={styles.actionBtn('invite')}
                            disabled={acting === r.id}
                            onClick={() => handleAction(r.id, 'invited')}
                          >
                            Invite
                          </button>
                          <button
                            type="button"
                            style={styles.actionBtn('dismiss')}
                            disabled={acting === r.id}
                            onClick={() => handleAction(r.id, 'dismissed')}
                          >
                            Dismiss
                          </button>
                        </>
                      ) : (
                        <span style={{ color: '#9ca3af', fontSize: '12px' }}>—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
