// -----------------------------------------------------------------------------
// frontend/src/components/layout/Sidebar.jsx
//
// Shared sidebar nav shell used by both AdminLayout and PartnerLayout —
// parameterized by `title` and `items` so each layout supplies its own nav
// links instead of duplicating the component. Highlights the active route
// via react-router-dom's NavLink.
// -----------------------------------------------------------------------------

import { NavLink } from 'react-router-dom'

const styles = {
  sidebar: {
    width: '220px',
    flexShrink: 0,
    backgroundColor: '#111827',
    color: '#f9fafb',
    padding: '24px 16px',
  },
  title: {
    margin: '0 0 24px',
    fontSize: '18px',
    fontWeight: 700,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  link: {
    display: 'block',
    borderRadius: '6px',
    padding: '10px 12px',
    color: '#d1d5db',
    textDecoration: 'none',
    fontWeight: 500,
  },
  activeLink: {
    backgroundColor: '#2563eb',
    color: '#ffffff',
  },
}

export default function Sidebar({ title, items }) {
  return (
    <aside style={styles.sidebar}>
      <p style={styles.title}>{title}</p>
      <nav aria-label="Primary navigation" style={styles.nav}>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            style={({ isActive }) => ({
              ...styles.link,
              ...(isActive ? styles.activeLink : {}),
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
