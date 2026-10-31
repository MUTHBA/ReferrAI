// shadcn/ui Label (Radix) in the ReferrAI caption style.
import * as LabelPrimitive from '@radix-ui/react-label'
import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

const Label = forwardRef(function Label({ className, ...props }, ref) {
  return (
    <LabelPrimitive.Root
      ref={ref}
      className={cn('block text-caption font-medium text-text peer-disabled:opacity-60', className)}
      {...props}
    />
  )
})

export { Label }
