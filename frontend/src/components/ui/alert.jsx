// Inline message box: error (rose), success (jade), info (cobalt), warning (amber).
import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react'

import { cn } from '@/lib/utils'

const STYLES = {
  error: { box: 'border-rose bg-rose-soft text-text', icon: AlertCircle, iconClass: 'text-rose' },
  success: { box: 'border-jade/40 bg-jade-soft text-text', icon: CheckCircle2, iconClass: 'text-jade' },
  info: { box: 'border-cobalt/40 bg-cobalt-soft text-text', icon: Info, iconClass: 'text-cobalt' },
  warning: { box: 'border-amber/50 bg-amber-soft text-text', icon: TriangleAlert, iconClass: 'text-amber' },
}

export function Alert({ variant = 'info', className, children, ...props }) {
  const s = STYLES[variant]
  const Icon = s.icon
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-[6px] border p-3 text-caption', s.box, className)}
      {...props}
    >
      <Icon className={cn('mt-px size-4 shrink-0', s.iconClass)} aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
