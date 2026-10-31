// -----------------------------------------------------------------------------
// frontend/src/features/auth/AuthLayout.jsx
//
// Split-screen layout for sign-in, sign-up and password screens (Stitch
// "01-auth" design). Desktop: 45% ink panel with the ledger preview, 55%
// sage canvas with a 400px form panel. Mobile: a compact brand bar and the
// form first; the decorative ledger is hidden.
// -----------------------------------------------------------------------------

import { Link } from 'react-router-dom'

import { ThemeToggle } from '@/components/brand/ThemeToggle'
import { Wordmark } from '@/components/brand/Wordmark'

import { LedgerPreview } from './LedgerPreview'

export function AuthLayout({ title, description, children, footer }) {
  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <aside className="hidden flex-col justify-between bg-[#18232D] p-12 lg:flex lg:w-[45%]">
        <Link to="/login" className="w-fit">
          <Wordmark inverted />
        </Link>
        <div className="flex flex-1 items-center justify-center py-12">
          <LedgerPreview />
        </div>
        <p className="text-caption text-white/40">Referral partnerships, simplified.</p>
      </aside>

      <main className="flex flex-1 flex-col bg-canvas">
        <div className="flex items-center justify-between px-4 py-3 sm:px-6 lg:justify-end lg:px-8 lg:pt-6">
          <Link to="/login" className="lg:hidden">
            <Wordmark />
          </Link>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-start justify-center px-4 pt-6 pb-12 sm:items-center sm:px-6 sm:pt-0">
          <section className="w-full max-w-[400px] rounded-[10px] border border-line bg-surface p-6 sm:p-8">
            <header className="mb-6">
              <h1 className="text-title font-semibold tracking-tight text-ink">{title}</h1>
              {description && <p className="mt-1 text-caption text-muted-text">{description}</p>}
            </header>
            {children}
            {footer && <div className="mt-6 text-center text-caption text-muted-text">{footer}</div>}
          </section>
        </div>
      </main>
    </div>
  )
}
