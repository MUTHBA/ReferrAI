// Bordered surface panel (10px radius, no shadow) with an optional header row.
import { cn } from '@/lib/utils'

export function Panel({ className, children, ...props }) {
  return (
    <section className={cn('min-w-0 rounded-[10px] border border-line bg-surface', className)} {...props}>
      {children}
    </section>
  )
}

export function PanelHeader({ title, description, actions, className, children }) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4', className)}>
      <div className="min-w-0">
        <h2 className="text-section font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-caption text-muted-text">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function PanelBody({ className, children }) {
  return <div className={cn('p-5', className)}>{children}</div>
}
