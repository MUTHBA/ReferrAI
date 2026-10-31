// -----------------------------------------------------------------------------
// Become a partner (sign-up). Creates a partner account (admins are created
// with the backend CLI), signs in, then saves the optional profile details
// (business name, category, phone) to the new partner profile.
// -----------------------------------------------------------------------------

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/ui/password-input'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/context/AuthContext'
import { errorMessage } from '@/lib/api'
import { login as loginRequest, registerPartner } from '@/lib/auth-api'
import { partnerApi } from '@/lib/endpoints'

import { AuthLayout } from './AuthLayout'

export const CATEGORIES = [
  'Fitness',
  'Fashion & apparel',
  'Food & drink',
  'Tech & productivity',
  'Beauty',
  'Travel',
  'Wellness & nutrition',
  'Other',
]

export default function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', business_name: '', category: '', phone: '', email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const passwordShort = form.password.length > 0 && form.password.length < 8

  async function submit(e) {
    e.preventDefault()
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await registerPartner({ name: form.name.trim(), email: form.email.trim(), password: form.password })
      const { access_token } = await loginRequest(form.email.trim(), form.password)
      login(access_token)
      const extra = {
        business_name: form.business_name.trim() || null,
        category: form.category || null,
        phone: form.phone.trim() || null,
      }
      if (extra.business_name || extra.category || extra.phone) {
        await partnerApi.updateProfile(extra).catch(() => {})
      }
      navigate('/partner', { replace: true })
    } catch (err) {
      setError(err.response?.status === 409 ? 'An account with this email already exists. Sign in instead.' : errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Become a partner"
      description="Earn commission on every sale you refer."
      footer={
        <>
          Already a partner?{' '}
          <Link to="/login" className="font-semibold text-jade hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert variant="error">{error}</Alert>}
        <Field label="Full name">
          {(p) => <Input {...p} autoComplete="name" value={form.name} onChange={set('name')} placeholder="Alex Morgan" required autoFocus />}
        </Field>
        <Field label="Business name (optional)">
          {(p) => <Input {...p} autoComplete="organization" value={form.business_name} onChange={set('business_name')} placeholder="Morgan Studio" />}
        </Field>
        <Field label="Category">
          {(p) => (
            <Select {...p} value={form.category} onChange={set('category')}>
              <option value="">Select a category…</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Phone (optional)">
          {(p) => <Input {...p} type="tel" autoComplete="tel" value={form.phone} onChange={set('phone')} placeholder="+1 555 019 2834" />}
        </Field>
        <Field label="Email">
          {(p) => <Input {...p} type="email" autoComplete="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required />}
        </Field>
        <Field label="Password" helper="At least 8 characters." error={passwordShort ? 'At least 8 characters.' : null}>
          {(p) => <PasswordInput {...p} autoComplete="new-password" value={form.password} onChange={set('password')} required />}
        </Field>
        <Button type="submit" className="w-full" disabled={busy || !form.name || !form.email || !form.password}>
          {busy && <Spinner />}
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
