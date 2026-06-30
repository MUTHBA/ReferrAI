// -----------------------------------------------------------------------------
// frontend/src/pages/auth/ResetPasswordPage.jsx
//
// Step 2 of the password reset flow (AUTH-004 UI, previously an unwired
// placeholder). Since this platform doesn't send real emails, there's no
// link to click with the token pre-filled — the user pastes the token
// retrieved from the backend console log alongside their new password.
// Calls POST /auth/reset-password; on success, links back to /login.
// -----------------------------------------------------------------------------

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { extractErrorMessage, resetPassword } from '../../api/authApi.js'

const styles = {
  form: { display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '360px' },
  field: { display: 'flex', flexDirection: 'column', gap: '4px' },
  input: { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px' },
  textarea: {
    padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px',
    fontFamily: 'monospace', fontSize: '12px', resize: 'vertical', minHeight: '60px',
  },
  button: {
    padding: '10px', borderRadius: '6px', border: 'none',
    backgroundColor: '#2563eb', color: '#ffffff', fontWeight: 600, cursor: 'pointer',
  },
  error: { color: '#b91c1c' },
  success: { color: '#15803d', maxWidth: '360px' },
}

export default function ResetPasswordPage() {
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await resetPassword(token, newPassword)
      setSuccess(true)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <section>
        <h1>Reset Password</h1>
        <p style={styles.success}>
          Your password has been reset. <Link to="/login">Log in</Link> with your new password.
        </p>
      </section>
    )
  }

  return (
    <section>
      <h1>Reset Password</h1>
      <form style={styles.form} onSubmit={handleSubmit}>
        <label style={styles.field}>
          Reset Token
          <textarea
            style={styles.textarea}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Paste the token from the backend console log"
            required
          />
        </label>
        <label style={styles.field}>
          New Password
          <input
            style={styles.input}
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        {error && <p style={styles.error}>{error}</p>}
        <button style={styles.button} type="submit" disabled={submitting}>
          {submitting ? 'Resetting…' : 'Reset Password'}
        </button>
      </form>
      <p>
        <Link to="/login">Back to login</Link>
      </p>
    </section>
  )
}
