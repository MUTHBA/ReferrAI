import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'
import PageWrapper from './PageWrapper.jsx'

const navItems = [
  { to: '/partner', label: 'Dashboard', end: true },
  { to: '/partner/referrals', label: 'Referrals' },
  { to: '/partner/commissions', label: 'Commissions' },
  { to: '/partner/wallet', label: 'Wallet' },
  { to: '/partner/profile', label: 'Profile' },
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

export default function PartnerLayout() {
  return (
    <div style={styles.shell}>
      <Sidebar title="ReferrAI Partner" items={navItems} />
      <div style={styles.contentShell}>
        <Topbar title="Partner" />
        <PageWrapper>
          <Outlet />
        </PageWrapper>
      </div>
    </div>
  )
}
