// A group of bordered radio options (e.g. attribution model, commission type).
import { cn } from '@/lib/utils'

export function RadioCards({ name, options, value, onChange, className, columns = 1 }) {
  return (
    <div
      role="radiogroup"
      className={cn('grid gap-2', columns === 2 && 'sm:grid-cols-2', className)}
    >
      {options.map((o) => {
        const checked = o.value === value
        return (
          <label
            key={o.value}
            className={cn(
              'flex cursor-pointer items-start gap-3 rounded-[6px] border p-3 transition-colors duration-150',
              checked ? 'border-jade bg-jade-soft/50' : 'border-line hover:bg-canvas',
            )}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={checked}
              onChange={() => onChange(o.value)}
              className="mt-0.5 size-4 accent-[var(--jade)]"
            />
            <span className="min-w-0">
              <span className="block text-body font-medium text-text">{o.label}</span>
              {o.description && <span className="mt-0.5 block text-caption text-muted-text">{o.description}</span>}
            </span>
          </label>
        )
      })}
    </div>
  )
}
