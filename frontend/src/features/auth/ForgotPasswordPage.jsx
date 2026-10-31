// -----------------------------------------------------------------------------
// Reset your password: request a reset link. The response is the same whether
// or not the email exists, so the page never reveals which emails have accounts.
// -----------------------------------------------------------------------------

import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { requestPasswordReset } from '@/lib/auth-api'

import { AuthLayout } from './AuthLayout'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await requestPasswordReset(email.trim())
      setSent(true)
    } catch (err) {
      setError(errorMessage(err))
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

  if (sent) {
    return (
      <AuthLayout title="Check your email" footer={back}>
        <Alert variant="success">
          If an account exists for <strong>{email}</strong>, we&apos;ve sent a reset link. It expires in 15 minutes.
        </Alert>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Reset your password" description="Enter your email and we'll send you a link to reset your password." footer={back}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert variant="error">{error}</Alert>}
        <Field label="Email">
          {(p) => (
            <Input {...p} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required autoFocus />
          )}
        </Field>
        <Button type="submit" className="w-full" disabled={busy || !email}>
          {busy && <Spinner />}
          Send reset link
        </Button>
      </form>
    </AuthLayout>
  )
}
