import { Suspense, lazy } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { EmptyState, Spinner } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import { ToastProvider } from './lib/toast'
import type { Role } from './lib/types'
import { Hub } from './pages/Hub'
import { Login } from './pages/Login'

// Every route is split, so a visit to Outreach never downloads the trade
// dashboard's charts and vice versa.
const Landing = lazy(() => import('./pages/Landing').then((m) => ({ default: m.Landing })))
const SignUp = lazy(() => import('./pages/auth/SignUp').then((m) => ({ default: m.SignUp })))
const ForgotPassword = lazy(() =>
  import('./pages/auth/ForgotPassword').then((m) => ({ default: m.ForgotPassword })),
)
const ResetPassword = lazy(() =>
  import('./pages/auth/ResetPassword').then((m) => ({ default: m.ResetPassword })),
)
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Pipeline = lazy(() => import('./pages/Pipeline').then((m) => ({ default: m.Pipeline })))
const Contacts = lazy(() => import('./pages/Contacts').then((m) => ({ default: m.Contacts })))
const ContactDetail = lazy(() =>
  import('./pages/ContactDetail').then((m) => ({ default: m.ContactDetail })),
)
const Activities = lazy(() => import('./pages/Activities').then((m) => ({ default: m.Activities })))
const Documents = lazy(() => import('./pages/Documents').then((m) => ({ default: m.Documents })))
const Reminders = lazy(() => import('./pages/Reminders').then((m) => ({ default: m.Reminders })))
const Campaigns = lazy(() => import('./pages/Campaigns').then((m) => ({ default: m.Campaigns })))
const CampaignDetail = lazy(() => import('./pages/CampaignDetail').then((m) => ({ default: m.CampaignDetail })))
const OutreachReport = lazy(() => import('./pages/OutreachReport').then((m) => ({ default: m.OutreachReport })))
const OutreachSettings = lazy(() => import('./pages/OutreachSettings').then((m) => ({ default: m.OutreachSettings })))
const Outreach = lazy(() => import('./pages/Outreach').then((m) => ({ default: m.Outreach })))
const Team = lazy(() => import('./pages/Team').then((m) => ({ default: m.Team })))
const Profile = lazy(() => import('./pages/Profile').then((m) => ({ default: m.Profile })))

// Bevi Stoq - Inventory Management
const BeviStoqDashboard = lazy(() =>
  import('./pages/BevoGrow/BeviStoqDashboard').then((m) => ({ default: m.BeviStoqDashboard })),
)
const BeviStoqProducts = lazy(() =>
  import('./pages/BevoGrow/BeviStoqProducts').then((m) => ({ default: m.BeviStoqProducts })),
)
const BeviStoqCategories = lazy(() =>
  import('./pages/BevoGrow/BeviStoqCategories').then((m) => ({ default: m.BeviStoqCategories })),
)
const BeviStoqLocations = lazy(() =>
  import('./pages/BevoGrow/BeviStoqLocations').then((m) => ({ default: m.BeviStoqLocations })),
)
const BeviStoqStock = lazy(() =>
  import('./pages/BevoGrow/BeviStoqStock').then((m) => ({ default: m.BeviStoqStock })),
)

function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Warming the cup…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />

  // The API enforces this too — the guard only avoids showing a page whose
  // every request would be rejected.
  if (roles && !roles.includes(user.role)) {
    return (
      <EmptyState
        emoji="🔒"
        title="You don't have access to this page"
        hint="Ask a BeviGrow administrator if you need it."
      />
    )
  }
  return <>{children}</>
}

export default function App() {
  return (
    <Router>
      <ToastProvider>
        <AuthProvider>
          <Suspense fallback={<Spinner label="Brewing…" />}>
            <Routes>
              {/* public */}
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<SignUp />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />

              {/* authenticated */}
              <Route
                path="/app"
                element={
                  <RequireAuth>
                    <AppShell />
                  </RequireAuth>
                }
              >
                {/* the choice between the two workspaces */}
                <Route index element={<Hub />} />

                {/* workspace 1 — inbound quoting */}
                <Route path="trade" element={<Dashboard />} />
                <Route path="trade/quotes" element={<Contacts />} />
                <Route path="trade/quotes/:id" element={<ContactDetail />} />
                <Route path="trade/pipeline" element={<Pipeline />} />
                <Route path="trade/activity" element={<Activities />} />
                <Route path="trade/documents" element={<Documents />} />
                <Route path="trade/follow-ups" element={<Reminders />} />

                {/* workspace 2 — outbound prospecting */}
                <Route path="outreach" element={<Outreach />} />
                <Route path="outreach/campaigns" element={<Campaigns />} />
                <Route path="outreach/campaigns/:id" element={<CampaignDetail />} />
                <Route path="outreach/settings" element={<OutreachSettings />} />
                <Route path="outreach/report" element={<OutreachReport />} />

                {/* shared */}
                <Route path="profile" element={<Profile />} />
                <Route
                  path="team"
                  element={
                    <RequireAuth roles={['admin', 'manager']}>
                      <Team />
                    </RequireAuth>
                  }
                />

                {/* Bevi Stoq — Inventory Management */}
                <Route path="bevi-stoq" element={<BeviStoqDashboard />} />
                <Route path="bevi-stoq/products" element={<BeviStoqProducts />} />
                <Route path="bevi-stoq/categories" element={<BeviStoqCategories />} />
                <Route path="bevi-stoq/locations" element={<BeviStoqLocations />} />
                <Route path="bevi-stoq/stock" element={<BeviStoqStock />} />

                {/* the old flat URLs, kept so existing links and bookmarks work */}
                <Route path="contacts" element={<Navigate to="/app/trade/quotes" replace />} />
                <Route path="contacts/:id" element={<LegacyQuoteRedirect />} />
                <Route path="pipeline" element={<Navigate to="/app/trade/pipeline" replace />} />
                <Route path="activities" element={<Navigate to="/app/trade/activity" replace />} />
                <Route path="documents" element={<Navigate to="/app/trade/documents" replace />} />
                <Route path="reminders" element={<Navigate to="/app/trade/follow-ups" replace />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </ToastProvider>
    </Router>
  )
}

/** /app/contacts/12 → /app/trade/quotes/12 */
function LegacyQuoteRedirect() {
  const id = window.location.pathname.split('/').pop()
  return <Navigate to={`/app/trade/quotes/${id}`} replace />
}
