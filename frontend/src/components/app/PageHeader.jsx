// Page title (28/36) on the left, the page's actions on the right, and one line
// of muted helper text under the title only when it adds information.
import { cn } from '@/lib/utils'

export function PageHeader({ title, description, actions, className, children }) {
  return (
    <div className={cn('mb-6 flex flex-wrap items-start justify-between gap-x-4 gap-y-3', className)}>
      <div className="min-w-0">
        {children}
        <h1 className="text-title font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-caption text-muted-text">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
