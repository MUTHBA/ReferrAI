// -----------------------------------------------------------------------------
// frontend/src/lib/utils.js
//
// cn(): merge Tailwind class names, letting later classes win over earlier
// conflicting ones (the standard shadcn/ui helper).
// -----------------------------------------------------------------------------

import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
