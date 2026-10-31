// -----------------------------------------------------------------------------
// Confirmation dialog for consequential actions: title, one sentence of
// consequences, an optional reason/notes field, and a matching action button.
// The dialog stays open (with the error shown inside) if the action fails.
// -----------------------------------------------------------------------------

import { useState } from 'react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/api'

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive = false,
  reasonLabel,
  reasonPlaceholder,
  reasonRequired = false,
  warning,
  onConfirm,
  children,
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  function change(next) {
    if (!next) {
      setReason('')
      setError(null)
    }
    onOpenChange(next)
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm(reason.trim())
      change(false)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent title={title} description={description}>
        {children}
        {warning && (
          <Alert variant="warning" className="mb-4">
            {warning}
          </Alert>
        )}
        {reasonLabel && (
          <div className="space-y-1.5">
            <Label htmlFor="confirm-reason">{reasonLabel}</Label>
            <Textarea
              id="confirm-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder}
              rows={3}
              maxLength={500}
            />
          </div>
        )}
        {error && (
          <Alert variant="error" className="mt-4">
            {error}
          </Alert>
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={() => change(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'primary'}
            onClick={confirm}
            disabled={busy || (reasonRequired && !reason.trim())}
          >
            {busy && <Spinner />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
