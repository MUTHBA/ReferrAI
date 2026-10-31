// -----------------------------------------------------------------------------
// The "ledger strip": key figures in ONE bordered band split into cells by
// dividers (label above, large tabular number, small context line). Cells wrap
// to a 2-column grid on small screens; numbers never overflow their cell.
// -----------------------------------------------------------------------------

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const TONE = {
  default: 'text-ink',
  jade: 'text-jade',
  amber: 'text-amber',
  rose: 'text-rose',
  cobalt: 'text-cobalt',
}

const COLS = {
  2: 'sm:grid-cols-2',
  3: 'sm:grid-cols-3',
  4: 'sm:grid-cols-2 xl:grid-cols-4',
  5: 'sm:grid-cols-3 xl:grid-cols-5',
  6: 'sm:grid-cols-3 xl:grid-cols-6',
}

export function LedgerStrip({ items, loading, className }) {
  return (
    <div
      className={cn(
        'mb-6 grid grid-cols-2 overflow-hidden rounded-[10px] border border-line bg-surface',
        COLS[items.length] || 'sm:grid-cols-4',
        className,
      )}
    >
      {items.map((item, i) => (
        <div
          key={item.label}
          className={cn(
            // 1px dividers: right and bottom edges, trimmed by the outer border.
            '-mr-px -mb-px min-w-0 border-r border-b border-line px-5 py-4',
            items.length % 2 === 1 && i === items.length - 1 && 'col-span-2 sm:col-span-1',
          )}
        >
          <div className="truncate text-caption text-muted-text">{item.label}</div>
          {loading ? (
            <Skeleton className="mt-2 h-8 w-28" />
          ) : (
            <div
              className={cn(
                'tabular mt-1 truncate text-[20px] leading-7 font-semibold tracking-tight sm:text-[24px] sm:leading-8 xl:text-[28px] xl:leading-9',
                TONE[item.tone || 'default'],
              )}
              title={typeof item.value === 'string' ? item.value : undefined}
            >
              {item.value}
            </div>
          )}
          {item.context && <div className="mt-1 truncate text-label text-muted-text">{item.context}</div>}
        </div>
      ))}
    </div>
  )
}
