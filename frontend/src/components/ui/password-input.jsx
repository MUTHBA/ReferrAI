// Password field with a Show/Hide toggle (text button, as in the Stitch design).
import { forwardRef, useState } from 'react'

import { Input } from './input'

const PasswordInput = forwardRef(function PasswordInput(props, ref) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <Input ref={ref} type={visible ? 'text' : 'password'} className="pr-16" {...props} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute top-1/2 right-2 -translate-y-1/2 rounded px-1.5 py-0.5 text-caption text-muted-text hover:text-ink"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? 'Hide' : 'Show'}
      </button>
    </div>
  )
})

export { PasswordInput }
