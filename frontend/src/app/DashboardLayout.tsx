import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  ShieldCheck,
  X,
} from 'lucide-react'

import { useAuth } from '@/auth/AuthContext'
import { Tooltip, cn } from '@/components/ui'
import { AssistantWidget } from '@/features/assistant/AssistantWidget'
import { useRunningCount } from '@/scan/scanStore'

import { useBackendHealth } from './useBackendHealth'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/dashboard/scan', label: 'New scan', icon: Radar, end: false },
]

const HEALTH_COPY = {
  checking: { dot: 'bg-text-tertiary', label: 'Checking engine' },
  online: { dot: 'bg-status-success', label: 'Engine online' },
  offline: { dot: 'bg-status-danger', label: 'Engine offline' },
} as const

export function DashboardLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const health = useBackendHealth()
  const running = useRunningCount()
  const [menuOpen, setMenuOpen] = useState(false)
  // Persisted, because a sidebar that springs back open on every navigation is not a preference.
  // Reading localStorage can throw in a locked-down browser, so a failure just means expanded.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('mcie.sidebar') === 'collapsed'
    } catch {
      return false
    }
  })

  // The next value is computed here rather than inside the state updater. React may invoke an
  // updater more than once, and a localStorage write in there ran twice and left the stored
  // preference disagreeing with the rendered width.
  function toggleCollapsed() {
    const next = !collapsed
    setCollapsed(next)
    try {
      localStorage.setItem('mcie.sidebar', next ? 'collapsed' : 'expanded')
    } catch {
      // A preference that cannot be saved is still a preference for this session.
    }
  }

  function signOut() {
    logout()
    navigate('/', { replace: true })
  }

  // `rail` is the collapsed desktop sidebar. The mobile drawer is always full width, because a
  // 64px rail behind a hamburger would be two ways of saying the same thing.
  const sidebarInner = (rail: boolean) => (
    <div className="flex h-full flex-col">
      <div className={cn('flex h-14 items-center border-b border-surface-border', rail ? 'justify-center px-2' : 'gap-2 px-4')}>
        <ShieldCheck className="h-5 w-5 shrink-0 text-accent" />
        {!rail && <span className="text-body font-semibold text-text-primary">MCIE</span>}
        {!rail && (
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label="Collapse sidebar"
            className="ml-auto hidden rounded p-1 text-text-tertiary transition-colors hover:bg-surface-hover hover:text-text-primary md:block"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {rail && (
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label="Expand sidebar"
          className="mx-auto mt-2 rounded p-1.5 text-text-tertiary transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
      )}

      <nav className={cn('flex-1 space-y-1', rail ? 'p-2' : 'p-3')}>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded border-l-[3px] py-2 text-body-sm transition-colors',
                rail ? 'justify-center px-2' : 'px-3',
                isActive
                  ? 'border-accent bg-accent-muted text-text-primary'
                  : 'border-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!rail && label}
            {label === 'New scan' && running > 0 && (
              <span
                className={cn(
                  'rounded-full bg-accent-muted text-overline text-accent',
                  rail ? 'absolute ml-6 -mt-4 px-1' : 'ml-auto px-1.5',
                )}
              >
                {running}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className={cn('border-t border-surface-border', rail ? 'p-2' : 'p-3')}>
        {!rail && (
          <div className="mb-2 px-1">
            <p className="truncate text-body-sm text-text-primary">{user?.name}</p>
            <p className="truncate text-caption text-text-tertiary">{user?.role}</p>
          </div>
        )}
        <button
          type="button"
          onClick={signOut}
          title={rail ? 'Sign out' : undefined}
          className={cn(
            'flex w-full items-center gap-3 rounded py-2 text-body-sm text-text-secondary transition-colors hover:bg-status-danger-muted hover:text-status-danger',
            rail ? 'justify-center px-2' : 'px-3',
          )}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!rail && 'Sign out'}
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-surface">
      <aside
        data-print-hide
        className={cn(
          'fixed inset-y-0 left-0 z-40 hidden border-r border-surface-border bg-surface-raised',
          'md:block',
          // Deliberately not transitioned. With `transition-[width]` on an element whose display
          // is controlled by a media query, Chrome kept reporting the old computed width after
          // React swapped the class: re-applying the identical class resolved it to the right
          // value. A collapse that animates but does not collapse is worse than an instant one.
          collapsed ? 'w-16' : 'w-60',
        )}
      >
        {sidebarInner(collapsed)}
      </aside>

      {menuOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 md:hidden"
            onClick={() => setMenuOpen(false)}
          />
          <aside
            data-print-hide
            className="fixed inset-y-0 left-0 z-50 w-60 border-r border-surface-border bg-surface-raised md:hidden"
          >
            {sidebarInner(false)}
          </aside>
        </>
      )}

      {/* The shell is a fixed sidebar plus a 240px left inset here. On paper that leaves an
          empty column and pushes the report off the right edge, so print resets it. */}
      <div
        className={cn(collapsed ? 'md:pl-16' : 'md:pl-60')}
        data-print-main
      >
        <header
          data-print-hide
          className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-surface-border bg-surface-raised/95 px-4 backdrop-blur"
        >
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded p-1.5 text-text-secondary hover:bg-surface-hover hover:text-text-primary md:hidden"
            aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          <span className="text-body-sm text-text-secondary">
            Merchant Compliance Intelligence Engine
          </span>

          <div className="ml-auto flex items-center gap-3">
            <Tooltip content="Accounts live in this browser tab only. The MCIE API is unauthenticated.">
              <span className="cursor-default rounded-full border border-surface-border px-2 py-0.5 text-overline uppercase text-text-tertiary">
                Demo mode
              </span>
            </Tooltip>

            <span className="flex items-center gap-1.5 text-caption text-text-secondary">
              <span className={cn('h-2 w-2 rounded-full', HEALTH_COPY[health].dot)} />
              <span className="hidden sm:inline">{HEALTH_COPY[health].label}</span>
            </span>

            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-muted text-caption font-semibold text-accent">
              {user?.initials}
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>

      {/* Reads the report on whichever route is open, so answers are about this merchant. */}
      <AssistantWidget />
    </div>
  )
}
