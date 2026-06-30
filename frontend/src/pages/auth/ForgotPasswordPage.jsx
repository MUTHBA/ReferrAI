// -----------------------------------------------------------------------------
// frontend/src/pages/auth/ForgotPasswordPage.jsx
//
// Step 1 of the password reset flow. Submits the email to
// POST /auth/forgot-password, which always returns the same generic message
// regardless of whether the account exists (no email enumeration — see
// CLAUDE.md). Since this platform doesn't send real emails (the reset token
// is logged server-side per AUTH-004's scope), the success message tells the
// user to retrieve the token from the backend console and continue to
// /reset-password to enter it.
// -----------------------------------------------------------------------------

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { extractErrorMessage, forgotPassword } from '../../api/authApi.js'

const styles = {
  form: { display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '360px' },
  field: { display: 'flex', flexDirection: 'column', gap: '4px' },
  input: { padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: '6px' },
  button: {
    padding: '10px', borderRadius: '6px', border: 'none',
    backgroundColor: '#2563eb', color: '#ffffff', fontWeight: 600, cursor: 'pointer',
  },
  error: { color: '#b91c1c' },
  success: { color: '#15803d', maxWidth: '360px' },
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await forgotPassword(email)
      setSubmitted(true)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <section>
        <h1>Forgot Password</h1>
        <p style={styles.success}>
          If that email is registered, a reset token has been issued. In this dev environment,
          emails are not actually sent — ask an admin to check the backend console log for your
          token, then continue to{' '}
          <Link to="/reset-password">Reset Password</Link> to enter it.
        </p>
      </section>
    )
  }

  return (
    <section>
      <h1>Forgot Password</h1>
      <form style={styles.form} onSubmit={handleSubmit}>
        <label style={styles.field}>
          Email
          <input
            style={styles.input}
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        {error && <p style={styles.error}>{error}</p>}
        <button style={styles.button} type="submit" disabled={submitting}>
          {submitting ? 'Sending…' : 'Send Reset Link'}
        </button>
      </form>
      <p>
        Remembered it? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
