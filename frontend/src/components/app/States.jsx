// Loading, error and empty states shared by all pages.
import { AlertCircle, Inbox } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

export function ErrorState({ error, onRetry, className }) {
  return (
    <div className={cn('flex flex-col items-center gap-3 px-6 py-10 text-center', className)} role="alert">
      <AlertCircle className="size-6 text-rose" aria-hidden />
      <p className="max-w-md text-body text-text">{errorMessage(error, 'This section could not be loaded.')}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ title, children, action, className, icon: Icon = Inbox }) {
  return (
    <div className={cn('flex flex-col items-center gap-2 px-6 py-12 text-center', className)}>
      <Icon className="size-6 text-muted-text" aria-hidden />
      {title && <p className="text-body font-semibold text-ink">{title}</p>}
      {children && <p className="max-w-md text-caption text-muted-text">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function LoadingRows({ rows = 5, className }) {
  return (
    <div className={cn('space-y-3 p-5', className)} aria-label="Loading" role="status">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-7 w-full" />
      ))}
    </div>
  )
}
