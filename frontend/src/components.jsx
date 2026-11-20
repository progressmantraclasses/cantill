import React from 'react'
import { ROUTE_LABEL } from './api.js'

const PATHS = {
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  layers: <><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></>,
  inbox: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" /></>,
  shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>,
  star: <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />,
  history: <><path d="M3 3v5h5" /><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" /><polyline points="12 7 12 12 15 15" /></>,
  alert: <><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></>,
  check: <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></>,
  x: <><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
  send: <><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></>,
  search: <><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></>,
  refresh: <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
  info: <><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></>,
  plus: <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>,
  menu: <><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></>,
  arrow: <><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>,
  inboxempty: <><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></>,
}

export function Icon({ name, size = 18, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {PATHS[name]}
    </svg>
  )
}

export function Button({ variant = '', icon, loading, children, size, ...p }) {
  return (
    <button {...p} className={`btn ${variant} ${size || ''} ${p.className || ''}`} aria-busy={loading || undefined} disabled={p.disabled || loading}>
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="page-head">
      <div className="t"><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      {children && <div className="actions">{children}</div>}
    </header>
  )
}

export const Next = ({ children }) => (
  <div className="next" role="note"><Icon name="arrow" className="ic" size={18} /><div><b>Next:</b> {children}</div></div>
)

export function RouteChip({ route }) {
  const cls = route?.endsWith('_PO') ? 'po' : route === 'NOT_PROCESSED' ? 'bad' : route === 'NEW_ITEM_SOURCING' || route === 'CAPEX_SOURCING' ? 'warn' : ''
  return <span className={`chip ${cls}`}><i />{ROUTE_LABEL[route] || route}</span>
}

export function Banner({ kind = 'info', children }) {
  if (!children) return null
  const icon = kind === 'err' ? 'x' : kind === 'ok' ? 'check' : kind === 'warn' ? 'alert' : 'info'
  return <div className={`banner ${kind}`} role={kind === 'err' ? 'alert' : 'status'}><Icon name={icon} size={18} /><div>{children}</div></div>
}

export const Err = ({ e }) => (e ? <Banner kind="err">{e.message || String(e)}{e.body?.errors ? '\n• ' + e.body.errors.join('\n• ') : ''}</Banner> : null)

export function Empty({ icon = 'inboxempty', title, children }) {
  return <div className="empty"><Icon name={icon} size={36} /><b>{title}</b><div>{children}</div></div>
}

export function Skeleton({ rows = 5 }) {
  return <div aria-hidden="true">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skel" style={{ width: `${95 - (i % 3) * 18}%` }} />)}</div>
}

export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  )
}

export const Kpi = ({ value, label, onClick, on }) => {
  const inner = <><div className="v">{value}</div><div className="l">{label}</div></>
  return onClick ? <button className={`kpi ${on ? 'on' : ''}`} onClick={onClick} aria-pressed={!!on}>{inner}</button> : <div className="kpi">{inner}</div>
}

export const Field = ({ label, children, hint }) => <label className="field"><span>{label}</span>{children}{hint && <span className="muted small" style={{ fontWeight: 400 }}>{hint}</span>}</label>
