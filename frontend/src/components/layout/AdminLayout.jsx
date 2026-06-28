// -----------------------------------------------------------------------------
// frontend/src/components/layout/AdminLayout.jsx
//
// Layout shell wrapped around every /admin/* route by AppRouter — renders
// the admin nav in Sidebar, the Topbar, and the active page via <Outlet/>
// inside PageWrapper. Only reachable past AdminRoute's role check.
// -----------------------------------------------------------------------------

import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'
import PageWrapper from './PageWrapper.jsx'

const navItems = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/partners', label: 'Partners' },
  { to: '/admin/payouts', label: 'Payouts' },
  { to: '/admin/fraud', label: 'Fraud Alerts' },
  { to: '/admin/discovery', label: 'Discovery' },
  { to: '/admin/settings', label: 'Settings' },
]

const styles = {
  shell: {
    minHeight: '100vh',
    display: 'flex',
    backgroundColor: '#f8fafc',
    color: '#111827',
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  contentShell: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
}

export default function AdminLayout() {
  return (
    <div style={styles.shell}>
      <Sidebar title="ReferrAI Admin" items={navItems} />
      <div style={styles.contentShell}>
        <Topbar title="Admin" />
        <PageWrapper>
          <Outlet />
        </PageWrapper>
      </div>
    </div>
  )
}
