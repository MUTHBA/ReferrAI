import { useAuth } from '../../hooks/useAuth.js'

const styles = {
  bar: {
    height: '64px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid #e5e7eb',
    backgroundColor: '#ffffff',
    padding: '0 32px',
  },
  title: {
    fontSize: '20px',
    fontWeight: 700,
  },
  userArea: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    fontSize: '14px',
    color: '#374151',
  },
  logoutButton: {
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    padding: '6px 12px',
    backgroundColor: '#ffffff',
    cursor: 'pointer',
    fontWeight: 500,
  },
}

export default function Topbar({ title }) {
  const { user, logout } = useAuth()

  return (
    <header style={styles.bar}>
      <span style={styles.title}>{title}</span>
      <div style={styles.userArea}>
        {user && <span>{user.email ?? user.sub}</span>}
        <button type="button" style={styles.logoutButton} onClick={logout}>
          Log out
        </button>
      </div>
    </header>
  )
}
