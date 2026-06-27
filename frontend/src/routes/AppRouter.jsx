import { Navigate, Route, Routes } from 'react-router-dom'
import AdminRoute from './AdminRoute.jsx'
import PartnerRoute from './PartnerRoute.jsx'
import AdminLayout from '../components/layout/AdminLayout.jsx'
import PartnerLayout from '../components/layout/PartnerLayout.jsx'
import LoginPage from '../pages/auth/LoginPage.jsx'
import RegisterPage from '../pages/auth/RegisterPage.jsx'
import ResetPasswordPage from '../pages/auth/ResetPasswordPage.jsx'
import AdminDashboardPage from '../pages/admin/AdminDashboardPage.jsx'
import PartnersPage from '../pages/admin/PartnersPage.jsx'
import PartnerDetailPage from '../pages/admin/PartnerDetailPage.jsx'
import PayoutsPage from '../pages/admin/PayoutsPage.jsx'
import FraudAlertsPage from '../pages/admin/FraudAlertsPage.jsx'
import DiscoveryPage from '../pages/admin/DiscoveryPage.jsx'
import SettingsPage from '../pages/admin/SettingsPage.jsx'
import PartnerDashboardPage from '../pages/partner/PartnerDashboardPage.jsx'
import ReferralsPage from '../pages/partner/ReferralsPage.jsx'
import CommissionsPage from '../pages/partner/CommissionsPage.jsx'
import WalletPage from '../pages/partner/WalletPage.jsx'
import ProfilePage from '../pages/partner/ProfilePage.jsx'

function NotFoundPage() {
  return (
    <section>
      <h1>404 - Page Not Found</h1>
    </section>
  )
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route element={<AdminRoute />}>
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/admin/partners" element={<PartnersPage />} />
          <Route path="/admin/partners/:partnerId" element={<PartnerDetailPage />} />
          <Route path="/admin/payouts" element={<PayoutsPage />} />
          <Route path="/admin/fraud" element={<FraudAlertsPage />} />
          <Route path="/admin/discovery" element={<DiscoveryPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route element={<PartnerRoute />}>
        <Route element={<PartnerLayout />}>
          <Route path="/partner" element={<PartnerDashboardPage />} />
          <Route path="/partner/referrals" element={<ReferralsPage />} />
          <Route path="/partner/commissions" element={<CommissionsPage />} />
          <Route path="/partner/wallet" element={<WalletPage />} />
          <Route path="/partner/profile" element={<ProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
