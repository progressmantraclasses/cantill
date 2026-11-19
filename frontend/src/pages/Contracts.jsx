import React, { useEffect, useState } from 'react'
import { api, inr } from '../api.js'
import { Banner, Button, Empty, Err, Field, Next, PageHeader, Skeleton } from '../components.jsx'

const blank = { contract_id: '', supplier_id: '', start_date: '', end_date: '', value_cap: '', consumed_value: 0, lines: {} }

export default function Contracts() {
  const [list, setList] = useState(null)
  const [form, setForm] = useState(null)
  const [warn, setWarn] = useState([])
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)
  const [lineText, setLineText] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api.get('/api/contracts').then(setList).catch((e) => { setError(e); setList([]) })
  useEffect(() => { load() }, [])

  async function onPdf(f) {
    if (!f) return
    setError(null); setOk(null); setBusy(true)
    try {
      const x = await api.upload('/api/contracts/extract', f)
      setForm({ ...blank, ...x, source: 'pdf' }); setWarn([...(x.warnings || []), ...(x.already_loaded ? ['This contract is already loaded.'] : [])])
      setLineText(Object.entries(x.lines || {}).map(([k, v]) => `${k}=${v}`).join('\n'))
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  function parseLines(t) {
    const out = {}
    t.split(/\n|,/).forEach((s) => { const [k, v] = s.split('='); if (k && v && !isNaN(parseFloat(v))) out[k.trim()] = parseFloat(v) })
    return out
  }
  async function save() {
    setError(null); setBusy(true)
    try {
      await api.post('/api/contracts', { ...form, lines: parseLines(lineText), value_cap: Number(form.value_cap), consumed_value: Number(form.consumed_value || 0), source: form.source || 'manual' })
      setOk(`${form.contract_id} saved. Reprocess a batch to apply it.`); setForm(null); load()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div>
      <PageHeader title="Contracts" subtitle="The register as at 31 Oct 2026, plus contracts signed since. Those exist only as signed PDFs and are binding from their start date (policy 4.4)." />
      <Err e={error} />{ok && <Banner kind="ok">{ok}</Banner>}
      {!form ? (
        <section className="card" aria-label="Add contract">
          <Next>upload a signed contract PDF to add it, or enter one by hand.</Next>
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <Field label="Signed contract (PDF)"><input type="file" accept=".pdf" onChange={(e) => onPdf(e.target.files[0])} disabled={busy} /></Field>
            <Button icon="plus" onClick={() => { setForm({ ...blank, source: 'manual' }); setLineText(''); setWarn([]) }}>Enter manually</Button>
          </div>
        </section>
      ) : (
        <section className="card" aria-label="Review contract">
          <div className="card-head"><h3>Review contract before saving</h3></div>
          {warn.map((w, i) => <Banner key={i} kind="warn">{w}</Banner>)}
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <Field label="Contract no."><input value={form.contract_id || ''} onChange={set('contract_id')} /></Field>
            <Field label="Supplier id"><input value={form.supplier_id || ''} onChange={set('supplier_id')} /></Field>
            <Field label="Start date"><input type="date" value={form.start_date || ''} onChange={set('start_date')} /></Field>
            <Field label="End date"><input type="date" value={form.end_date || ''} onChange={set('end_date')} /></Field>
            <Field label="Value ceiling (₹)"><input value={form.value_cap || ''} onChange={set('value_cap')} inputMode="decimal" /></Field>
            <Field label="Consumed so far (₹)"><input value={form.consumed_value ?? 0} onChange={set('consumed_value')} inputMode="decimal" /></Field>
          </div>
          <div style={{ marginTop: 12 }}><Field label="Item rates" hint="One per line, e.g. ITM-1036=3537.76"><textarea value={lineText} onChange={(e) => setLineText(e.target.value)} style={{ fontFamily: 'var(--mono)', fontSize: 12 }} /></Field></div>
          <div className="row" style={{ marginTop: 12 }}><Button variant="primary" icon="check" loading={busy} onClick={save}>Save contract</Button><Button onClick={() => setForm(null)}>Cancel</Button></div>
        </section>
      )}
      <section className="card flush" aria-label="Contract register">
        {list === null ? <div style={{ padding: 16 }}><Skeleton rows={6} /></div> : !list.length ? <Empty icon="file" title="No contracts">Add the first contract above.</Empty> : (
          <div className="tablewrap"><table aria-label="Contracts">
            <thead><tr><th>Contract</th><th>Supplier</th><th>Valid</th><th className="num">Ceiling</th><th className="num">Consumed</th><th>Items</th><th>Source</th></tr></thead>
            <tbody>{list.map((c) => {
              const expired = c.end_date < today, future = c.start_date > today
              const pct = Math.min(100, Math.round((c.consumed_value / c.value_cap) * 100))
              return (
                <tr key={c.contract_id}><td className="mono"><b>{c.contract_id}</b></td>
                  <td>{c.supplier_id} {c.supplier_name}{c.supplier_status !== 'Active' && <span className="chip bad" style={{ marginLeft: 6 }}><i />{c.supplier_status}</span>}</td>
                  <td className="small nowrap">{c.start_date} → {c.end_date}{expired && <span className="chip gray" style={{ marginLeft: 6 }}>Expired</span>}{future && <span className="chip warn" style={{ marginLeft: 6 }}>Not started</span>}</td>
                  <td className="num">{inr(c.value_cap)}</td>
                  <td className="num" style={{ minWidth: 130 }}>{inr(c.consumed_value)}<div className="score-bar" aria-hidden="true"><i style={{ width: `${pct}%`, background: pct > 90 ? 'var(--bad)' : undefined }} /></div><span className="muted small">{pct}% used</span></td>
                  <td className="small">{Object.entries(c.lines).map(([k, v]) => <div key={k}><span className="mono">{k}</span> @ {inr(v)}</div>)}</td>
                  <td><span className={`chip ${c.source === 'register' ? 'gray' : 'warn'}`}>{c.source === 'register' ? 'Register' : 'PDF-only'}</span></td></tr>)
            })}</tbody></table></div>
        )}
      </section>
    </div>
  )
}
