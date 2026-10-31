// -----------------------------------------------------------------------------
// frontend/src/components/app/AppShell.jsx
//
// Signed-in layout for both roles: a full-height ink sidebar (248px) on
// desktop, a top bar with a slide-in menu on mobile, a slim top bar with the
// breadcrumb and theme toggle, and the page content (max 1280px wide).
// Admin menu items can show live counts (open fraud alerts, payouts waiting).
// -----------------------------------------------------------------------------

import * as DialogPrimitive from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { LogOut, Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { ThemeToggle } from '@/components/brand/ThemeToggle'
import { Wordmark } from '@/components/brand/Wordmark'
import { useAuth } from '@/context/AuthContext'
import { adminApi, partnerApi } from '@/lib/endpoints'
import { initials } from '@/lib/format'
import { cn } from '@/lib/utils'

import { ADMIN_NAV, PARTNER_NAV } from './nav'

function useBadgeCounts(enabled) {
  const fraud = useQuery({
    queryKey: ['fraud-flags', 'pending_review'],
    queryFn: () => adminApi.fraudFlags('pending_review'),
    enabled,
    refetchInterval: 60_000,
  })
  const payouts = useQuery({
    queryKey: ['withdrawals', { status: 'pending' }],
    queryFn: () => adminApi.withdrawals({ status: 'pending' }),
    enabled,
    refetchInterval: 60_000,
  })
  return { fraud: fraud.data?.length || 0, payouts: payouts.data?.length || 0 }
}

function currentPage(nav, pathname) {
  let best = null
  for (const group of nav) {
    for (const item of group.items) {
      const match = item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)
      if (match && (!best || item.to.length > best.item.to.length)) best = { item, section: group.section }
    }
  }
  return best
}

function SidebarContent({ nav, counts, user, displayName, onNavigate, onSignOut }) {
  const isAdmin = user?.role === 'admin'
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-5 pb-4">
        <Link to={isAdmin ? '/admin' : '/partner'} onClick={onNavigate} className="block w-fit">
          <Wordmark inverted />
          <span className="mt-0.5 block text-caption text-white/55">{isAdmin ? 'Admin' : 'Partner'}</span>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main">
        {nav.map((group, gi) => (
          <div key={group.section || gi} className={cn(gi > 0 && 'mt-5')}>
            {group.section && <div className="px-3 pb-1.5 text-label font-medium text-white/45">{group.section}</div>}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon
                const count = item.badge ? counts[item.badge] : 0
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          'relative flex h-9 items-center gap-3 rounded-[6px] px-3 text-body whitespace-nowrap transition-colors duration-150',
                          isActive ? 'bg-white/10 font-semibold text-white' : 'text-white/70 hover:bg-white/5 hover:text-white',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && <span className="absolute top-1.5 bottom-1.5 left-0 w-[3px] rounded-full bg-jade-bright" aria-hidden />}
                          <Icon className="size-4 shrink-0" aria-hidden />
                          <span className="truncate">{item.label}</span>
                          {count > 0 && (
                            <span
                              className={cn(
                                'tabular ml-auto rounded-full px-1.5 text-label leading-5 font-semibold',
                                item.badge === 'fraud' ? 'bg-rose text-white' : 'bg-amber text-white',
                              )}
                              aria-label={`${count} waiting`}
                            >
                              {count}
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-4 py-4">
        <div className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white/10 text-label font-semibold text-white">
            {initials(displayName)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-caption font-semibold text-white">{displayName}</div>
            <div className="truncate text-label text-white/55">{user?.email}</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onSignOut}
          className="mt-3 flex h-8 w-full items-center gap-2 rounded-[6px] px-2 text-caption text-white/70 transition-colors hover:bg-white/5 hover:text-white"
        >
          <LogOut className="size-4" aria-hidden />
          Sign out
        </button>
      </div>
    </div>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const isAdmin = user?.role === 'admin'
  const nav = isAdmin ? ADMIN_NAV : PARTNER_NAV
  const counts = useBadgeCounts(isAdmin)

  const profile = useQuery({ queryKey: ['me', 'partner'], queryFn: partnerApi.profile, enabled: !isAdmin })
  const displayName = isAdmin ? 'Admin' : profile.data?.name || user?.email?.split('@')[0] || 'Partner'

  const page = currentPage(nav, pathname)
  const crumbRoot = isAdmin ? page?.section || 'Admin' : 'Partner'

  useEffect(() => {
    const title = page?.item.label
    document.title = title ? `${title} · ReferrAI` : 'ReferrAI'
  }, [page])

  function signOut() {
    logout()
    navigate('/login', { replace: true })
  }

  const sidebarProps = { nav, counts, user, displayName, onSignOut: signOut }

  return (
    <div className="min-h-dvh bg-canvas lg:flex">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-[248px] shrink-0 bg-ink-panel lg:block dark:border-r dark:border-line">
        <SidebarContent {...sidebarProps} />
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <DialogPrimitive.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <DialogPrimitive.Trigger
              className="-ml-1 rounded-[6px] p-2 text-ink hover:bg-canvas lg:hidden"
              aria-label="Open menu"
            >
              <Menu className="size-5" />
            </DialogPrimitive.Trigger>
            <DialogPrimitive.Portal>
              <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#0c141a]/55 lg:hidden" />
              <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 w-[280px] max-w-[85vw] bg-ink-panel focus:outline-none lg:hidden">
                <DialogPrimitive.Title className="sr-only">Menu</DialogPrimitive.Title>
                <DialogPrimitive.Description className="sr-only">Main navigation</DialogPrimitive.Description>
                <DialogPrimitive.Close
                  className="absolute top-4 right-3 rounded-[6px] p-1.5 text-white/70 hover:bg-white/10 hover:text-white"
                  aria-label="Close menu"
                >
                  <X className="size-5" />
                </DialogPrimitive.Close>
                <SidebarContent {...sidebarProps} onNavigate={() => setMenuOpen(false)} />
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          </DialogPrimitive.Root>

          <nav aria-label="Breadcrumb" className="min-w-0 flex-1 truncate text-caption text-muted-text">
            <span>{crumbRoot}</span>
            {page && (
              <>
                <span className="mx-1.5" aria-hidden>
                  /
                </span>
                <span className="font-medium text-ink">{page.item.label}</span>
              </>
            )}
          </nav>
          <ThemeToggle />
        </header>

        <main className="mx-auto w-full max-w-[1344px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
