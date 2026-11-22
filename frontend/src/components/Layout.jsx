import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import BuildFooter from './BuildFooter.jsx'

const NAV = [
  { to: '/comparisons', label: 'Comparisons' },
  { to: '/documents', label: 'Documents' },
  { to: '/search', label: 'Search' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            <img src="/favicon.svg" alt="" width="24" height="24" />
            RegulationDiff
          </NavLink>
          <nav className="nav">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-user">
            <span className="muted">{user?.email}</span>
            <button type="button" className="button ghost small" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <BuildFooter />
    </div>
  )
}
