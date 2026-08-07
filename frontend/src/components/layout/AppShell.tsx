import {
  BarChart3,
  Bell,
  Coffee,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Users,
  Users2,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../lib/auth'
import type { Role } from '../../lib/types'
import { initials } from '../../lib/format'
import { Steam } from '../coffee/Ambient'
import { cx } from '../ui'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  /** When set, only these roles see the link. The API enforces it as well. */
  roles?: Role[]
}

const NAV: NavItem[] = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/pipeline', label: 'Pipeline', icon: BarChart3 },
  { to: '/app/contacts', label: 'Customers', icon: Users },
  { to: '/app/activities', label: 'Activity Log', icon: MessageSquare },
  { to: '/app/documents', label: 'Documents', icon: FileText },
  { to: '/app/reminders', label: 'Follow-ups', icon: Bell },
  { to: '/app/team', label: 'Team', icon: Users2, roles: ['admin', 'manager'] },
]

export function AppShell() {
  const { user, logout } = useAuth()
  // Hide links the current role cannot use, so nobody is sent to a dead end.
  const visibleNav = NAV.filter((item) => !item.roles || (user && item.roles.includes(user.role)))
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setOpen(false), [location.pathname])

  return (
    <div className="relative min-h-screen">
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-bean/70 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-caramel/15 bg-darkroast/95 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between px-5 py-6">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gold-gradient shadow-lift">
                <Coffee size={20} className="text-bean" />
              </div>
              <Steam count={2} className="absolute -top-4 left-2.5 opacity-60" />
            </div>
            <div>
              <p className="font-display text-lg leading-none text-latte">BeviGrow</p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-gold/70">Trade Tracker</p>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-latte/50 hover:bg-latte/10 lg:hidden"
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {visibleNav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  'group relative flex min-h-[44px] items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-gold/12 text-latte'
                    : 'text-latte/55 hover:bg-latte/5 hover:text-latte/85',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-gold" />
                  )}
                  <Icon size={17} className={isActive ? 'text-gold' : ''} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-caramel/15 p-4">
          <NavLink
            to="/app/profile"
            className={({ isActive }) =>
              cx(
                'mb-3 flex items-center gap-3 rounded-xl px-3 py-2.5 transition',
                isActive ? 'bg-gold/12 ring-1 ring-gold/30' : 'bg-espresso/50 hover:bg-espresso/80',
              )
            }
          >
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt=""
                referrerPolicy="no-referrer"
                className="h-9 w-9 shrink-0 rounded-full border border-caramel/30 object-cover"
              />
            ) : (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold-gradient text-xs font-bold text-bean">
                {initials(user?.name ?? 'BG')}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-latte">{user?.name}</p>
              <p className="truncate text-[11px] capitalize text-latte/45">
                {user?.role} · view profile
              </p>
            </div>
          </NavLink>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-caramel/20 px-3 py-2 text-sm text-latte/60 transition hover:border-red-400/40 hover:text-red-300"
          >
            <LogOut size={15} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main column */}
      <div className="relative z-10 lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-4 border-b border-caramel/15 bg-darkroast/80 px-5 py-3.5 backdrop-blur-xl lg:px-8">
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg p-2 text-latte/60 hover:bg-latte/10 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={19} />
          </button>
          <div className="flex-1">
            <p className="text-[11px] uppercase tracking-[0.22em] text-gold/60">
              Export &amp; Import Operations
            </p>
          </div>
        </header>

        <main className="px-5 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
