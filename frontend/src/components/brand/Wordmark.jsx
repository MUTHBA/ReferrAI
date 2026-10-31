// ReferrAI wordmark: "Referr" + "AI" in the bright jade accent.
import { cn } from '@/lib/utils'

export function Wordmark({ className, inverted = false }) {
  return (
    <span className={cn('select-none text-section font-semibold tracking-tight', inverted ? 'text-white' : 'text-ink', className)}>
      Referr<span className={inverted ? 'text-jade-bright' : 'text-jade'}>AI</span>
    </span>
  )
}
