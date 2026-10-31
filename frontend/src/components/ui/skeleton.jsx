// Pulsing placeholder block for loading states (shadcn-style primitive, new in the overhaul).

import { cn } from '@/lib/utils'

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-[6px] bg-muted', className)} aria-hidden />
}
