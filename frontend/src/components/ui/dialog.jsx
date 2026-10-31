// Dialog (Radix) styled to DESIGN.md: centred, 10px radius, clear title, one
// sentence of consequences, matching action button. Only one dialog at a time.
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

export function DialogContent({ className, children, title, description, wide = false, hideClose = false }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#0c141a]/55 data-[state=open]:animate-[fade-in_120ms_ease-out]" />
      <DialogPrimitive.Content
        className={cn(
          'fixed top-1/2 left-1/2 z-50 max-h-[calc(100dvh-32px)] w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto',
          'rounded-[10px] border border-line bg-surface p-6 shadow-xl focus:outline-none',
          wide ? 'max-w-[560px]' : 'max-w-[440px]',
          className,
        )}
      >
        <div className="mb-4 pr-8">
          <DialogPrimitive.Title className="text-section font-semibold text-ink">{title}</DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-1 text-caption text-muted-text">{description}</DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
          )}
        </div>
        {children}
        {!hideClose && (
          <DialogPrimitive.Close
            className="absolute top-5 right-5 rounded-[6px] p-1 text-muted-text hover:bg-canvas hover:text-ink"
            aria-label="Close"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function DialogFooter({ className, children }) {
  return <div className={cn('mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)}>{children}</div>
}
