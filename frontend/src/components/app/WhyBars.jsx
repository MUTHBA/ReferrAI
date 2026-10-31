// -----------------------------------------------------------------------------
// The signature "why" bars: up to three factors behind an AI score, each a
// labelled bar growing left (lowers the score) or right (raises it) from a
// centre line. Labels sit on their own line above the bar so they never
// overlap. For risk scores (`risk`) raising the score is bad, so raises are
// rose and lowers are jade; otherwise raises are jade and lowers rose.
// factors: [{ label, effect }] — effect in score points (+ raises, − lowers).
// -----------------------------------------------------------------------------

import { cn } from '@/lib/utils'

export function topFactors(contributingFactors, limit = 3) {
  const list = contributingFactors?.top_factors
  if (!Array.isArray(list)) return []
  return list.slice(0, limit).map((f) => ({ label: f.label || f.feature, effect: Number(f.effect) || 0 }))
}

export function WhyBars({ factors, risk = false, max, compact = false, className, emptyText = 'No single factor stood out.' }) {
  if (!factors?.length) return <p className={cn('text-caption text-muted-text', className)}>{emptyText}</p>
  const scale = max || Math.max(10, ...factors.map((f) => Math.abs(f.effect)))
  return (
    <ul className={cn(compact ? 'space-y-1.5' : 'space-y-2.5', className)}>
      {factors.map((f) => {
        const raises = f.effect >= 0
        const good = risk ? !raises : raises
        const width = `${Math.min(100, (Math.abs(f.effect) / scale) * 100)}%`
        return (
          <li key={f.label} className="min-w-0">
            <div className="flex items-baseline justify-between gap-3 text-label">
              <span className="min-w-0 text-text">{f.label}</span>
              <span className={cn('tabular shrink-0 font-semibold', good ? 'text-jade' : 'text-rose')}>
                {raises ? '+' : '−'}
                {Math.abs(f.effect).toFixed(0)}
              </span>
            </div>
            <div className="relative mt-1 grid h-1.5 grid-cols-2 rounded-full bg-muted" aria-hidden>
              <span className="absolute top-[-2px] bottom-[-2px] left-1/2 w-px bg-line" />
              <div className="flex justify-end">
                {!raises && <span className={cn('h-full rounded-l-full', good ? 'bg-jade' : 'bg-rose')} style={{ width }} />}
              </div>
              <div>{raises && <span className={cn('block h-full rounded-r-full', good ? 'bg-jade' : 'bg-rose')} style={{ width }} />}</div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
