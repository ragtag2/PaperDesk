import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { CircleHelp, Inbox, LayoutDashboard, LogOut, Menu, Network, Plus, Settings2, Ticket, Users, X } from 'lucide-react'
import { isDemoMode } from '../api/client'
import { useAuth } from './AuthContext'
import { NotificationsProvider } from './NotificationsContext'
import { NotificationBell } from '../components/NotificationBell'

const nav = [
  { to: '/tickets', label: 'All tickets', icon: LayoutDashboard },
  { to: '/tickets/new', label: 'New ticket', icon: Plus },
  { to: '/notifications', label: 'Notifications', icon: Inbox },
  { to: '/profile', label: 'My profile', icon: Settings2 },
]

export function AppLayout() {
  const { user } = useAuth()
  return <NotificationsProvider key={user?._id}><LayoutContent /></NotificationsProvider>
}

function LayoutContent() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  async function handleLogout() {
    try { await signOut() } finally { navigate('/login', { replace: true }) }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-top">
        <Link className="brand" to="/tickets" onClick={() => setMenuOpen(false)} aria-label="Paperdesk home">
          <span className="brand-mark"><Ticket size={23} strokeWidth={2.5} /></span>
          <span>paperdesk<span className="brand-dot">.</span></span>
        </Link>
        <button className="mobile-close icon-button" type="button" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={21} /></button>
      </div>
      <div className="sidebar-note"><span className="note-pin" aria-hidden="true" />Good things get done one ticket at a time.<span className="note-squiggle" aria-hidden="true">~~~~</span></div>
      <div className="nav-caption">WORKSPACE</div>
      <nav className="sidebar-nav" aria-label="Main navigation">
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/tickets'} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={20} strokeWidth={2.3} /><span>{label}</span></NavLink>)}
        {user?.role === 'admin' && <NavLink to="/users" onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Users size={20} strokeWidth={2.3} /><span>Team members</span></NavLink>}
        {user?.role === 'admin' && <NavLink to="/teams" onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Network size={20} strokeWidth={2.3} /><span>Teams</span></NavLink>}
      </nav>
      <div className="sidebar-bottom">
        {isDemoMode && <div className="demo-chip"><span className="demo-dot" /> Sample workspace</div>}
        <div className="sidebar-help"><CircleHelp size={17} /><span>Need a hand? Create a ticket.</span></div>
        <div className="profile-mini">
          <span className="avatar">{user?.name?.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span>
          <span className="profile-mini-text"><strong>{user?.name}</strong><small>{user?.role}</small></span>
          <button className="icon-button logout-button" type="button" onClick={handleLogout} aria-label="Log out" title="Log out"><LogOut size={19} /></button>
        </div>
      </div>
    </aside>
    {menuOpen && <button className="menu-backdrop" type="button" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}
    <div className="app-main">
      <header className="workspace-header"><button type="button" className="icon-button mobile-menu-toggle" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu size={24} /></button><Link className="brand workspace-mobile-brand" to="/tickets">paperdesk<span className="brand-dot">.</span></Link><span className="workspace-header-label">Your workspace</span><div className="workspace-header-actions"><NotificationBell /><Link to="/profile" className="header-profile" aria-label="My profile"><span className="avatar">{user?.name?.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><span>{user?.name}</span></Link><Link to="/tickets/new" className="mobile-new" aria-label="New ticket"><Plus size={22} /></Link></div></header>
      <main id="main-content" className="page-content"><Outlet /></main>
    </div>
  </div>
}
