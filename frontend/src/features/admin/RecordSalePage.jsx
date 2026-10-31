// -----------------------------------------------------------------------------
// Record a sale manually (the shop can also send sales to the API). Recording
// attributes the sale to a click (first/last click within the attribution
// window), calculates the commission at the partner's tier rate, credits the
// wallet and checks for a tier upgrade — all in one step. The AI quality
// score follows a few seconds later.
// -----------------------------------------------------------------------------

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, CirclePlus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/app/PageHeader'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel, PanelBody, PanelHeader } from '@/components/ui/panel'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { money, rateLabel, toNumber } from '@/lib/format'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function commissionFor(type, rate, value) {
  if (value === null || rate === null) return null
  return type === 'fixed' ? rate : Math.round(value * rate * 100) / 100
}

export default function RecordSalePage() {
  const qc = useQueryClient()
  const partners = useQuery({ queryKey: ['partners'], queryFn: () => adminApi.partners() })
  const tiers = useQuery({ queryKey: ['tiers'], queryFn: adminApi.tiers })
  const settings = useQuery({ queryKey: ['settings'], queryFn: adminApi.settings })
  const [form, setForm] = useState({ partner_id: '', external_reference: '', conversion_value: '', referral_code: '', click_id: '' })
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const setting = (key) => settings.data?.find((s) => s.key === key)?.value
  const active = (partners.data || []).filter((p) => p.status === 'active').sort((a, b) => a.name.localeCompare(b.name))
  const partner = active.find((p) => p.id === form.partner_id)
  const tier = tiers.data?.find((t) => t.id === partner?.tier_id)
  const value = toNumber(form.conversion_value)
  const preview = useMemo(() => {
    if (!partner) return null
    if (tier && tier.commission_type !== 'tier_based') {
      return { label: `${tier.name} · ${rateLabel(tier.commission_type, tier.commission_value)}`, amount: commissionFor(tier.commission_type, toNumber(tier.commission_value), value) }
    }
    if (tier) return { label: `${tier.name} · ${rateLabel('percentage', tier.commission_value)}`, amount: commissionFor('percentage', toNumber(tier.commission_value), value) }
    const type = setting('commission.default_type')
    const rate = type === 'fixed' ? toNumber(setting('commission.default_fixed_amount')) : toNumber(setting('commission.default_percentage'))
    return { label: `Default · ${rateLabel(type, rate)}`, amount: commissionFor(type, rate, value) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partner, tier, value, settings.data])

  const valueProblem = form.conversion_value && (value === null || value <= 0 || !/^\d+(\.\d{1,2})?$/.test(form.conversion_value.trim()))
  const clickProblem = form.click_id && !UUID.test(form.click_id.trim())
  const canSubmit = partner && form.external_reference.trim() && value > 0 && !valueProblem && !clickProblem

  async function submit(e) {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const conv = await adminApi.recordSale({
        partner_id: partner.id,
        external_reference: form.external_reference.trim(),
        conversion_value: form.conversion_value.trim(),
        referral_code: form.referral_code.trim() || null,
        click_id: form.click_id.trim() || null,
      })
      const rows = await adminApi.partnerConversions(partner.id, { limit: 5 }).catch(() => [])
      const row = rows.find((r) => r.id === conv.id)
      setDone({ partner: partner.name, partnerId: partner.id, order: conv.external_reference, commission: row?.commission_amount, attributed: conv.click_id !== null || conv.referral_code_id !== null })
      setForm((f) => ({ ...f, external_reference: '', conversion_value: '', referral_code: '', click_id: '' }))
      for (const key of ['partners', 'admin-dashboard', 'commissions', 'partner']) qc.invalidateQueries({ queryKey: [key] })
    } catch (err) {
      setError(
        err.response?.status === 409 && /already/i.test(err.response?.data?.detail || '')
          ? 'This order ID was already recorded for this partner.'
          : errorMessage(err),
      )
    } finally {
      setBusy(false)
    }
  }

  const model = setting('referral.attribution_model') === 'first_click' ? 'first click' : 'last click'
  const windowDays = setting('referral.attribution_window_days') ?? 30

  return (
    <>
      <PageHeader title="Record a sale" description="Use this to record a sale manually. Your shop can also send sales to the API." />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel>
          <PanelBody>
            <form onSubmit={submit} className="space-y-4" noValidate>
              {done && (
                <Alert variant="success">
                  Sale recorded. {done.commission ? `Commission ${money(done.commission)} credited to ${done.partner}.` : `Credited to ${done.partner}.`}{' '}
                  {done.attributed ? 'Linked to their referral.' : 'No matching click in the window, so it isn’t linked to a click.'} The quality score
                  appears in a few seconds.{' '}
                  <Link to={`/admin/partners/${done.partnerId}`} className="font-semibold underline">
                    View partner
                  </Link>
                </Alert>
              )}
              {error && <Alert variant="error">{error}</Alert>}
              <Field label="Partner" helper={partners.data && !active.length ? 'There are no active partners.' : 'Only active partners can be credited.'}>
                {(p) => (
                  <Select {...p} value={form.partner_id} onChange={set('partner_id')} disabled={partners.isLoading}>
                    <option value="">{partners.isLoading ? 'Loading partners…' : 'Choose a partner…'}</option>
                    {active.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name} · {x.email}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Order ID" helper="Your shop's order number. Must be unique for this partner.">
                  {(p) => <Input {...p} value={form.external_reference} onChange={set('external_reference')} placeholder="demo-order-2042" maxLength={255} />}
                </Field>
                <Field label="Order value ($)" error={valueProblem ? 'Enter an amount above 0 with at most two decimals.' : null}>
                  {(p) => <Input {...p} inputMode="decimal" value={form.conversion_value} onChange={set('conversion_value')} placeholder="200.00" />}
                </Field>
              </div>
              <Field label="Referral code (optional)" helper="If the customer used a partner code at checkout. It must belong to this partner.">
                {(p) => <Input {...p} value={form.referral_code} onChange={(e) => setForm((f) => ({ ...f, referral_code: e.target.value.toUpperCase() }))} placeholder="K7Q2X9PA" />}
              </Field>
              <div>
                <button
                  type="button"
                  onClick={() => setAdvanced((v) => !v)}
                  className="inline-flex items-center gap-1 text-caption font-medium text-muted-text hover:text-ink"
                  aria-expanded={advanced}
                >
                  <ChevronDown className={`size-4 transition-transform ${advanced ? 'rotate-180' : ''}`} aria-hidden />
                  Advanced
                </button>
              </div>
              {advanced && (
                <Field label="Click ID (optional)" helper="Credit a specific tracked click instead of using the attribution rule." error={clickProblem ? 'A click ID looks like 3f2b…-…; copy it exactly.' : null}>
                  {(p) => <Input {...p} value={form.click_id} onChange={set('click_id')} placeholder="00000000-0000-0000-0000-000000000000" />}
                </Field>
              )}
              <Button type="submit" className="w-full sm:w-auto" disabled={!canSubmit || busy}>
                {busy ? <Spinner /> : <CirclePlus />}
                Record sale
              </Button>
            </form>
          </PanelBody>
        </Panel>

        <Panel className="lg:sticky lg:top-20">
          <PanelHeader title="Preview" description="Calculated with the current settings." />
          <PanelBody className="space-y-4">
            <div className="rounded-[8px] border border-line p-4">
              <div className="text-caption text-muted-text">Commission</div>
              <div className="tabular mt-1 text-[28px] leading-9 font-semibold text-jade">
                {preview?.amount !== null && preview?.amount !== undefined ? money(preview.amount) : '—'}
              </div>
              <div className="mt-1 text-caption text-muted-text">{preview ? preview.label : 'Choose a partner to see their rate.'}</div>
            </div>
            <div className="rounded-[8px] border border-line p-4">
              <div className="text-caption text-muted-text">Attribution</div>
              <div className="mt-1 text-body font-medium text-text">
                {form.click_id ? 'The click ID you entered' : form.referral_code ? `Code ${form.referral_code}, else ${model}` : `${model.charAt(0).toUpperCase() + model.slice(1)} within ${windowDays} days`}
              </div>
              <div className="mt-1 text-caption text-muted-text">Clicks already used by another sale aren&apos;t reused.</div>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </>
  )
}
