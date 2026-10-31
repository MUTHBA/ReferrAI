// Inline spinning loader icon (shadcn-style primitive, new in the overhaul).

import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export function Spinner({ className }) {
  return <Loader2 className={cn('size-4 animate-spin', className)} aria-hidden />
}
