// Native <select> styled like Input — accessible and reliable on mobile.
import { ChevronDown } from 'lucide-react'
import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

const Select = forwardRef(function Select({ className, invalid, children, ...props }, ref) {
  return (
    <div className={cn('relative', className)}>
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          'h-9 w-full cursor-pointer appearance-none rounded-[6px] border border-line bg-surface pr-9 pl-3 text-body text-text',
          'transition-colors duration-150 focus:border-ink focus:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-rose',
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-text" aria-hidden />
    </div>
  )
})

export { Select }
