// -----------------------------------------------------------------------------
// Settings: the business rules that live in the database (not in code).
// Each group saves on its own; the server validates every value (range, type)
// and records each change in the audit log. Percentages are shown as % but
// stored as fractions (10% = 0.10).
// -----------------------------------------------------------------------------

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { PageHeader } from '@/components/app/PageHeader'
import { ErrorState, LoadingRows } from '@/components/app/States'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Panel } from '@/components/ui/panel'
import { RadioCards } from '@/components/ui/radio-cards'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { adminApi } from '@/lib/endpoints'
import { toNumber } from '@/lib/format'

const WEIGHT_KEYS = [
  ['quality', 'Quality'],
  ['churn', 'Churn resistance'],
  ['volume', 'Volume'],
  ['revenue', 'Revenue'],
]

const GROUPS = [
  {
    title: 'Commission',
    description: 'Used when a partner has no tier, or their tier gives no rate.',
    fields: [
      {
        key: 'commission.default_type',
        label: 'Commission type',
        type: 'choice',
        options: [
          { value: 'percentage', label: 'Percentage', description: 'A share of each order value.' },
          { value: 'fixed', label: 'Fixed', description: 'The same amount for every sale.' },
        ],
      },
      { key: 'commission.default_percentage', label: 'Default rate', type: 'percent', showIf: (v) => v['commission.default_type'] !== 'fixed' },
      { key: 'commission.default_fixed_amount', label: 'Fixed amount', type: 'money', showIf: (v) => v['commission.default_type'] === 'fixed' },
    ],
  },
  {
    title: 'Wallet',
    description: 'Withdrawal limits and automatic approval.',
    fields: [
      { key: 'wallet.min_withdrawal_amount', label: 'Minimum withdrawal', type: 'money' },
      { key: 'wallet.auto_approval_threshold', label: 'Auto-approve withdrawals under', type: 'money', help: 'Also caps the total auto-approved per partner in 24 hours. Partners with an open fraud alert always need review.' },
    ],
  },
  {
    title: 'Referrals',
    description: 'Which click gets credit for a sale.',
    fields: [
      {
        key: 'referral.attribution_model',
        label: 'Attribution model',
        type: 'choice',
        options: [
          { value: 'last_click', label: 'Last click', description: 'Credit the partner whose link was clicked most recently.' },
          { value: 'first_click', label: 'First click', description: 'Credit the partner who first introduced the customer.' },
        ],
      },
      { key: 'referral.attribution_window_days', label: 'Attribution window', type: 'int', suffix: 'days' },
    ],
  },
  {
    title: 'Fraud',
    description: 'When a fraud alert is raised. Alerts go to review; nobody is suspended automatically.',
    fields: [
      { key: 'fraud.alert_threshold', label: 'Alert threshold', type: 'number', suffix: 'of 100', help: 'Raise an alert when the fraud score is above this.' },
      { key: 'fraud.rule_weight', label: 'Rule weight', type: 'number', suffix: 'points', help: 'Points added to the score for each rule triggered.' },
      { key: 'fraud.max_clicks_per_hour', label: 'Max clicks per IP per hour', type: 'int' },
      { key: 'fraud.max_device_partner_spread', label: 'Max partners per device (24h)', type: 'int' },
    ],
  },
  {
    title: 'Churn',
    description: 'Who shows as at risk of leaving.',
    fields: [{ key: 'churn.alert_threshold', label: 'Alert threshold', type: 'number', suffix: 'of 100', help: 'Partners with a churn score above this are flagged.' }],
  },
  {
    title: 'Ranking weights',
    description: "Weights are relative; they don't need to add up to 1.",
    fields: [{ key: 'ranking.weights', type: 'weights' }],
  },
  {
    title: 'AI',
    description: 'How often churn and ranking scores are recalculated.',
    fields: [{ key: 'ai.batch_scoring_interval_hours', label: 'Scoring interval', type: 'int', suffix: 'hours', help: '0 turns automatic scoring off.' }],
  },
]

// Value from the API -> what's shown in the input.
function toInput(type, value) {
  if (value === null || value === undefined) return ''
  if (type === 'percent') return String(Math.round(Number(value) * 10000) / 100)
  if (type === 'weights') return Object.fromEntries(WEIGHT_KEYS.map(([k]) => [k, String(value[k] ?? '')]))
  return String(value)
}

// Input -> value sent to the API (or an error message).
function fromInput(type, raw) {
  if (type === 'choice') return { value: raw }
  if (type === 'weights') {
    const out = {}
    for (const [k, label] of WEIGHT_KEYS) {
      const n = toNumber(raw[k])
      if (n === null || n < 0) return { error: `${label}: enter a number of 0 or more.` }
      out[k] = n
    }
    if (!Object.values(out).some((n) => n > 0)) return { error: 'At least one weight must be above 0.' }
    return { value: out }
  }
  const n = toNumber(raw)
  if (n === null) return { error: 'Enter a number.' }
  if (type === 'int' && !Number.isInteger(n)) return { error: 'Enter a whole number.' }
  if (type === 'percent') return { value: Math.round(n * 100) / 10000 }
  return { value: n }
}

function SettingGroup({ group, saved, onSaved }) {
  const initial = useMemo(
    () => Object.fromEntries(group.fields.map((f) => [f.key, toInput(f.type, saved[f.key])])),
    [group, saved],
  )
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => setValues(initial), [initial])
  const dirty = JSON.stringify(values) !== JSON.stringify(initial)
  const visible = group.fields.filter((f) => !f.showIf || f.showIf(values))

  async function save(e) {
    e.preventDefault()
    const nextErrors = {}
    const changes = []
    for (const f of group.fields) {
      if (JSON.stringify(values[f.key]) === JSON.stringify(initial[f.key])) continue
      const parsed = fromInput(f.type, values[f.key])
      if (parsed.error) nextErrors[f.key] = parsed.error
      else changes.push([f.key, parsed.value])
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return
    setBusy(true)
    setError(null)
    let current = null
    try {
      for (const [key, value] of changes) {
        current = key
        await adminApi.updateSetting(key, value)
      }
      toast.success(`${group.title} settings saved.`)
      onSaved()
    } catch (err) {
      // Server messages name the setting key; show the field's label instead.
      const field = group.fields.find((f) => f.key === current)
      setError(errorMessage(err).replace(current, field?.label || group.title))
      onSaved()
    } finally {
      setBusy(false)
    }
  }

  const setField = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }))

  return (
    <Panel>
      <form onSubmit={save} className="grid gap-5 p-5 md:grid-cols-[220px_minmax(0,1fr)] md:gap-8">
        <div>
          <h2 className="text-section font-semibold text-ink">{group.title}</h2>
          <p className="mt-1 text-caption text-muted-text">{group.description}</p>
        </div>
        <div className="min-w-0 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {visible.map((f) => {
              if (f.type === 'choice') {
                return (
                  <div key={f.key} className="sm:col-span-2">
                    <div className="mb-1.5 text-caption font-medium text-text">{f.label}</div>
                    <RadioCards
                      name={f.key}
                      columns={2}
                      options={f.options}
                      value={values[f.key]}
                      onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))}
                    />
                  </div>
                )
              }
              if (f.type === 'weights') {
                return (
                  <div key={f.key} className="grid gap-4 sm:col-span-2 sm:grid-cols-4">
                    {WEIGHT_KEYS.map(([k, label]) => (
                      <Field key={k} label={label}>
                        {(p) => (
                          <Input
                            {...p}
                            inputMode="decimal"
                            value={values[f.key][k]}
                            onChange={(e) => setValues((s) => ({ ...s, [f.key]: { ...s[f.key], [k]: e.target.value } }))}
                          />
                        )}
                      </Field>
                    ))}
                    {errors[f.key] && <p className="text-caption text-rose sm:col-span-4">{errors[f.key]}</p>}
                  </div>
                )
              }
              const prefix = f.type === 'money' ? '$' : null
              const suffix = f.type === 'percent' ? '%' : f.suffix
              return (
                <Field key={f.key} label={f.label} helper={f.help} error={errors[f.key]}>
                  {(p) => (
                    <div className="relative">
                      {prefix && <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-text">{prefix}</span>}
                      <Input
                        {...p}
                        inputMode="decimal"
                        value={values[f.key]}
                        onChange={setField(f.key)}
                        className={`${prefix ? 'pl-7' : ''} ${suffix ? 'pr-16' : ''}`}
                      />
                      {suffix && (
                        <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-caption text-muted-text">{suffix}</span>
                      )}
                    </div>
                  )}
                </Field>
              )
            })}
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          <div className="flex items-center justify-end gap-2">
            {dirty && (
              <Button type="button" variant="ghost" onClick={() => (setValues(initial), setErrors({}))}>
                Discard
              </Button>
            )}
            <Button type="submit" disabled={!dirty || busy}>
              {busy && <Spinner />}
              Save
            </Button>
          </div>
        </div>
      </form>
    </Panel>
  )
}

export default function SettingsPage() {
  const qc = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: adminApi.settings })
  const saved = useMemo(() => Object.fromEntries((settings.data || []).map((s) => [s.key, s.value])), [settings.data])

  return (
    <>
      <PageHeader title="Settings" description="Changes apply immediately and are recorded in the audit log." />
      {settings.isLoading ? (
        <Panel>
          <LoadingRows rows={8} />
        </Panel>
      ) : settings.isError ? (
        <Panel>
          <ErrorState error={settings.error} onRetry={settings.refetch} />
        </Panel>
      ) : (
        <div className="space-y-6">
          {GROUPS.map((g) => (
            <SettingGroup key={g.title} group={g} saved={saved} onSaved={() => qc.invalidateQueries({ queryKey: ['settings'] })} />
          ))}
        </div>
      )}
    </>
  )
}
