import React, { useRef, useState } from 'react'
import { ROUTE_LABEL } from './api.js'

/* ───────── Icons (24px stroke set) ───────── */
const PATHS = {
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  layers: <><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></>,
  inbox: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" /></>,
  shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  shieldCheck: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>,
  fileSign: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M8 18c1.5-2 2.5-2 3 0s1.5 2 3-1" /></>,
  sheet: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><rect x="8" y="12" width="8" height="6" rx="1" /><line x1="12" y1="12" x2="12" y2="18" /><line x1="8" y1="15" x2="16" y2="15" /></>,
  star: <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />,
  history: <><path d="M3 3v5h5" /><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" /><polyline points="12 7 12 12 15 15" /></>,
  alert: <><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></>,
  check: <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></>,
  tick: <polyline points="20 6 9 17 4 12" />,
  x: <><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></>,
  close: <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
  uploadCloud: <><polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" /><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" /></>,
  send: <><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></>,
  search: <><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></>,
  refresh: <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
  info: <><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></>,
  plus: <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>,
  trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /></>,
  edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" /></>,
  bot: <><rect x="4" y="8" width="16" height="12" rx="3" /><path d="M12 4v4" /><circle cx="12" cy="3" r="1" /><line x1="9" y1="13" x2="9" y2="15" /><line x1="15" y1="13" x2="15" y2="15" /></>,
  sparkles: <><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" /><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" /></>,
  chevronLeft: <polyline points="15 18 9 12 15 6" />,
  chevronRight: <polyline points="9 18 15 12 9 6" />,
  chevronDown: <polyline points="6 9 12 15 18 9" />,
  menu: <><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></>,
  arrow: <><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>,
  inboxempty: <><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></>,
  lock: <><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></>,
  calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></>,
  clock: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
  cart: <><circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" /><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" /></>,
  package: <><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></>,
  list: <><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" /></>,
  flag: <><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" /></>,
  zap: <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />,
  users: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>,
  wallet: <><path d="M20 12V8H6a2 2 0 0 1 0-4h12v4" /><path d="M4 6v12a2 2 0 0 0 2 2h14v-4" /><path d="M18 12a2 2 0 0 0 0 4h4v-4z" /></>,
}

export function Icon({ name, size = 18, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {PATHS[name]}
    </svg>
  )
}

/* ───────── Basic controls ───────── */
export function Button({ variant = '', icon, loading, children, size, ...p }) {
  return (
    <button {...p} className={`btn ${variant} ${size || ''} ${p.className || ''}`} aria-busy={loading || undefined} disabled={p.disabled || loading}>
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  )
}

/** Two-step destructive action without a browser dialog: first click asks, second click acts. */
export function ConfirmButton({ children, confirmLabel = 'Yes, continue', onConfirm, loading, icon = 'trash', variant = 'danger' }) {
  const [asking, setAsking] = useState(false)
  if (!asking) return <Button variant={variant} icon={icon} onClick={() => setAsking(true)}>{children}</Button>
  return (
    <span className="confirm-inline" role="group" aria-label="Confirm action">
      <span className="small">Are you sure?</span>
      <Button variant="danger" size="sm" loading={loading} onClick={async () => { await onConfirm(); setAsking(false) }}>{confirmLabel}</Button>
      <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
    </span>
  )
}

export const Field = ({ label, children, hint }) => <label className="field"><span>{label}</span>{children}{hint && <span className="muted small" style={{ fontWeight: 400 }}>{hint}</span>}</label>

export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  )
}

/* ───────── Layout ───────── */
export function PageHeader({ icon, title, subtitle, children }) {
  return (
    <header className="page-head">
      {icon && <div className="page-ic" aria-hidden="true"><Icon name={icon} size={22} /></div>}
      <div className="t"><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      {children && <div className="actions">{children}</div>}
    </header>
  )
}

/** Card heading with an icon tile, an optional one-line description and actions on the right. */
export function SectionHead({ icon, title, sub, children }) {
  return (
    <div className="sec-head">
      {icon && <span className="sec-ic" aria-hidden="true"><Icon name={icon} size={18} /></span>}
      <div className="grow"><h3>{title}</h3>{sub && <div className="muted small">{sub}</div>}</div>
      {children}
    </div>
  )
}

export const Next = ({ children }) => (
  <div className="next" role="note"><Icon name="arrow" className="ic" size={18} /><div><b>Next:</b> {children}</div></div>
)

export const Kpi = ({ value, label, icon, tone = '', onClick, on }) => {
  const inner = (
    <>
      {icon && <span className={`kpi-ic ${tone}`} aria-hidden="true"><Icon name={icon} size={17} /></span>}
      <span className="kpi-txt"><span className="v">{value}</span><span className="l">{label}</span></span>
    </>
  )
  return onClick
    ? <button className={`kpi ${on ? 'on' : ''}`} onClick={onClick} aria-pressed={!!on}>{inner}</button>
    : <div className="kpi">{inner}</div>
}

/* ───────── Feedback ───────── */
export function RouteChip({ route }) {
  const cls = route?.endsWith('_PO') ? 'po' : route === 'NOT_PROCESSED' ? 'bad' : route === 'NEW_ITEM_SOURCING' || route === 'CAPEX_SOURCING' ? 'warn' : ''
  return <span className={`chip ${cls}`}><i />{ROUTE_LABEL[route] || route}</span>
}

export function Banner({ kind = 'info', icon, children }) {
  if (!children) return null
  const name = icon || (kind === 'err' ? 'x' : kind === 'ok' ? 'check' : kind === 'warn' ? 'alert' : 'info')
  return <div className={`banner ${kind}`} role={kind === 'err' ? 'alert' : 'status'}><Icon name={name} size={18} /><div>{children}</div></div>
}

export const Err = ({ e }) => (e ? <Banner kind="err">{e.message || String(e)}{e.body?.errors ? '\n• ' + e.body.errors.join('\n• ') : ''}</Banner> : null)

/** Shown in place of an action the current role may not take. */
export function RoleNotice({ role, allowed, action }) {
  if (allowed.includes(role)) return null
  return (
    <Banner kind="warn" icon="lock">
      You are acting as <b>{role}</b>. Switch your role to <b>{allowed.join(' or ')}</b> (bottom of the menu) to {action}.
    </Banner>
  )
}

export function Empty({ icon = 'inboxempty', title, children }) {
  return <div className="empty"><span className="empty-ic"><Icon name={icon} size={28} /></span><b>{title}</b><div>{children}</div></div>
}

/* ───────── File upload ───────── */
const fmtSize = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`)
const extOf = (name) => (name.match(/\.[^.]+$/)?.[0] || '').toLowerCase()

/**
 * Drag-and-drop upload area with type/size validation and a file preview.
 * `accept` is a list of extensions, e.g. ['.csv']. `onFile(file | null)`.
 */
export function FileDrop({ id, accept, maxMB = 20, file, onFile, title, hint, busy, busyLabel = 'Uploading…', disabled }) {
  const input = useRef()
  const [drag, setDrag] = useState(false)
  const [error, setError] = useState(null)
  const types = accept.map((a) => a.replace('.', '').toUpperCase()).join(', ')

  function take(f) {
    if (!f) return
    if (!accept.includes(extOf(f.name))) return setError(`“${f.name}” is not a ${types} file.`)
    if (f.size === 0) return setError(`“${f.name}” is empty.`)
    if (f.size > maxMB * 1048576) return setError(`“${f.name}” is ${fmtSize(f.size)}; the limit is ${maxMB} MB.`)
    setError(null)
    onFile(f)
  }
  const clear = () => { onFile(null); setError(null); if (input.current) input.current.value = '' }
  const off = disabled || busy

  return (
    <div>
      <div
        className={`drop ${drag ? 'dragging' : ''} ${file ? 'has-file' : ''} ${error ? 'invalid' : ''} ${off ? 'off' : ''}`}
        onDragOver={(e) => { e.preventDefault(); if (!off) setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (!off) take(e.dataTransfer.files[0]) }}
      >
        <input id={id} ref={input} type="file" className="sr-only" accept={accept.join(',')} disabled={off}
          onChange={(e) => { take(e.target.files[0]); e.target.value = '' }} />
        {busy ? (
          <div className="drop-busy" role="status"><span className="spinner lg" aria-hidden="true" /><b>{busyLabel}</b>{file && <span className="muted small">{file.name}</span>}</div>
        ) : file ? (
          <div className="drop-file">
            <span className="file-badge" aria-hidden="true">{extOf(file.name).slice(1) || 'file'}</span>
            <div className="grow"><b className="file-name">{file.name}</b><div className="muted small">{fmtSize(file.size)} · ready</div></div>
            <label htmlFor={id} className="btn sm">Replace</label>
            <button type="button" className="btn sm ghost icon-only" onClick={clear} aria-label="Remove file"><Icon name="close" size={16} /></button>
          </div>
        ) : (
          <label htmlFor={id} className="drop-empty">
            <span className="drop-ic" aria-hidden="true"><Icon name="uploadCloud" size={26} /></span>
            <b>{title || 'Drag & drop a file here'}</b>
            <span className="muted">or <span className="link">browse your computer</span></span>
            <span className="drop-hint">{hint || `${types} · up to ${maxMB} MB`}</span>
          </label>
        )}
      </div>
      {error && <div className="field-error" role="alert"><Icon name="alert" size={14} />{error}</div>}
    </div>
  )
}

/* ───────── Skeletons ───────── */
const range = (n) => Array.from({ length: n }, (_, i) => i)
const Bone = ({ w = '100%', h = 12, r }) => <span className="skel" style={{ width: w, height: h, borderRadius: r }} />

/** Text-block placeholder: a short heading bar then lines of varying width. */
export function Skeleton({ rows = 5, heading = true }) {
  return (
    <div className="skel-block" role="status" aria-label="Loading">
      {heading && <Bone w="38%" h={16} />}
      {range(rows).map((i) => <Bone key={i} w={`${96 - (i % 3) * 17}%`} />)}
    </div>
  )
}

/** Table-shaped placeholder that matches the layout of the data tables. */
export function SkeletonTable({ rows = 6, cols = 5 }) {
  return (
    <div className="skel-table" role="status" aria-label="Loading table">
      <div className="skel-tr head">{range(cols).map((c) => <Bone key={c} w={`${50 + (c % 3) * 15}%`} h={10} />)}</div>
      {range(rows).map((r) => (
        <div key={r} className="skel-tr">
          {range(cols).map((c) => <Bone key={c} w={`${c === 0 ? 70 : 40 + ((r + c) % 4) * 14}%`} />)}
        </div>
      ))}
    </div>
  )
}

export function SkeletonKpis({ count = 5 }) {
  return (
    <div className="kpis" role="status" aria-label="Loading figures">
      {range(count).map((i) => <div key={i} className="kpi"><Bone w={34} h={34} r={9} /><span className="kpi-txt"><Bone w={48} h={20} /><Bone w={90} h={10} /></span></div>)}
    </div>
  )
}

/** List / detail placeholder, e.g. the buyer workspace. */
export function SkeletonSplit() {
  return (
    <>
      <SkeletonKpis count={6} />
      <div className="split">
        <div className="card flush"><SkeletonTable rows={8} cols={4} /></div>
        <div className="card"><Skeleton rows={7} /></div>
      </div>
    </>
  )
}

/* ───────── Chat ───────── */
export function Avatar({ kind, label }) {
  return <div className={`chat-avatar ${kind}`} aria-hidden="true">{kind === 'assistant' ? <Icon name="bot" size={16} /> : label}</div>
}
