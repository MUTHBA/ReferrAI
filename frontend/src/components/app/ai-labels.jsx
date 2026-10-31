// -----------------------------------------------------------------------------
// Shared AI display helpers: fraud rule names, the ranking breakdown bars and
// the plain-language rule pills.
// -----------------------------------------------------------------------------

import { Pill } from '@/components/ui/pill'
import { cn } from '@/lib/utils'

export const FRAUD_RULES = {
  clicks_per_hour_exceeded: 'Too many clicks from one IP in an hour',
  device_shared_across_partners: 'Same device clicked many different partners',
  self_referral: 'IP already converted for this partner (possible self-referral)',
}

export function RulePills({ rules }) {
  if (!rules?.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {rules.map((r) => (
        <Pill key={r} tone="rose" className="h-auto py-0.5 whitespace-normal">
          {FRAUD_RULES[r] || r}
        </Pill>
      ))}
    </div>
  )
}

export const RANK_COMPONENTS = [
  { key: 'quality', label: 'Quality' },
  { key: 'churn', label: 'Churn resistance' },
  { key: 'volume', label: 'Volume' },
  { key: 'revenue', label: 'Revenue' },
]

/** Four 0–100 bars for the ranking components, with each weight. */
export function RankBreakdown({ factors, compact = false, className }) {
  const components = factors?.components
  if (!components) return <p className={cn('text-caption text-muted-text', className)}>Not ranked yet.</p>
  const weights = factors.weights || {}
  const total = RANK_COMPONENTS.reduce((a, c) => a + (Number(weights[c.key]) || 0), 0) || 1
  const neutral = new Set(factors.neutral_defaults || [])
  return (
    <ul className={cn(compact ? 'space-y-1.5' : 'space-y-2.5', className)}>
      {RANK_COMPONENTS.map((c) => {
        const value = Math.round(Number(components[c.key]) || 0)
        const share = Math.round(((Number(weights[c.key]) || 0) / total) * 100)
        return (
          <li key={c.key}>
            <div className="flex items-baseline justify-between gap-3 text-label">
              <span className="text-text">
                {c.label} <span className="text-muted-text">· {share}%</span>
              </span>
              <span className="tabular font-semibold text-ink">{neutral.has(c.key) ? '50*' : value}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-muted" aria-hidden>
              <div className={cn('h-full rounded-full', neutral.has(c.key) ? 'bg-muted-text/40' : 'bg-cobalt')} style={{ width: `${value}%` }} />
            </div>
          </li>
        )
      })}
      {neutral.size > 0 && !compact && (
        <li className="text-label text-muted-text">* No score yet, counted as a neutral 50.</li>
      )}
    </ul>
  )
}
