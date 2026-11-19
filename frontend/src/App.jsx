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

export default function App() {
  const [user, setUser] = useState(session.user)
  const [role, setRole] = useState(session.role)
  const [open, setOpen] = useState(false)
  const [pol, setPol] = useState(null)
  const loc = useLocation()
  const save = (u, r) => { session.set(u, r); setUser(u); setRole(r) }
  useEffect(() => setOpen(false), [loc.pathname])
  useEffect(() => { api.get('/api/policies/active').then((p) => setPol(p)).catch(() => {}) }, [loc.pathname])
  const initials = (user || '?').split(/\s+/).map((s) => s[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <nav className={`side ${open ? 'open' : ''}`} aria-label="Main">
        <div className="brand"><div className="brand-mark">C</div><div><b>Corvo Engineering</b><span>PR → PO automation</span></div></div>
        {NAV.map(([group, items]) => (
          <React.Fragment key={group}>
            <div className="nav-group">{group}</div>
            {items.map(([to, label, icon]) => (
              <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav ${isActive ? 'active' : ''}`}>
                <Icon name={icon} size={18} />{label}
              </NavLink>
            ))}
          </React.Fragment>
        ))}
        <div className="who">
          <div className="me"><div className="avatar" aria-hidden="true">{initials}</div>
            <div><div style={{ color: '#fff', fontWeight: 600 }}>{user || 'Set your name'}</div><div className="small" style={{ color: '#9db0da' }}>{role}</div></div></div>
          <label>Your name<input value={user} onChange={(e) => save(e.target.value, role)} placeholder="e.g. Asha Patil" /></label>
          <label>Role<select value={role} onChange={(e) => save(user, e.target.value)}><option>Requester</option><option>Buyer</option><option>Procurement</option></select></label>
          {pol && <div className="pol"><Icon name="shield" size={13} />Policy v{pol.version} active</div>}
        </div>
      </nav>
      <div>
        <button className="btn menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Toggle menu"><Icon name="menu" size={18} />Menu</button>
        <main id="main" className="main" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Chat />} />
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
