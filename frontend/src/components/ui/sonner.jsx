// Toast host (sonner), bottom-right, themed with the ReferrAI tokens.
import { Toaster as Sonner } from 'sonner'

import { useTheme } from '@/providers/theme-provider'

export function Toaster() {
  const { theme } = useTheme()
  return (
    <Sonner
      theme={theme}
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: 'rounded-[10px] border border-line bg-surface text-text font-sans text-caption shadow-lg',
          description: 'text-muted-text',
        },
      }}
    />
  )
}
