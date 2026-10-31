// 404: simple and calm — where to go next.
import { Link } from 'react-router-dom'

import { Wordmark } from '@/components/brand/Wordmark'
import { Button } from '@/components/ui/button'
import { homePathFor, useAuth } from '@/context/AuthContext'

export default function NotFoundPage() {
  const { user } = useAuth()
  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <header className="px-4 py-4 sm:px-8">
        <Link to="/" className="w-fit">
          <Wordmark />
        </Link>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-12 pb-16 sm:items-center sm:pt-0">
        <section className="w-full max-w-[440px] rounded-[10px] border border-line bg-surface px-6 py-10 text-center sm:px-10">
          <p className="tabular text-[64px] leading-none font-semibold tracking-tight text-ink">404</p>
          <h1 className="mt-4 text-section font-semibold text-ink">Page not found</h1>
          <p className="mt-1 text-caption text-muted-text">This page doesn&apos;t exist or you don&apos;t have access to it.</p>
          <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
            <Button asChild>
              <Link to={homePathFor(user)}>{user ? 'Go to dashboard' : 'Go to sign in'}</Link>
            </Button>
          </div>
        </section>
      </main>
    </div>
  )
}
