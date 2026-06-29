// -----------------------------------------------------------------------------
// frontend/src/pages/admin/SettingsPage.jsx
//
// Admin settings table with inline editing. Values are displayed and edited
// as JSON strings so every JSONB shape (string, number, object) works uniformly.
// Each save writes one PUT /api/v1/settings/{key} and refreshes only that row.
// -----------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { extractErrorMessage, getSettings, updateSetting } from '../../api/settingsApi.js'

const tdStyle = { padding: '0.6rem 0.75rem', verticalAlign: 'middle' }
const thStyle = { ...tdStyle, textAlign: 'left', borderBottom: '2px solid #d1d5db' }
const rowStyle = { borderBottom: '1px solid #e5e7eb' }

export default function SettingsPage() {
  const [settings, setSettings] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [editingKey, setEditingKey] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState(null) // { key, ok, message }

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => setLoadError('Failed to load settings.'))
      .finally(() => setLoading(false))
  }, [])

  function startEdit(setting) {
    setEditingKey(setting.key)
    setEditValue(JSON.stringify(setting.value))
    setFeedback(null)
  }

  function cancelEdit() {
    setEditingKey(null)
    setEditValue('')
  }

  async function saveEdit(key) {
    let parsed
    try {
      parsed = JSON.parse(editValue)
    } catch {
      setFeedback({ key, ok: false, message: 'Invalid JSON — check the value and try again.' })
      return
    }

    setSaving(true)
    try {
      const updated = await updateSetting(key, parsed)
      setSettings((prev) => prev.map((s) => (s.key === key ? updated : s)))
      setEditingKey(null)
      setEditValue('')
      setFeedback({ key, ok: true, message: 'Saved.' })
    } catch (err) {
      setFeedback({ key, ok: false, message: extractErrorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <section style={{ padding: '1rem' }}>
        <p>Loading settings…</p>
      </section>
    )
  }

  if (loadError) {
    return (
      <section style={{ padding: '1rem' }}>
        <p style={{ color: '#dc2626' }}>{loadError}</p>
      </section>
    )
  }

  return (
    <section style={{ padding: '1rem' }}>
      <h1 style={{ marginBottom: '1rem' }}>Settings</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr>
            <th style={thStyle}>Key</th>
            <th style={thStyle}>Description</th>
            <th style={{ ...thStyle, minWidth: '200px' }}>Value</th>
            <th style={{ ...thStyle, width: '130px' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {settings.map((s) => (
            <tr key={s.key} style={rowStyle}>
              <td style={{ ...tdStyle, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                {s.key}
              </td>
              <td style={{ ...tdStyle, color: '#6b7280' }}>{s.description ?? '—'}</td>
              <td style={tdStyle}>
                {editingKey === s.key ? (
                  <input
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    disabled={saving}
                    style={{
                      width: '100%',
                      fontFamily: 'monospace',
                      padding: '0.25rem 0.5rem',
                      border: '1px solid #9ca3af',
                      borderRadius: '4px',
                      boxSizing: 'border-box',
                    }}
                  />
                ) : (
                  <code style={{ background: '#f3f4f6', padding: '0.1rem 0.3rem', borderRadius: '3px' }}>
                    {JSON.stringify(s.value)}
                  </code>
                )}
                {feedback?.key === s.key && (
                  <div
                    style={{
                      marginTop: '0.25rem',
                      fontSize: '0.8rem',
                      color: feedback.ok ? '#16a34a' : '#dc2626',
                    }}
                  >
                    {feedback.message}
                  </div>
                )}
              </td>
              <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                {editingKey === s.key ? (
                  <>
                    <button
                      onClick={() => saveEdit(s.key)}
                      disabled={saving}
                      style={{ marginRight: '0.4rem' }}
                    >
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button onClick={cancelEdit} disabled={saving}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <button onClick={() => startEdit(s)}>Edit</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
