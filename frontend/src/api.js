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
    const fallback = res.status >= 500 && !body
      ? 'The server did not respond properly. Check that the backend is running on port 8000.'
      : `Request failed (${res.status})`
    const e = new Error((body && body.error) || fallback)
    e.body = body
    e.status = res.status
    throw e
  }
  return body
}

/** fetch() that turns a network failure into a message a user can act on. */
async function request(path, init = {}) {
  let res
  try {
    res = await fetch(BASE + path, { ...init, headers: headers(init.headers) })
  } catch {
    const e = new Error('Cannot reach the server. Check that the backend is running (port 8000) and try again.')
    e.status = 0
    throw e
  }
  return res
}

const json = (method) => (p, body) => request(p, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(handle)

export const api = {
  get: (p) => request(p).then(handle),
  post: json('POST'),
  patch: json('PATCH'),
  upload: (p, file, fields = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v))
    return request(p, { method: 'POST', body: fd }).then(handle)
  },
  url: (p) => BASE + p,
}

export async function download(path, filename) {
  const res = await request(path)
  if (!res.ok) await handle(res)
  const href = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000) // revoking immediately can cancel the download in some browsers
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
