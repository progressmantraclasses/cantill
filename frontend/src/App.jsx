import React, { useEffect, useState } from 'react'
import { NavLink, Route, Routes, Navigate, useLocation } from 'react-router-dom'
import { api, session } from './api.js'
import { Icon } from './components.jsx'
import Chat from './pages/Chat.jsx'
import Batches from './pages/Batches.jsx'
import Workspace from './pages/Workspace.jsx'
import Policy from './pages/Policy.jsx'
import Contracts from './pages/Contracts.jsx'
import Preferred from './pages/Preferred.jsx'
import Audit from './pages/Audit.jsx'

const NAV = [
  ['Request', [['/', 'Raise a request', 'chat']]],
  ['Procure', [['/batches', 'PR batches', 'layers'], ['/workspace', 'Buyer workspace', 'inbox'], ['/preferred', 'Preferred suppliers', 'star']]],
  ['Govern', [['/policy', 'Policy', 'shield'], ['/contracts', 'Contracts', 'file'], ['/audit', 'Audit log', 'history']]],
]

const COLLAPSE_KEY = 'sidebar-collapsed'
const readCollapsed = () => { try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false } }
const initialsOf = (name) => (name || '?').split(/\s+/).map((s) => s[0]).join('').slice(0, 2).toUpperCase()

/** Desktop: collapsed state is remembered. Mobile: the menu slides in and closes on navigation. */
function useSidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => setMobileOpen(false), [loc.pathname])
  const toggleCollapsed = () => setCollapsed((c) => {
    try { localStorage.setItem(COLLAPSE_KEY, c ? '0' : '1') } catch { /* storage unavailable */ }
    return !c
  })
  return { collapsed, toggleCollapsed, mobileOpen, setMobileOpen }
}

function Sidebar({ collapsed, onToggle, mobileOpen, user, role, onSave, policy }) {
  return (
    <nav className={`side ${mobileOpen ? 'open' : ''}`} aria-label="Main">
      <div className="brand">
        <div className="brand-mark">C</div>
        <div className="brand-text"><b>Corvo Engineering</b><span>PR → PO automation</span></div>
        <button className="collapse-btn" onClick={onToggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={16} />
        </button>
      </div>
      {NAV.map(([group, items]) => (
        <React.Fragment key={group}>
          <div className="nav-group">{group}</div>
          {items.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === '/'} title={collapsed ? label : undefined}
              className={({ isActive }) => `nav ${isActive ? 'active' : ''}`}>
              <Icon name={icon} size={18} /><span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </React.Fragment>
      ))}
      <div className="who">
        <div className="me" title={collapsed ? `${user} · ${role}` : undefined}>
          <div className="avatar" aria-hidden="true">{initialsOf(user)}</div>
          <div className="me-text"><div className="me-name">{user || 'Set your name'}</div><div className="small me-role">{role}</div></div>
        </div>
        <div className="who-fields">
          <label>Your name<input value={user} onChange={(e) => onSave(e.target.value, role)} placeholder="e.g. Asha Patil" /></label>
          <label>Role<select value={role} onChange={(e) => onSave(user, e.target.value)}><option>Requester</option><option>Buyer</option><option>Procurement</option></select></label>
          {policy && <div className="pol"><Icon name="shield" size={13} />Policy v{policy.version} active</div>}
        </div>
      </div>
    </nav>
  )
}

export default function App() {
  const [user, setUser] = useState(session.user)
  const [role, setRole] = useState(session.role)
  const [policy, setPolicy] = useState(null)
  const { collapsed, toggleCollapsed, mobileOpen, setMobileOpen } = useSidebar()
  const loc = useLocation()
  const save = (u, r) => { session.set(u, r); setUser(u); setRole(r) }
  useEffect(() => { api.get('/api/policies/active').then(setPolicy).catch(() => {}) }, [loc.pathname])

  return (
    <div className={`shell ${collapsed ? 'collapsed' : ''}`}>
      <a href="#main" className="skip">Skip to content</a>
      <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} mobileOpen={mobileOpen}
        user={user} role={role} onSave={save} policy={policy} />
      {mobileOpen && <div className="scrim" onClick={() => setMobileOpen(false)} aria-hidden="true" />}
      <div>
        <button className="btn menu-btn" onClick={() => setMobileOpen(!mobileOpen)} aria-expanded={mobileOpen} aria-label="Toggle menu">
          <Icon name="menu" size={18} />Menu
        </button>
        <main id="main" className="main" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Chat user={user} />} />
            <Route path="/batches" element={<Batches />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/policy" element={<Policy />} />
            <Route path="/contracts" element={<Contracts />} />
            <Route path="/preferred" element={<Preferred />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
