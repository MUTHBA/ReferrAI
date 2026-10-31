// -----------------------------------------------------------------------------
// Partner profile: business details (email is read-only; admins change it),
// password change, the tier ladder with progress, and account status.
// -----------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { PageHeader } from '@/components/app/PageHeader'
import { ErrorState, LoadingRows } from '@/components/app/States'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel, PanelBody, PanelHeader } from '@/components/ui/panel'
import { PasswordInput } from '@/components/ui/password-input'
import { Pill, StatusPill } from '@/components/ui/pill'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { CATEGORIES } from '@/features/auth/RegisterPage'
import { errorMessage } from '@/lib/api'
import { account, partnerApi } from '@/lib/endpoints'
import { date, money, number, rateLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

import { needsText } from './TierProgress'

function DetailsForm({ profile }) {
  const qc = useQueryClient()
  const [form, setForm] = useState(() => ({
    name: profile.name || '',
    business_name: profile.business_name || '',
    category: profile.category || '',
    phone: profile.phone || '',
  }))
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const dirty =
    form.name !== (profile.name || '') ||
    form.business_name !== (profile.business_name || '') ||
    form.category !== (profile.category || '') ||
    form.phone !== (profile.phone || '')
  const save = useMutation({
    mutationFn: () =>
      partnerApi.updateProfile({
        name: form.name.trim(),
        business_name: form.business_name.trim() || null,
        category: form.category || null,
        phone: form.phone.trim() || null,
      }),
    onSuccess: (data) => {
      qc.setQueryData(['me', 'partner'], data)
      toast.success('Profile saved.')
    },
  })
  const categories = form.category && !CATEGORIES.includes(form.category) ? [form.category, ...CATEGORIES] : CATEGORIES

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate()
      }}
      className="space-y-4"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name">{(p) => <Input {...p} value={form.name} onChange={set('name')} required autoComplete="name" />}</Field>
        <Field label="Business name">
          {(p) => <Input {...p} value={form.business_name} onChange={set('business_name')} autoComplete="organization" />}
        </Field>
        <Field label="Category">
          {(p) => (
            <Select {...p} value={form.category} onChange={set('category')}>
              <option value="">Select a category…</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Phone">{(p) => <Input {...p} type="tel" value={form.phone} onChange={set('phone')} autoComplete="tel" />}</Field>
      </div>
      <Field label="Email" helper="Contact an admin to change your email.">
        {(p) => <Input {...p} value={profile.email} readOnly disabled />}
      </Field>
      {save.isError && <Alert variant="error">{errorMessage(save.error)}</Alert>}
      <div className="flex justify-end">
        <Button type="submit" disabled={!dirty || !form.name.trim() || save.isPending}>
          {save.isPending ? <Spinner /> : <Check />}
          Save changes
        </Button>
      </div>
    </form>
  )
}

function PasswordForm() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const change = useMutation({
    mutationFn: () => account.changePassword(current, next),
    onSuccess: () => {
      toast.success('Password changed.')
      setCurrent('')
      setNext('')
    },
  })
  const short = next.length > 0 && next.length < 8
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!short) change.mutate()
      }}
      className="space-y-4"
    >
      <Field label="Current password">
        {(p) => <PasswordInput {...p} value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />}
      </Field>
      <Field label="New password" helper="At least 8 characters." error={short ? 'At least 8 characters.' : null}>
        {(p) => <PasswordInput {...p} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />}
      </Field>
      {change.isError && <Alert variant="error">{errorMessage(change.error)}</Alert>}
      <Button type="submit" variant="secondary" disabled={!current || next.length < 8 || change.isPending}>
        {change.isPending && <Spinner />}
        Change password
      </Button>
    </form>
  )
}

function TierLadder({ tiers, progress }) {
  const sorted = [...tiers].sort((a, b) => a.rank_order - b.rank_order)
  const currentIndex = sorted.findIndex((t) => t.name === progress?.current_tier)
  return (
    <ol className="space-y-3">
      {sorted.map((t, i) => {
        const current = i === currentIndex
        const reached = i <= currentIndex
        return (
          <li
            key={t.id}
            className={cn('rounded-[8px] border p-3', current ? 'border-jade bg-jade-soft/40' : 'border-line')}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-body font-semibold text-ink">
                <span
                  className={cn(
                    'grid size-5 place-items-center rounded-full border text-[10px]',
                    reached ? 'border-jade bg-jade text-white' : 'border-line text-muted-text',
                  )}
                  aria-hidden
                >
                  {reached ? <Check className="size-3" /> : i + 1}
                </span>
                {t.name} · {rateLabel(t.commission_type, t.commission_value)}
              </span>
              {current && <Pill tone="jade">Your tier</Pill>}
            </div>
            <p className="mt-1 pl-7 text-caption text-muted-text">
              {Number(t.min_referral_count) === 0 && Number(t.min_revenue_contribution) === 0
                ? 'Starting tier'
                : `Needs ${number(t.min_referral_count)} sales and ${money(t.min_revenue_contribution, { round: true })} revenue`}
            </p>
            {i === currentIndex + 1 && progress?.next_tier === t.name && (
              <div className="mt-3 pl-7">
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-jade" style={{ width: `${Math.round((progress.progress || 0) * 100)}%` }} />
                </div>
                <p className="mt-2 text-caption text-text">{needsText(progress)}</p>
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}

export default function ProfilePage() {
  const profile = useQuery({ queryKey: ['me', 'partner'], queryFn: partnerApi.profile })
  const tiers = useQuery({ queryKey: ['tiers'], queryFn: partnerApi.tiers })
  const dash = useQuery({ queryKey: ['partner-dashboard', 30], queryFn: () => partnerApi.dashboard(30) })

  return (
    <>
      <PageHeader title="Profile" description="Your business details, password and tier." />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-6">
          <Panel>
            <PanelHeader title="Business details" />
            <PanelBody>
              {profile.isLoading ? (
                <LoadingRows rows={4} className="p-0" />
              ) : profile.isError ? (
                <ErrorState error={profile.error} onRetry={profile.refetch} />
              ) : (
                <DetailsForm key={profile.data.id} profile={profile.data} />
              )}
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Password" description="Changing it also cancels any password reset links." />
            <PanelBody>
              <PasswordForm />
            </PanelBody>
          </Panel>
        </div>
        <div className="space-y-6">
          <Panel>
            <PanelHeader
              title="Your tier"
              actions={dash.data?.tier?.current_tier && <Pill tone="jade">{dash.data.tier.current_rate_label} rate</Pill>}
            />
            <PanelBody>
              {tiers.isLoading || dash.isLoading ? (
                <LoadingRows rows={3} className="p-0" />
              ) : tiers.isError ? (
                <ErrorState error={tiers.error} onRetry={tiers.refetch} />
              ) : (
                <>
                  <TierLadder tiers={tiers.data} progress={dash.data?.tier} />
                  <p className="mt-4 text-label text-muted-text">
                    Upgrades happen automatically when you reach BOTH targets, and apply to future sales.
                  </p>
                </>
              )}
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Account" />
            <PanelBody>
              {profile.data && (
                <dl className="divide-y divide-line text-caption">
                  <div className="flex justify-between gap-4 py-2">
                    <dt className="text-muted-text">Member since</dt>
                    <dd className="font-medium">{date(profile.data.created_at)}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 py-2">
                    <dt className="text-muted-text">Status</dt>
                    <dd>
                      <StatusPill kind="partner" status={profile.data.status} />
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4 py-2">
                    <dt className="text-muted-text">Tier</dt>
                    <dd className="font-medium">{dash.data?.tier?.current_tier || '—'}</dd>
                  </div>
                </dl>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  )
}
