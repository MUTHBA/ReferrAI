// Segmented control / tabs: a row of options with one selected. Each option
// can carry a count shown in a separate pill (never overlapping the label).
import { cn } from '@/lib/utils'

export function Segmented({ options, value, onChange, className, size = 'default', label }) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn('inline-flex max-w-full flex-wrap gap-1 rounded-[8px] border border-line bg-surface p-1', className)}
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={String(o.value)}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex items-center gap-2 whitespace-nowrap rounded-[6px] font-medium transition-colors duration-150',
              size === 'sm' ? 'h-7 px-2.5 text-label' : 'h-8 px-3 text-caption',
              active ? 'bg-ink text-surface' : 'text-muted-text hover:bg-canvas hover:text-ink',
            )}
          >
            {o.label}
            {o.count !== undefined && o.count !== null && (
              <span
                className={cn(
                  'tabular rounded-full px-1.5 text-label leading-4',
                  active ? 'bg-surface/20 text-surface' : 'bg-muted text-muted-text',
                )}
              >
                {o.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
