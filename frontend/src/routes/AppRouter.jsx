// -----------------------------------------------------------------------------
// frontend/src/routes/AppRouter.jsx
//
// All routes. Public: sign in, sign up, password reset. Signed-in pages sit
// inside AppShell and are guarded by role: partners under /partner, admins
// under /admin. Signed-in users visiting /login go to their home page.
// Pages are loaded on demand to keep the first download small.
// -----------------------------------------------------------------------------

import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/app/AppShell'
import { Spinner } from '@/components/ui/spinner'
import { homePathFor, useAuth } from '@/context/AuthContext'

const SignInPage = lazy(() => import('@/features/auth/SignInPage'))
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/features/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/features/auth/ResetPasswordPage'))
const NotFoundPage = lazy(() => import('@/features/NotFoundPage'))

const PartnerDashboard = lazy(() => import('@/features/partner/DashboardPage'))
const ReferralLinksPage = lazy(() => import('@/features/partner/ReferralLinksPage'))
const PartnerConversionsPage = lazy(() => import('@/features/partner/ConversionsPage'))
const PartnerCommissionsPage = lazy(() => import('@/features/partner/CommissionsPage'))
const WalletPage = lazy(() => import('@/features/partner/WalletPage'))
const ProfilePage = lazy(() => import('@/features/partner/ProfilePage'))

const AdminOverview = lazy(() => import('@/features/admin/OverviewPage'))
const PartnersPage = lazy(() => import('@/features/admin/PartnersPage'))
const PartnerDetailPage = lazy(() => import('@/features/admin/PartnerDetailPage'))
const PayoutsPage = lazy(() => import('@/features/admin/PayoutsPage'))
const AdminCommissionsPage = lazy(() => import('@/features/admin/CommissionsPage'))
const RecordSalePage = lazy(() => import('@/features/admin/RecordSalePage'))
const TiersPage = lazy(() => import('@/features/admin/TiersPage'))
const SettingsPage = lazy(() => import('@/features/admin/SettingsPage'))
const ModelsPage = lazy(() => import('@/features/admin/ModelsPage'))
const FraudAlertsPage = lazy(() => import('@/features/admin/FraudAlertsPage'))
const ChurnRiskPage = lazy(() => import('@/features/admin/ChurnRiskPage'))
const RankingPage = lazy(() => import('@/features/admin/RankingPage'))
const DiscoveryPage = lazy(() => import('@/features/admin/DiscoveryPage'))
const AuditLogPage = lazy(() => import('@/features/admin/AuditLogPage'))

function PageFallback() {
  return (
    <div className="grid min-h-[40vh] place-items-center text-muted-text" role="status" aria-label="Loading">
      <Spinner className="size-5" />
    </div>
  )
}

function RequireRole({ role }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== role) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}

function PublicOnly() {
  const { user } = useAuth()
  if (user) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}

function Home() {
  const { user } = useAuth()
  return <Navigate to={homePathFor(user)} replace />
}

export default function AppRouter() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route element={<PublicOnly />}>
          <Route path="/login" element={<SignInPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Route>
        {/* Reachable signed in or out: the link comes from an email. */}
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        <Route element={<RequireRole role="partner" />}>
          <Route path="/partner" element={<AppShell />}>
            <Route index element={<Suspense fallback={<PageFallback />}><PartnerDashboard /></Suspense>} />
            <Route path="links" element={<Suspense fallback={<PageFallback />}><ReferralLinksPage /></Suspense>} />
            <Route path="conversions" element={<Suspense fallback={<PageFallback />}><PartnerConversionsPage /></Suspense>} />
            <Route path="commissions" element={<Suspense fallback={<PageFallback />}><PartnerCommissionsPage /></Suspense>} />
            <Route path="wallet" element={<Suspense fallback={<PageFallback />}><WalletPage /></Suspense>} />
            <Route path="profile" element={<Suspense fallback={<PageFallback />}><ProfilePage /></Suspense>} />
          </Route>
        </Route>

        <Route element={<RequireRole role="admin" />}>
          <Route path="/admin" element={<AppShell />}>
            <Route index element={<Suspense fallback={<PageFallback />}><AdminOverview /></Suspense>} />
            <Route path="partners" element={<Suspense fallback={<PageFallback />}><PartnersPage /></Suspense>} />
            <Route path="partners/:partnerId" element={<Suspense fallback={<PageFallback />}><PartnerDetailPage /></Suspense>} />
            <Route path="payouts" element={<Suspense fallback={<PageFallback />}><PayoutsPage /></Suspense>} />
            <Route path="commissions" element={<Suspense fallback={<PageFallback />}><AdminCommissionsPage /></Suspense>} />
            <Route path="record-sale" element={<Suspense fallback={<PageFallback />}><RecordSalePage /></Suspense>} />
            <Route path="tiers" element={<Suspense fallback={<PageFallback />}><TiersPage /></Suspense>} />
            <Route path="settings" element={<Suspense fallback={<PageFallback />}><SettingsPage /></Suspense>} />
            <Route path="models" element={<Suspense fallback={<PageFallback />}><ModelsPage /></Suspense>} />
            <Route path="fraud" element={<Suspense fallback={<PageFallback />}><FraudAlertsPage /></Suspense>} />
            <Route path="churn" element={<Suspense fallback={<PageFallback />}><ChurnRiskPage /></Suspense>} />
            <Route path="ranking" element={<Suspense fallback={<PageFallback />}><RankingPage /></Suspense>} />
            <Route path="discovery" element={<Suspense fallback={<PageFallback />}><DiscoveryPage /></Suspense>} />
            <Route path="audit-log" element={<Suspense fallback={<PageFallback />}><AuditLogPage /></Suspense>} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
