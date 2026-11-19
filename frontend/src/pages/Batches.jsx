import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, download, inr, ROUTE_LABEL } from '../api.js'
import { Banner, Button, Empty, Err, Icon, Kpi, Next, PageHeader, RouteChip, Skeleton } from '../components.jsx'

const PAGE = 50

export default function Batches() {
  const [file, setFile] = useState(null)
  const [batches, setBatches] = useState(null)
  const [current, setCurrent] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [versions, setVersions] = useState([])
  const [ver, setVer] = useState('')

  const load = () => api.get('/api/batches').then(setBatches).catch((e) => { setError(e); setBatches([]) })
  useEffect(() => { load().then?.(() => {}); api.get('/api/batches').then((b) => { if (b[0]) api.get(`/api/batches/${b[0].id}`).then((r) => setCurrent({ batch_id: r.id, summary: r.summary, decisions: r.decisions })).catch(() => {}) }).catch(() => {}); api.get('/api/policies').then((v) => setVersions(v.filter((x) => x.status === 'approved'))).catch(() => {}) }, [])
  useEffect(() => setPage(0), [filter, q, current?.batch_id])

  async function process() {
    setBusy(true); setError(null)
    try { setCurrent(await api.upload('/api/process-batch' + (ver ? `?policy_version=${encodeURIComponent(ver)}` : ''), file)); load() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function reprocess(id) {
    setBusy(true); setError(null)
    try { setCurrent(await api.post(`/api/batches/${id}/reprocess`, { policy_version: ver })); load() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function open(id) {
    setError(null)
    try { const r = await api.get(`/api/batches/${id}`); setCurrent({ batch_id: r.id, summary: r.summary, decisions: r.decisions }) } catch (e) { setError(e) }
  }

  const rows = useMemo(() => (current?.decisions || []).filter((r) =>
    (!filter || r.route === filter) &&
    (!q || `${r.pr_no} ${r.resolved_item_code} ${r.supplier_id} ${r.group_id} ${r.po_id} ${r.reason}`.toLowerCase().includes(q.toLowerCase()))), [current, filter, q])
  const pages = Math.max(1, Math.ceil(rows.length / PAGE))
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE)

  const verSelect = (
    <label className="field"><span>Policy version</span>
      <select value={ver} onChange={(e) => setVer(e.target.value)}>
        <option value="">By effective date (default)</option>
        {versions.map((v) => <option key={v.id} value={v.version}>Force v{v.version} (effective {v.effective_from})</option>)}
      </select>
    </label>
  )

  return (
    <div>
      <PageHeader title="PR batches" subtitle="Upload a PR batch CSV. The active policy decides every line: clubbing, valuation, contracts, route and PO consolidation." />
      <section className="card" aria-label="Upload batch">
        <Next>{file ? <>press <b>Process batch</b>.</> : <>choose a PR batch CSV file.</>}</Next>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <label className="field grow"><span>PR batch file (.csv)</span><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0])} /></label>
          {verSelect}
          <Button variant="primary" icon="upload" loading={busy} disabled={!file} onClick={process}>{busy ? 'Processing…' : 'Process batch'}</Button>
        </div>
        <Err e={error} />
      </section>

      {!current && !error && (
        <section className="card" aria-label="How it works">
          <div className="steps">
            <div className="step"><div className="n">1</div><div><b>Upload</b><span>A CSV in the sample PR format: one row per PR line.</span></div></div>
            <div className="step"><div className="n">2</div><div><b>Decide</b><span>Lines are clubbed into requirements, valued and routed by the active policy.</span></div></div>
            <div className="step"><div className="n">3</div><div><b>Review or export</b><span>Approve in the buyer workspace, or download the decisions as CSV.</span></div></div>
          </div>
        </section>
      )}

      {current && (
        <section aria-label="Batch results">
          <div className="page-head" style={{ marginBottom: 12 }}>
            <div className="t"><h3 style={{ fontSize: 17 }}>Batch #{current.batch_id} · policy v{current.summary.policy_versions.join(', v')}</h3>
              <div className="muted small">{current.summary.lines} lines → {current.summary.requirements} requirements → {current.summary.pos} POs</div></div>
            <div className="actions">
              <Button icon="refresh" loading={busy} onClick={() => reprocess(current.batch_id)}>Reprocess</Button>
              <Link className="btn" to="/workspace">Open in workspace</Link>
              <Button variant="primary" icon="download" onClick={() => download(`/api/batches/${current.batch_id}/export.csv`, `decisions_batch_${current.batch_id}.csv`)}>Export CSV</Button>
            </div>
          </div>
          <div className="kpis">
            <Kpi value={current.summary.lines} label="All lines" onClick={() => setFilter('')} on={!filter} />
            {Object.entries(current.summary.routes).map(([r, n]) => <Kpi key={r} value={n} label={ROUTE_LABEL[r] || r} onClick={() => setFilter(filter === r ? '' : r)} on={filter === r} />)}
          </div>
          <div className="card flush">
            <div className="row" style={{ padding: 12 }}>
              <div className="search grow"><Icon name="search" size={16} /><input aria-label="Search decisions" placeholder="Search PR, item, supplier, reason…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
              <span className="muted small">{rows.length} of {current.decisions.length} lines</span>
            </div>
            <div className="tablewrap scroll">
              <table aria-label="Decisions">
                <thead><tr><th>PR / line</th><th>Item</th><th>Group</th><th>PO</th><th>Route</th><th>Supplier / suggested</th><th className="num">Unit price</th><th className="num">Group value</th><th>Reason</th></tr></thead>
                <tbody>
                  {shown.map((r, i) => (
                    <tr key={i}>
                      <td className="mono nowrap">{r.pr_no}/{r.pr_line}</td><td className="mono">{r.resolved_item_code}</td><td className="mono">{r.group_id}</td><td className="mono">{r.po_id}</td>
                      <td><RouteChip route={r.route} /></td>
                      <td className="mono">{r.supplier_id || r.suggested_supplier_ids}</td>
                      <td className="num">{inr(r.unit_price)}</td><td className="num">{inr(r.group_value_inr)}</td>
                      <td className="small" style={{ minWidth: 320 }}>{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && <Empty icon="search" title="No lines match">Clear the filter or search.</Empty>}
            </div>
            <div className="pager"><span className="muted small">Page {page + 1} of {pages}</span>
              <div className="row"><Button size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><Button size="sm" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next</Button></div></div>
          </div>
        </section>
      )}

      <section className="card flush" aria-label="Earlier batches">
        <div className="card-head" style={{ padding: '14px 16px 0' }}><h3>Earlier batches</h3></div>
        {batches === null ? <div style={{ padding: 16 }}><Skeleton rows={3} /></div> : batches.length === 0 ? <Empty title="No batches yet">Upload your first PR batch above.</Empty> : (
          <div className="tablewrap"><table aria-label="Batches">
            <thead><tr><th>#</th><th>Name</th><th>Kind</th><th className="num">Lines</th><th>Policy</th><th>Processed</th><th /></tr></thead>
            <tbody>{batches.map((b) => (
              <tr key={b.id}><td>{b.id}</td><td>{b.name}</td><td><span className="chip gray">{b.kind}</span></td><td className="num">{b.summary?.lines}</td><td>v{b.summary?.policy_versions?.join(', v')}</td><td className="small">{String(b.processed_at || '').replace('T', ' ')}</td>
                <td><Button size="sm" onClick={() => open(b.id)}>View</Button></td></tr>))}</tbody>
          </table></div>
        )}
      </section>
    </div>
  )
}
