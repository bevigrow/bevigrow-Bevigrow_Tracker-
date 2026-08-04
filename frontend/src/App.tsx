import { Suspense, lazy } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { Spinner } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import { ToastProvider } from './lib/toast'
import { Dashboard } from './pages/Dashboard'
import { Login } from './pages/Login'

// The landing page pulls in Three.js and GSAP (~950 kB). Splitting it out keeps
// that weight off every authenticated route — the dashboard never loads it.
const Landing = lazy(() => import('./pages/Landing').then((m) => ({ default: m.Landing })))
const Pipeline = lazy(() => import('./pages/Pipeline').then((m) => ({ default: m.Pipeline })))
const Contacts = lazy(() => import('./pages/Contacts').then((m) => ({ default: m.Contacts })))
const ContactDetail = lazy(() =>
  import('./pages/ContactDetail').then((m) => ({ default: m.ContactDetail })),
)
const Activities = lazy(() => import('./pages/Activities').then((m) => ({ default: m.Activities })))
const Documents = lazy(() => import('./pages/Documents').then((m) => ({ default: m.Documents })))
const Reminders = lazy(() => import('./pages/Reminders').then((m) => ({ default: m.Reminders })))
const Team = lazy(() => import('./pages/Team').then((m) => ({ default: m.Team })))

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Warming the cup…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PageFallback() {
  return <Spinner label="Brewing…" />
}

export default function App() {
  return (
    <Router>
      <ToastProvider>
        <AuthProvider>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route
                path="/app"
                element={
                  <RequireAuth>
                    <AppShell />
                  </RequireAuth>
                }
              >
                <Route index element={<Dashboard />} />
                <Route path="pipeline" element={<Pipeline />} />
                <Route path="contacts" element={<Contacts />} />
                <Route path="contacts/:id" element={<ContactDetail />} />
                <Route path="activities" element={<Activities />} />
                <Route path="documents" element={<Documents />} />
                <Route path="reminders" element={<Reminders />} />
                <Route path="team" element={<Team />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </ToastProvider>
    </Router>
  )
}
