// shadcn/ui Input, restyled: 36px tall, 1px line border, ink border on focus.
import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

const Input = forwardRef(function Input({ className, type = 'text', invalid, ...props }, ref) {
  return (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      className={cn(
        'h-9 w-full rounded-[6px] border border-line bg-surface px-3 text-body text-text placeholder:text-muted-text/70',
        'transition-colors duration-150 focus:border-ink focus:outline-none focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-60',
        'aria-[invalid=true]:border-rose',
        className,
      )}
      {...props}
    />
  )
})

export { Input }
