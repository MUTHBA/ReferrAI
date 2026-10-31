// -----------------------------------------------------------------------------
// Sign in (Stitch "Sign in"). Email + password; on success the user lands on
// the page they were sent from, or their role's home page.
// -----------------------------------------------------------------------------

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/ui/password-input'
import { Spinner } from '@/components/ui/spinner'
import { homePathFor, useAuth } from '@/context/AuthContext'
import { errorMessage } from '@/lib/api'
import { login as loginRequest } from '@/lib/auth-api'

import { AuthLayout } from './AuthLayout'

export default function SignInPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const notice = location.state?.notice

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const { access_token } = await loginRequest(email.trim(), password)
      const user = login(access_token)
      const from = location.state?.from
      const home = homePathFor(user)
      navigate(from && from.startsWith(home) ? from : home, { replace: true })
    } catch (err) {
      setError(err.response?.status === 401 ? 'Email or password is incorrect.' : errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      description="Enter your email and password to continue."
      footer={
        <>
          New partner?{' '}
          <Link to="/register" className="font-semibold text-jade hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {notice && <Alert variant="success">{notice}</Alert>}
        {error && <Alert variant="error">{error}</Alert>}
        <Field label="Email">
          {(p) => (
            <Input
              {...p}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
            />
          )}
        </Field>
        <Field
          label="Password"
          action={
            <Link to="/forgot-password" className="text-caption text-jade hover:underline">
              Forgot password?
            </Link>
          }
        >
          {(p) => (
            <PasswordInput
              {...p}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          )}
        </Field>
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>
          {busy && <Spinner />}
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
