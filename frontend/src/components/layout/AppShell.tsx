import {
  BarChart3,
  Bell,
  ChevronLeft,
  Coffee,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Send,
  Users,
  Users2,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../lib/auth'
import { initials } from '../../lib/format'
import type { Role } from '../../lib/types'
import { cx } from '../ui'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  /** When set, only these roles see the link. The API enforces it as well. */
  roles?: Role[]
}

/**
 * Two workspaces, never shown at once.
 *
 * Inbound quoting and outbound prospecting are separate jobs. Listing all of
 * both made a dozen sidebar links where a person only ever needs a handful, so
 * the shell shows the section you are actually in and offers a way back.
 */
const TRADE_NAV: NavItem[] = [
  { to: '/app/trade', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/trade/quotes', label: 'Quotes', icon: Users },
  { to: '/app/trade/pipeline', label: 'Deal Stages', icon: BarChart3 },
  { to: '/app/trade/activity', label: 'Activity Log', icon: MessageSquare },
  { to: '/app/trade/documents', label: 'Documents', icon: FileText },
  { to: '/app/trade/follow-ups', label: 'Follow-ups', icon: Bell },
]

const OUTREACH_NAV: NavItem[] = [{ to: '/app/outreach', label: 'Outreach', icon: Send, end: true }]

const SHARED_NAV: NavItem[] = [
  { to: '/app/team', label: 'Team', icon: Users2, roles: ['admin', 'manager'] },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setOpen(false), [location.pathname])

  const inOutreach = location.pathname.startsWith('/app/outreach')
  const inTrade = location.pathname.startsWith('/app/trade')
  const section = inOutreach ? 'Outreach' : inTrade ? 'Trade Desk' : null

  const items = inOutreach ? OUTREACH_NAV : inTrade ? TRADE_NAV : []
  const visible = [...items, ...SHARED_NAV].filter(
    (item) => !item.roles || (user && item.roles.includes(user.role)),
  )

  return (
    <div className="relative min-h-screen">
      {open && (
        <div
          className="fixed inset-0 z-30 bg-bean/70 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-caramel/15 bg-darkroast/95 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between px-5 py-6">
          <NavLink to="/app" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gold-gradient shadow-lift">
              <Coffee size={20} className="text-bean" />
            </div>
            <div>
              <p className="font-display text-lg leading-none text-latte">BeviGrow</p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-gold/70">
                {section ?? 'Trade Tracker'}
              </p>
            </div>
          </NavLink>
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-latte/50 hover:bg-latte/10 lg:hidden"
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {section && (
            <NavLink
              to="/app"
              className="mb-2 flex min-h-[44px] items-center gap-2 rounded-xl px-3.5 text-[11px] uppercase tracking-wider text-latte/40 transition hover:text-latte/75"
            >
              <ChevronLeft size={14} />
              All sections
            </NavLink>
          )}

          {/* From the hub, offer both doors before anything shared. */}
          {!section && (
            <>
              <NavLink
                to="/app/trade"
                className="flex min-h-[44px] items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-latte/55 transition hover:bg-latte/5 hover:text-latte/85"
              >
                <LayoutDashboard size={17} />
                Trade Desk
              </NavLink>
              <NavLink
                to="/app/outreach"
                className="flex min-h-[44px] items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-latte/55 transition hover:bg-latte/5 hover:text-latte/85"
              >
                <Send size={17} />
                Outreach
              </NavLink>
            </>
          )}

          {visible.map(({ to, label, icon: Icon, end }) => (
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

      <div className="relative z-10 lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-4 border-b border-caramel/15 bg-darkroast/80 px-5 py-3.5 backdrop-blur-xl lg:px-8">
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg p-2 text-latte/60 hover:bg-latte/10 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={19} />
          </button>
          <p className="flex-1 text-[11px] uppercase tracking-[0.22em] text-gold/60">
            {section ?? 'BeviGrow'}
          </p>
        </header>

        <main className="px-5 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
