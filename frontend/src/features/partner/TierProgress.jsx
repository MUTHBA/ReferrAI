// -----------------------------------------------------------------------------
// Tier progress: current tier and rate, a bar towards the next tier, and what
// is still needed. Upgrades need BOTH targets (sales and revenue) and apply to
// future sales only. `tier` is the TierProgress object from the dashboard API.
// -----------------------------------------------------------------------------

import { Flag } from 'lucide-react'

import { Pill } from '@/components/ui/pill'
import { money, number, toNumber } from '@/lib/format'

export function needsText(tier) {
  const sales = tier.referrals_needed || 0
  const revenue = toNumber(tier.revenue_needed) || 0
  const parts = []
  if (sales > 0) parts.push(`${number(sales)} more ${sales === 1 ? 'sale' : 'sales'}`)
  if (revenue > 0) parts.push(`${money(revenue)} more revenue`)
  if (!parts.length) return `You've met both targets for ${tier.next_tier}; it applies from your next sale.`
  return `${parts.join(' and ')} to reach ${tier.next_tier}`
}

export function TierProgress({ tier, compact = false }) {
  if (!tier?.current_tier) {
    return <p className="text-caption text-muted-text">No tier assigned yet.</p>
  }
  const pct = Math.round((tier.progress ?? 0) * 100)
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-semibold text-ink">{tier.current_tier}</span>
        <Pill tone="jade">{tier.current_rate_label} commission</Pill>
      </div>
      {tier.next_tier ? (
        <>
          <div className="mt-4 flex items-center justify-between text-label text-muted-text">
            <span>Progress to {tier.next_tier}</span>
            <span className="tabular">{pct}%</span>
          </div>
          <div
            className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Progress to ${tier.next_tier}`}
          >
            <div className="h-full rounded-full bg-jade" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-3 flex gap-2 text-caption text-text">
            <Flag className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden />
            <span>
              {needsText(tier)}
              {tier.next_rate_label && <span className="text-muted-text"> ({tier.next_rate_label} commission)</span>}
            </span>
          </p>
          {!compact && (
            <p className="mt-3 text-label text-muted-text">
              Upgrades happen automatically when you reach both targets, and apply to future sales.
            </p>
          )}
        </>
      ) : (
        <p className="mt-3 text-caption text-muted-text">You&apos;re on the top tier.</p>
      )}
    </div>
  )
}
