// Label + control + helper/error text, with the ids wired for accessibility.
import { useId } from 'react'

import { cn } from '@/lib/utils'

import { Label } from './label'

export function Field({ label, helper, error, children, className, action }) {
  const id = useId()
  const describedBy = error ? `${id}-error` : helper ? `${id}-helper` : undefined
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between">
        <Label htmlFor={id}>{label}</Label>
        {action}
      </div>
      {children({ id, 'aria-describedby': describedBy, invalid: Boolean(error) })}
      {error ? (
        <p id={`${id}-error`} className="text-caption text-rose">
          {error}
        </p>
      ) : helper ? (
        <p id={`${id}-helper`} className="text-caption text-muted-text">
          {helper}
        </p>
      ) : null}
    </div>
  )
}
