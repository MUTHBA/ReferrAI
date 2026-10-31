// -----------------------------------------------------------------------------
// AI score badge (0-100). Quality/rank/potential scores use a cobalt outline;
// risk scores (fraud, churn) are coloured by risk: under 40 grey, 40-70 amber,
// over 70 rose. Missing scores are shown as words, never as 0:
//   model_unavailable -> "Not trained yet", insufficient_data -> "Not enough
//   history", error -> "Scoring failed", nothing yet -> "Scoring…" / "No score".
// -----------------------------------------------------------------------------

import { cn } from '@/lib/utils'

const MISSING = {
  model_unavailable: 'Not trained yet',
  insufficient_data: 'Not enough history',
  error: 'Scoring failed',
}

export function riskTone(score) {
  if (score === null || score === undefined) return 'grey'
  if (score > 70) return 'rose'
  if (score >= 40) return 'amber'
  return 'grey'
}

export function ScoreBadge({ score, status, risk = false, pendingLabel = 'No score yet', outOf = false, className }) {
  if (score === null || score === undefined) {
    const text = (status && MISSING[status]) || pendingLabel
    return <span className={cn('text-caption whitespace-nowrap text-muted-text italic', className)}>{text}</span>
  }
  const value = Math.round(Number(score))
  const tone = risk ? riskTone(value) : 'cobalt'
  const styles = {
    cobalt: 'border-cobalt/60 text-cobalt',
    grey: 'border-line text-muted-text',
    amber: 'border-amber/60 bg-amber-soft text-amber',
    rose: 'border-rose/60 bg-rose-soft text-rose',
  }
  return (
    <span
      className={cn(
        'tabular inline-flex h-6 min-w-9 items-center justify-center rounded-full border px-2 text-label font-semibold whitespace-nowrap',
        styles[tone],
        className,
      )}
    >
      {value}
      {outOf && <span className="font-normal opacity-70">/100</span>}
    </span>
  )
}
