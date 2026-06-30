// -----------------------------------------------------------------------------
// frontend/src/pages/auth/LoginPage.jsx
//
// Email/password login form. On success, decodes the returned JWT via
// useAuth().login() and redirects by role (admin → /admin, everyone else →
// /partner). Backend error messages (401 bad credentials, 422 validation)
// are surfaced inline via extractErrorMessage rather than thrown to a
// global handler, since the global axios 401 interceptor deliberately
// ignores the login endpoint's own 401s — see axiosInstance.js. Added a
// "Forgot password?" link to /forgot-password, wiring up the previously
// orphaned AUTH-004 password reset flow.
// -----------------------------------------------------------------------------

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login, extractErrorMessage } from '../../api/authApi.js'
import { useAuth } from '../../hooks/useAuth.js'

const styles = {
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    maxWidth: '320px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  input: {
    padding: '8px 10px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
  },
  button: {
    padding: '10px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: '#2563eb',
    color: '#ffffff',
    fontWeight: 600,
    cursor: 'pointer',
  },
  error: {
    color: '#b91c1c',
  },
}

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { login: setAuthSession } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const { access_token } = await login(email, password)
      const user = setAuthSession(access_token)
      navigate(user?.role === 'admin' ? '/admin' : '/partner', { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section>
      <h1>Login</h1>
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
        <label style={styles.field}>
          Password
          <input
            style={styles.input}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p style={styles.error}>{error}</p>}
        <button style={styles.button} type="submit" disabled={submitting}>
          {submitting ? 'Logging in...' : 'Log in'}
        </button>
      </form>
      <p>
        <Link to="/forgot-password">Forgot password?</Link>
      </p>
      <p>
        No account yet? <Link to="/register">Register</Link>
      </p>
    </section>
  )
}
