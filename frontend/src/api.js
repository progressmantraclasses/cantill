const BASE = import.meta.env.VITE_API_URL || ''

// Convenience for demos/links: ?user=Asha&role=Procurement sets who you act as.
try {
  const q = new URLSearchParams(window.location.search)
  if (q.get('role') || q.get('user')) {
    if (q.get('user')) localStorage.setItem('user', q.get('user'))
    if (['Requester', 'Buyer', 'Procurement'].includes(q.get('role'))) localStorage.setItem('role', q.get('role'))
  }
} catch { /* storage unavailable */ }

export const session = {
  get user() { return localStorage.getItem('user') || 'Demo user' },
  get role() { return localStorage.getItem('role') || 'Buyer' },
  set(user, role) { localStorage.setItem('user', user); localStorage.setItem('role', role) },
}

function headers(extra = {}) {
  return { 'X-User': session.user || 'anonymous', 'X-Role': session.role, ...extra }
}

async function handle(res) {
  const type = res.headers.get('content-type') || ''
  const body = type.includes('json') ? await res.json() : await res.text()
  if (!res.ok) {
    const e = new Error((body && body.error) || `Request failed (${res.status})`)
    e.body = body
    e.status = res.status
    throw e
  }
  return body
}

export const api = {
  get: (p) => fetch(BASE + p, { headers: headers() }).then(handle),
  post: (p, json) => fetch(BASE + p, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify(json || {}) }).then(handle),
  patch: (p, json) => fetch(BASE + p, { method: 'PATCH', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify(json || {}) }).then(handle),
  upload: (p, file, fields = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v))
    return fetch(BASE + p, { method: 'POST', headers: headers(), body: fd }).then(handle)
  },
  url: (p) => BASE + p,
}

export async function download(path, filename) {
  const res = await fetch(BASE + path, { headers: headers() })
  if (!res.ok) throw new Error('Download failed')
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export const inr = (v) => {
  if (v === null || v === undefined || v === '') return ''
  const n = Number(v)
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 })
}
export const ROUTE_LABEL = {
  CONTRACT_PO: 'Contract PO', EMERGENCY_PO: 'Emergency PO', SPOT_PO: 'Spot PO', RFQ: 'RFQ', RFP: 'RFP',
  CAPEX_SOURCING: 'Capex sourcing', NEW_ITEM_SOURCING: 'New item', NOT_PROCESSED: 'Not processed',
}
