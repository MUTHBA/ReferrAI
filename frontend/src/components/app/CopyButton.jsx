// Copy-to-clipboard icon button with a toast confirmation (new in the frontend overhaul).

import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'

export function CopyButton({ text, label = 'Copy', size = 'sm', variant = 'ghost', iconOnly = false }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy. Select the text and copy it manually.')
    }
  }
  return (
    <Button variant={variant} size={iconOnly ? 'icon' : size} onClick={copy} aria-label={`${label} ${text}`} title={label}>
      {copied ? <Check className="text-jade" /> : <Copy />}
      {!iconOnly && (copied ? 'Copied' : label)}
    </Button>
  )
}
