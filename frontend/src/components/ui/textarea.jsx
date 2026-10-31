// Styled multi-line text input (shadcn-style primitive, new in the overhaul).

import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

const Textarea = forwardRef(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'min-h-20 w-full rounded-[6px] border border-line bg-surface px-3 py-2 text-body text-text placeholder:text-muted-text/70',
        'transition-colors duration-150 focus:border-ink focus:outline-none aria-[invalid=true]:border-rose',
        className,
      )}
      {...props}
    />
  )
})

export { Textarea }
