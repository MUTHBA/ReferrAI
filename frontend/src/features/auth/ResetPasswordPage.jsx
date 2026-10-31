// -----------------------------------------------------------------------------
// Choose a new password, from the emailed link (/reset-password?token=...).
// Reset links are single-use: they stop working once the password changes.
// -----------------------------------------------------------------------------

import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { PasswordInput } from '@/components/ui/password-input'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { resetPassword } from '@/lib/auth-api'

import { AuthLayout } from './AuthLayout'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [expired, setExpired] = useState(!token)
  const [busy, setBusy] = useState(false)
  const mismatch = confirm.length > 0 && confirm !== password

  async function submit(e) {
    e.preventDefault()
    if (password.length < 8) return setError('Password must be at least 8 characters.')
    if (password !== confirm) return setError('The two passwords don’t match.')
    setBusy(true)
    setError(null)
    try {
      await resetPassword(token, password)
      navigate('/login', { replace: true, state: { notice: 'Password changed. Sign in with your new password.' } })
    } catch (err) {
      if (err.response?.status === 400) setExpired(true)
      else setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const back = (
    <Link to="/login" className="inline-flex items-center gap-1.5 font-semibold text-jade hover:underline">
      <ArrowLeft className="size-4" aria-hidden />
      Back to sign in
    </Link>
  )

  if (expired) {
    return (
      <AuthLayout title="Choose a new password" footer={back}>
        <Alert variant="error">This reset link has expired or was already used.</Alert>
        <Button asChild className="mt-4 w-full">
          <Link to="/forgot-password">Request a new link</Link>
        </Button>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Choose a new password" description="At least 8 characters." footer={back}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert variant="error">{error}</Alert>}
        <Field label="New password">
          {(p) => <PasswordInput {...p} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />}
        </Field>
        <Field label="Confirm new password" error={mismatch ? 'The passwords don’t match.' : null}>
          {(p) => <PasswordInput {...p} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
        </Field>
        <Button type="submit" className="w-full" disabled={busy || !password || !confirm}>
          {busy && <Spinner />}
          Save new password
        </Button>
      </form>
    </AuthLayout>
  )
}
