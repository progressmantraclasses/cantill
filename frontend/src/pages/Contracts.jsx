import React, { useEffect, useMemo, useState } from 'react'
import { api, inr, session } from '../api.js'
import { Banner, Button, Empty, Err, Field, FileDrop, Icon, Kpi, Next, PageHeader, RoleNotice, SectionHead, SkeletonTable } from '../components.jsx'

const BUYER_ROLES = ['Buyer', 'Procurement']
const blank = { contract_id: '', supplier_id: '', start_date: '', end_date: '', value_cap: '', consumed_value: 0, lines: {} }
const today = () => new Date().toISOString().slice(0, 10)
const RATE_RE = /^\s*([A-Za-z]{3}-\d+)\s*[=:]\s*₹?\s*([\d,]+(?:\.\d+)?)\s*$/

/** "ITM-1036=3,537.76" per line (or separated by ;) → { rates, bad lines }. */
export function parseRates(text) {
  const rates = {}, bad = []
  text.split(/\n|;/).map((s) => s.trim()).filter(Boolean).forEach((s) => {
    const m = s.match(RATE_RE)
    if (m) rates[m[1].toUpperCase()] = Number(m[2].replace(/,/g, ''))
    else bad.push(s)
  })
  return { rates, bad }
}

function validate(form, rates, bad) {
  const problems = []
  if (!String(form.contract_id || '').trim()) problems.push('Contract no. is required.')
  if (!String(form.supplier_id || '').trim()) problems.push('Supplier is required.')
  if (!form.start_date || !form.end_date) problems.push('Start and end dates are required.')
  else if (form.end_date < form.start_date) problems.push('End date is before start date.')
  const cap = Number(form.value_cap), used = Number(form.consumed_value || 0)
  if (!(cap > 0)) problems.push('Value ceiling must be a number greater than zero.')
  else if (!(used >= 0 && used <= cap)) problems.push('Consumed must be between zero and the ceiling.')
  if (!Object.keys(rates).length) problems.push('Add at least one item rate.')
  if (bad.length) problems.push(`Cannot read rate line(s): ${bad.join(' · ')}`)
  return problems
}

function UsageBar({ used, cap }) {
  const pct = cap > 0 ? Math.min(100, Math.round((used / cap) * 100)) : 0
  return (
    <>
      {inr(used)}
      <div className="score-bar" aria-hidden="true"><i style={{ width: `${pct}%`, background: pct > 90 ? 'var(--bad)' : pct > 70 ? 'var(--accent)' : undefined }} /></div>
      <span className="muted small">{pct}% used</span>
    </>
  )
}

export default function Contracts() {
  const [list, setList] = useState(null)
  const [suppliers, setSuppliers] = useState([])
  const [form, setForm] = useState(null)
  const [pdf, setPdf] = useState(null)
  const [warn, setWarn] = useState([])
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)
  const [lineText, setLineText] = useState('')
  const [busy, setBusy] = useState(false)
  const [problems, setProblems] = useState([])
  const canAct = BUYER_ROLES.includes(session.role)

  const load = () => api.get('/api/contracts').then(setList).catch((e) => { setError(e); setList([]) })
  useEffect(() => { load(); api.get('/api/suppliers').then(setSuppliers).catch(() => {}) }, [])

  async function onPdf(f) {
    setPdf(f)
    if (!f) return
    setError(null); setOk(null); setBusy(true)
    try {
      const x = await api.upload('/api/contracts/extract', f)
      setForm({ ...blank, ...x, source: 'pdf' })
      setWarn([...(x.warnings || []), ...(x.already_loaded ? [`${x.contract_id} is already loaded in the register.`] : [])])
      setLineText(Object.entries(x.lines || {}).map(([k, v]) => `${k}=${v}`).join('\n'))
      setProblems([])
    } catch (e) { setError(e) } finally { setBusy(false); setPdf(null) }
  }
  function startManual() { setForm({ ...blank, source: 'manual' }); setLineText(''); setWarn([]); setProblems([]); setOk(null) }
  async function save() {
    const { rates, bad } = parseRates(lineText)
    const found = validate(form, rates, bad)
    setProblems(found)
    if (found.length) return
    setError(null); setBusy(true)
    try {
      await api.post('/api/contracts', { ...form, contract_id: String(form.contract_id).trim(), lines: rates, value_cap: Number(form.value_cap), consumed_value: Number(form.consumed_value || 0), source: form.source || 'manual' })
      setOk(`${form.contract_id} saved. Reprocess a batch to apply it.`); setForm(null); load()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const stats = useMemo(() => {
    const t = today(), rows = list || []
    return { active: rows.filter((c) => c.start_date <= t && c.end_date >= t).length, pdf: rows.filter((c) => c.source !== 'register').length,
      expiring: rows.filter((c) => c.end_date >= t && c.end_date <= new Date(Date.now() + 60 * 864e5).toISOString().slice(0, 10)).length }
  }, [list])

  return (
    <div>
      <PageHeader icon="file" title="Contracts" subtitle="The register as at 31 Oct 2026, plus contracts signed since. Those exist only as signed PDFs and are binding from their start date (policy 4.4)." />
      <Err e={error} />{ok && <Banner kind="ok">{ok}</Banner>}
      <RoleNotice role={session.role} allowed={BUYER_ROLES} action="add contracts" />

      {list && (
        <div className="kpis">
          <Kpi icon="fileSign" value={list.length} label="Contracts" />
          <Kpi icon="tick" tone="ok" value={stats.active} label="Active today" />
          <Kpi icon="clock" tone="warn" value={stats.expiring} label="Expiring in 60 days" />
          <Kpi icon="file" value={stats.pdf} label="PDF-only / manual" />
        </div>
      )}

      {canAct && (!form ? (
        <section className="card" aria-label="Add contract">
          <SectionHead icon="plus" title="Add a contract" sub="The PDF is read for you; you review every field before it is saved." />
          <Next>drop a signed contract PDF, or enter one by hand.</Next>
          <div className="upload-grid">
            <FileDrop id="contract-file" accept={['.pdf']} file={pdf} onFile={onPdf} busy={busy} busyLabel="Reading contract…" title="Drag & drop a signed contract PDF" />
            <div className="upload-side">
              <span className="muted small">No PDF? Type the terms in yourself.</span>
              <Button icon="edit" onClick={startManual}>Enter manually</Button>
            </div>
          </div>
        </section>
      ) : (
        <section className="card" aria-label="Review contract">
          <SectionHead icon="shieldCheck" title="Review contract before saving" sub={form.source === 'pdf' ? 'Read from the PDF. Check each value against the signed copy.' : 'Manual entry.'} />
          {warn.map((w, i) => <Banner key={i} kind="warn">{w}</Banner>)}
          <div className="form-grid">
            <Field label="Contract no."><input value={form.contract_id || ''} onChange={set('contract_id')} placeholder="RC-2026-040" /></Field>
            <Field label="Supplier">
              <select value={form.supplier_id || ''} onChange={set('supplier_id')}>
                <option value="">Choose a supplier…</option>
                {suppliers.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.supplier_id} · {s.name}{s.status !== 'Active' ? ` (${s.status})` : ''}</option>)}
              </select>
            </Field>
            <Field label="Start date"><input type="date" value={form.start_date || ''} onChange={set('start_date')} /></Field>
            <Field label="End date"><input type="date" value={form.end_date || ''} onChange={set('end_date')} /></Field>
            <Field label="Value ceiling (₹)"><input value={form.value_cap || ''} onChange={set('value_cap')} inputMode="decimal" placeholder="500000" /></Field>
            <Field label="Consumed so far (₹)"><input value={form.consumed_value ?? 0} onChange={set('consumed_value')} inputMode="decimal" /></Field>
          </div>
          <div style={{ marginTop: 12 }}><Field label="Item rates" hint="One per line, e.g. ITM-1036=3537.76 (commas are fine)"><textarea value={lineText} onChange={(e) => setLineText(e.target.value)} style={{ fontFamily: 'var(--mono)', fontSize: 12 }} /></Field></div>
          {problems.length > 0 && <Banner kind="err">{problems.join('\n')}</Banner>}
          <div className="row" style={{ marginTop: 12 }}><Button variant="primary" icon="check" loading={busy} onClick={save}>Save contract</Button><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button></div>
        </section>
      ))}

      <section className="card flush" aria-label="Contract register">
        <div className="pad-head"><SectionHead icon="list" title="Contract register" /></div>
        {list === null ? <SkeletonTable rows={6} cols={7} /> : !list.length ? <Empty icon="file" title="No contracts">Add the first contract above.</Empty> : (
          <div className="tablewrap"><table aria-label="Contracts">
            <thead><tr><th>Contract</th><th>Supplier</th><th>Valid</th><th className="num">Ceiling</th><th className="num">Consumed</th><th>Items</th><th>Source</th></tr></thead>
            <tbody>{list.map((c) => {
              const t = today(), expired = c.end_date < t, future = c.start_date > t
              return (
                <tr key={c.contract_id}><td className="mono"><b>{c.contract_id}</b></td>
                  <td><span className="mono">{c.supplier_id}</span> {c.supplier_name}{c.supplier_status !== 'Active' && <span className="chip bad" style={{ marginLeft: 6 }}><i />{c.supplier_status}</span>}</td>
                  <td className="small nowrap"><Icon name="calendar" size={13} /> {c.start_date} → {c.end_date}{expired && <span className="chip gray" style={{ marginLeft: 6 }}>Expired</span>}{future && <span className="chip warn" style={{ marginLeft: 6 }}>Not started</span>}</td>
                  <td className="num">{inr(c.value_cap)}</td>
                  <td className="num" style={{ minWidth: 130 }}><UsageBar used={c.consumed_value} cap={c.value_cap} /></td>
                  <td className="small">{Object.entries(c.lines).map(([k, v]) => <div key={k}><span className="mono">{k}</span> @ {inr(v)}</div>)}</td>
                  <td><span className={`chip ${c.source === 'register' ? 'gray' : 'warn'}`}><Icon name={c.source === 'register' ? 'list' : 'file'} size={12} />{c.source === 'register' ? 'Register' : c.source === 'pdf' ? 'PDF-only' : 'Manual'}</span></td></tr>)
            })}</tbody></table></div>
        )}
      </section>
    </div>
  )
}
