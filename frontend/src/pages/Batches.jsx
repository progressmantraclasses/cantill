import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, download, inr, ROUTE_LABEL } from '../api.js'
import { Banner, Button, Empty, Err, FileDrop, Icon, Kpi, Next, PageHeader, RouteChip, SectionHead, SkeletonTable } from '../components.jsx'

const PAGE = 50
const ROUTE_ICON = { CONTRACT_PO: ['fileSign', 'ok'], EMERGENCY_PO: ['zap', 'bad'], SPOT_PO: ['cart', 'ok'], RFQ: ['users', ''], RFP: ['list', ''],
  CAPEX_SOURCING: ['wallet', 'warn'], NEW_ITEM_SOURCING: ['package', 'warn'], NOT_PROCESSED: ['alert', 'bad'] }
const STEPS = [
  ['uploadCloud', 'Upload', 'A CSV in the sample PR format: one row per PR line.'],
  ['shieldCheck', 'Decide', 'Lines are clubbed into requirements, valued and routed by the active policy.'],
  ['download', 'Review or export', 'Approve in the buyer workspace, or download the decisions as CSV.'],
]
const asCurrent = (r) => ({ batch_id: r.id, name: r.name, summary: r.summary, decisions: r.decisions })

export default function Batches() {
  const [file, setFile] = useState(null)
  const [batches, setBatches] = useState(null)
  const [current, setCurrent] = useState(null)
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)
  const [filter, setFilter] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [versions, setVersions] = useState([])
  const [ver, setVer] = useState('')

  const loadList = () => api.get('/api/batches').then((b) => { setBatches(b); return b }).catch((e) => { setError(e); setBatches([]); return [] })
  useEffect(() => {
    loadList().then((b) => b[0] && open(b[0].id))
    api.get('/api/policies').then((v) => setVersions(v.filter((x) => x.status === 'approved'))).catch(() => {})
  }, [])
  useEffect(() => setPage(0), [filter, q, current?.batch_id])

  async function run(action, success) {
    setBusy(true); setError(null); setOk(null)
    try { const r = await action(); setCurrent(r); setFilter(''); setOk(success(r)); loadList() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const process = () => run(async () => {
    const r = await api.upload('/api/process-batch' + (ver ? `?policy_version=${encodeURIComponent(ver)}` : ''), file)
    setFile(null)
    return { ...r, name: file.name }
  }, (r) => `Processed ${r.summary.lines} lines from ${r.name}.`)
  const reprocess = (id) => run(async () => ({ ...(await api.post(`/api/batches/${id}/reprocess`, { policy_version: ver })), name: current?.name }),
    (r) => `Batch #${r.batch_id} reprocessed under policy v${r.summary.policy_versions.join(', v')}.`)

  async function open(id) {
    setError(null)
    try { setCurrent(asCurrent(await api.get(`/api/batches/${id}`))); setFilter('') } catch (e) { setError(e) }
  }
  async function exportCsv() {
    setExporting(true); setError(null)
    try { await download(`/api/batches/${current.batch_id}/export.csv`, `decisions_batch_${current.batch_id}.csv`) } catch (e) { setError(e) } finally { setExporting(false) }
  }

  const rows = useMemo(() => (current?.decisions || []).filter((r) =>
    (!filter || r.route === filter) &&
    (!q || `${r.pr_no} ${r.resolved_item_code} ${r.supplier_id} ${r.group_id} ${r.po_id} ${r.reason}`.toLowerCase().includes(q.toLowerCase()))), [current, filter, q])
  const pages = Math.max(1, Math.ceil(rows.length / PAGE))
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE)

  return (
    <div>
      <PageHeader icon="layers" title="PR batches" subtitle="Upload a PR batch CSV. The active policy decides every line: clubbing, valuation, contracts, route and PO consolidation." />
      <Err e={error} />
      {ok && <Banner kind="ok">{ok}</Banner>}

      <section className="card" aria-label="Upload batch">
        <SectionHead icon="uploadCloud" title="Process a new batch" sub="Columns: pr_no, pr_line, created_at, plant, item_code / description, quantity, need_by_date, urgency…" />
        <Next>{file ? <>press <b>Process batch</b>.</> : <>drop a PR batch CSV below or browse for one.</>}</Next>
        <div className="upload-grid">
          <FileDrop id="batch-file" accept={['.csv']} file={file} onFile={setFile} busy={busy && !!file} busyLabel="Processing batch…"
            title="Drag & drop your PR batch CSV" />
          <div className="upload-side">
            <label className="field"><span>Policy version</span>
              <select value={ver} onChange={(e) => setVer(e.target.value)}>
                <option value="">By effective date (default)</option>
                {versions.map((v) => <option key={v.id} value={v.version}>Force v{v.version} (effective {v.effective_from})</option>)}
              </select>
            </label>
            <Button variant="primary" icon="zap" loading={busy && !!file} disabled={!file || busy} onClick={process}>Process batch</Button>
            <span className="muted small">Tip: try <span className="mono">data/pr_batches/sample_pr_batch.csv</span></span>
          </div>
        </div>
      </section>

      {!current && batches?.length === 0 && (
        <section className="card" aria-label="How it works">
          <div className="steps">
            {STEPS.map(([icon, t, d], i) => (
              <div key={t} className="step"><div className="n"><Icon name={icon} size={16} /></div><div><b>{i + 1}. {t}</b><span>{d}</span></div></div>
            ))}
          </div>
        </section>
      )}

      {current && (
        <section aria-label="Batch results">
          <div className="result-head">
            <div className="grow">
              <h3>Batch #{current.batch_id}{current.name ? ` · ${current.name}` : ''}</h3>
              <div className="flow small">
                <span><Icon name="list" size={14} />{current.summary.lines} lines</span><Icon name="chevronRight" size={14} />
                <span><Icon name="layers" size={14} />{current.summary.requirements} requirements</span><Icon name="chevronRight" size={14} />
                <span><Icon name="fileSign" size={14} />{current.summary.pos} POs</span>
                <span className="chip gray">policy v{current.summary.policy_versions.join(', v')}</span>
              </div>
            </div>
            <div className="actions">
              <Button icon="refresh" loading={busy && !file} disabled={busy} onClick={() => reprocess(current.batch_id)}>Reprocess</Button>
              <Link className="btn" to="/workspace"><Icon name="inbox" size={16} />Open in workspace</Link>
              <Button variant="primary" icon="download" loading={exporting} onClick={exportCsv}>Export CSV</Button>
            </div>
          </div>
          <div className="kpis">
            <Kpi icon="list" value={current.summary.lines} label="All lines" onClick={() => setFilter('')} on={!filter} />
            {Object.entries(current.summary.routes).map(([r, n]) => {
              const [icon, tone] = ROUTE_ICON[r] || ['file', '']
              return <Kpi key={r} icon={icon} tone={tone} value={n} label={ROUTE_LABEL[r] || r} onClick={() => setFilter(filter === r ? '' : r)} on={filter === r} />
            })}
          </div>
          <div className="card flush">
            <div className="toolbar">
              <div className="search grow"><Icon name="search" size={16} /><input aria-label="Search decisions" placeholder="Search PR, item, supplier, reason…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
              {filter && <button className="chip filter-chip" onClick={() => setFilter('')}>{ROUTE_LABEL[filter] || filter}<Icon name="close" size={12} /></button>}
              <span className="muted small">{rows.length} of {current.decisions.length} lines</span>
            </div>
            <div className="tablewrap scroll">
              <table aria-label="Decisions">
                <thead><tr><th>PR / line</th><th>Item</th><th>Group</th><th>PO</th><th>Route</th><th>Supplier / suggested</th><th className="num">Unit price</th><th className="num">Group value</th><th>Reason</th></tr></thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={`${r.pr_no}/${r.pr_line}`}>
                      <td className="mono nowrap">{r.pr_no}/{r.pr_line}</td><td className="mono">{r.resolved_item_code || '–'}</td><td className="mono">{r.group_id || '–'}</td><td className="mono">{r.po_id || '–'}</td>
                      <td><RouteChip route={r.route} /></td>
                      <td className="mono">{r.supplier_id || r.suggested_supplier_ids || '–'}</td>
                      <td className="num">{inr(r.unit_price) || '–'}</td><td className="num">{inr(r.group_value_inr) || '–'}</td>
                      <td className="small" style={{ minWidth: 320 }}>{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && <Empty icon="search" title="No lines match">Clear the filter or search.</Empty>}
            </div>
            <div className="pager"><span className="muted small">Page {page + 1} of {pages}</span>
              <div className="row"><Button size="sm" icon="chevronLeft" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><Button size="sm" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next<Icon name="chevronRight" size={14} /></Button></div></div>
          </div>
        </section>
      )}

      <section className="card flush" aria-label="Earlier batches">
        <div className="pad-head"><SectionHead icon="history" title="Earlier batches" sub="Open one to see its decisions again." /></div>
        {batches === null ? <SkeletonTable rows={3} cols={7} /> : batches.length === 0 ? <Empty icon="layers" title="No batches yet">Upload your first PR batch above.</Empty> : (
          <div className="tablewrap"><table aria-label="Batches">
            <thead><tr><th>#</th><th>Name</th><th>Kind</th><th className="num">Lines</th><th>Policy</th><th>Processed</th><th /></tr></thead>
            <tbody>{batches.map((b) => (
              <tr key={b.id} className={current?.batch_id === b.id ? 'sel' : ''}><td className="mono">{b.id}</td><td>{b.name}</td>
                <td><span className="chip gray"><Icon name={b.kind === 'chat' ? 'chat' : 'sheet'} size={12} />{b.kind}</span></td>
                <td className="num">{b.summary?.lines}</td><td>v{b.summary?.policy_versions?.join(', v')}</td><td className="small">{String(b.processed_at || '').replace('T', ' ')}</td>
                <td>{current?.batch_id === b.id ? <span className="chip po"><i />Showing</span> : <Button size="sm" icon="arrow" onClick={() => open(b.id)}>View</Button>}</td></tr>))}</tbody>
          </table></div>
        )}
      </section>
    </div>
  )
}
