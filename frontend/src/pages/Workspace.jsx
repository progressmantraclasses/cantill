import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, inr, ROUTE_LABEL } from '../api.js'
import { Banner, Button, Empty, Err, Field, Icon, Kpi, PageHeader, RouteChip, Skeleton, Tabs } from '../components.jsx'

const ROUTES = ['CONTRACT_PO', 'EMERGENCY_PO', 'SPOT_PO', 'RFQ', 'RFP', 'CAPEX_SOURCING', 'NEW_ITEM_SOURCING']

export default function Workspace() {
  const [batches, setBatches] = useState(null)
  const [bid, setBid] = useState(null)
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(null)
  const [filter, setFilter] = useState('pending')
  const [routeF, setRouteF] = useState('')
  const [q, setQ] = useState('')
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState(null)
  const [params, setParams] = useSearchParams()

  useEffect(() => { api.get('/api/batches').then((b) => { setBatches(b); if (b[0]) setBid(b[0].id) }).catch((e) => { setError(e); setBatches([]) }) }, [])
  const load = (id = bid) => id && api.get(`/api/requirements?batch_id=${id}`).then(setData).catch(setError)
  useEffect(() => { setSel(null); setData(null); load() }, [bid])
  // deep link: /workspace?req=REQ-0007 opens that requirement
  useEffect(() => {
    const want = params.get('req')
    if (data && want) { const r = data.requirements.find((x) => x.group_id === want); if (r) { setSel(r.key); setFilter('all') } }
  }, [data])

  const all = data?.requirements || []
  const counts = useMemo(() => ({
    pending: all.filter((r) => r.status === 'pending').length,
    done: all.filter((r) => r.status !== 'pending').length,
    po: all.filter((r) => r.decision === 'PO').length,
    src: all.filter((r) => r.decision !== 'PO').length,
    flagged: all.filter((r) => r.flags.length).length,
  }), [all])
  const reqs = all.filter((r) =>
    (filter === 'all' || (filter === 'pending' ? r.status === 'pending' : r.status !== 'pending')) &&
    (!routeF || r.route === routeF) &&
    (!q || `${r.group_id} ${r.item_code} ${r.item_description} ${r.supplier_id} ${r.plant}`.toLowerCase().includes(q.toLowerCase())))
  const cur = all.find((r) => r.key === sel)
  const usedRoutes = [...new Set(all.map((r) => r.route))]

  async function approve() {
    setError(null)
    try { const r = await api.post('/api/requirements/approve', { batch_id: bid, key: cur.key }); setMsg(`Created ${r.kind} ${r.document_id}`); await load() } catch (e) { setError(e) }
  }
  const pick = (r) => { setSel(r.key); setMsg(null); setParams({ req: r.group_id }, { replace: true }) }

  return (
    <div>
      <PageHeader title="Buyer workspace" subtitle="Each requirement groups the PR lines that policy clubs together. Review the decision and its reason, then approve it or override it with a comment.">
        {batches?.length > 0 && <label className="field"><span>Batch</span>
          <select value={bid || ''} onChange={(e) => setBid(Number(e.target.value))}>
            {batches.map((b) => <option key={b.id} value={b.id}>#{b.id} · {b.name} ({b.summary?.requirements} requirements)</option>)}
          </select></label>}
      </PageHeader>
      <Err e={error} />
      {msg && <Banner kind="ok">{msg}</Banner>}

      {batches?.length === 0 && <div className="card"><Empty icon="inbox" title="Nothing to review yet">Upload a PR batch or raise a request in chat.</Empty></div>}

      {data && (
        <>
          <div className="kpis">
            <Kpi value={counts.pending} label="Awaiting action" onClick={() => setFilter('pending')} on={filter === 'pending'} />
            <Kpi value={counts.done} label="Actioned" onClick={() => setFilter('done')} on={filter === 'done'} />
            <Kpi value={all.length} label="All requirements" onClick={() => setFilter('all')} on={filter === 'all'} />
            <Kpi value={counts.po} label="Purchase orders" />
            <Kpi value={counts.src} label="Sourcing requests" />
            <Kpi value={counts.flagged} label="With warnings" />
          </div>
          <div className="split">
            <section className="card flush" aria-label="Requirements">
              <div className="row" style={{ padding: 12 }}>
                <div className="search grow"><Icon name="search" size={16} /><input aria-label="Search requirements" placeholder="Search item, plant, supplier…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
                <select aria-label="Filter by route" value={routeF} onChange={(e) => setRouteF(e.target.value)}>
                  <option value="">All routes</option>{usedRoutes.map((r) => <option key={r} value={r}>{ROUTE_LABEL[r] || r}</option>)}
                </select>
              </div>
              <div className="tablewrap scroll" style={{ maxHeight: '68vh' }}>
                <table aria-label="Requirement list">
                  <thead><tr><th>Req</th><th>Item</th><th>Route</th><th className="num">Value</th><th aria-label="Status" /></tr></thead>
                  <tbody>
                    {reqs.map((r) => (
                      <tr key={r.key} className={`click ${sel === r.key ? 'sel' : ''}`} tabIndex={0} aria-selected={sel === r.key}
                        onClick={() => pick(r)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(r) } }}>
                        <td className="mono nowrap">{r.group_id}{r.lines.length > 1 && <div className="muted">{r.lines.length} lines</div>}</td>
                        <td><div className="req-cell"><span className="t" title={r.item_description}>{r.item_description || r.item_code}</span><span className="small muted"><span className="mono">{r.item_code}</span> · {r.plant}</span></div></td>
                        <td><div className="chips wrapok"><RouteChip route={r.route} />{r.is_emergency && <span className="chip bad">Urgent</span>}{r.flags.length > 0 && <span title={r.flags.join(' · ')} style={{ color: 'var(--accent)' }}><Icon name="alert" size={15} /></span>}</div></td>
                        <td className="num nowrap">{inr(r.value)}</td>
                        <td title={r.status === 'pending' ? 'Pending' : r.status}><span className={`dot ${r.status === 'pending' ? '' : 'ok'}`} /><span className="sr-only">{r.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!reqs.length && <Empty icon="check" title={filter === 'pending' ? 'All caught up' : 'No requirements match'}>{filter === 'pending' ? 'Nothing is waiting for action in this batch.' : 'Change the filters above.'}</Empty>}
              </div>
              <div className="pager"><span className="muted small">{reqs.length} shown</span><span className="legend"><span><span className="dot" /> pending</span><span><span className="dot ok" /> actioned</span><span><Icon name="alert" size={13} /> has warnings</span></span></div>
            </section>
            {cur ? <Detail r={cur} bid={bid} approve={approve} reload={load} setError={setError} setMsg={setMsg} /> :
              <div className="card"><Empty icon="inbox" title="Select a requirement">Pick a row on the left to see the decision, the policy clause and the suppliers behind it.</Empty></div>}
          </div>
        </>
      )}
      {batches && batches.length > 0 && !data && !error && <div className="card"><Skeleton rows={6} /></div>}
    </div>
  )
}

function Detail({ r, bid, approve, reload, setError, setMsg }) {
  const [tab, setTab] = useState('overview')
  const [override, setOverride] = useState(false)
  const [route, setRoute] = useState(r.route)
  const [supplier, setSupplier] = useState('')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setTab('overview'); setOverride(false); setRoute(r.route); setSupplier(r.supplier_id || ''); setComment('') }, [r.key])
  const isPO = route.endsWith('_PO')
  const actioned = r.review
  const supplierList = r.decision === 'PO' ? null : r.suggested

  async function doApprove() { setBusy(true); try { await approve() } finally { setBusy(false) } }
  async function submitOverride() {
    setError(null); setBusy(true)
    try { const x = await api.post('/api/requirements/override', { batch_id: bid, key: r.key, route, supplier_id: isPO ? supplier : null, comment }); setMsg(`Override recorded: ${x.document_id}`); setOverride(false); await reload() } catch (e) { setError(e) } finally { setBusy(false) }
  }

  return (
    <section className="card detail" aria-label={`Requirement ${r.group_id}`}>
      <div className="detail-head">
        <div className="row"><h3 className="grow" style={{ fontSize: 17 }}>{r.item_description || r.item_code}</h3><RouteChip route={r.route} /></div>
        <div className="muted small"><span className="mono">{r.group_id}</span> · <span className="mono">{r.item_code}</span> · {r.plant} · requirement date {r.date}</div>
        <div className="kv" style={{ marginBottom: 4 }}>
          <div>Value</div><div><b style={{ fontSize: 16 }}>{inr(r.value)}</b> <span className="muted small">{r.quantity} {r.uom || ''} × {inr(r.unit_price)} · {r.price_source}</span></div>
          {r.decision === 'PO' ? <><div>Supplier</div><div><b className="mono">{r.supplier_id}</b> {r.supplier_name} @ {inr(r.unit_price)} <span className="muted small">· {r.po_id}</span></div></> :
            supplierList.length > 0 ? <><div>Suggested</div><div>{supplierList.map((s, i) => <div key={s.supplier_id}>{i + 1}. <b className="mono">{s.supplier_id}</b> {s.name} <span className="muted small">({s.source})</span></div>)}</div></> :
              <><div>Suppliers</div><div className="muted">{r.route === 'NEW_ITEM_SOURCING' ? 'None: the buyer finds suppliers for a new item.' : 'None available.'}</div></>}
          <div>Clause</div><div>Rule <b>{r.rule_id}</b> · policy v{r.policy_version}</div>
        </div>
      </div>

      <Tabs label="Requirement sections" value={tab} onChange={setTab} tabs={[['overview', 'Why'], ['lines', `PR lines (${r.lines.length})`], ['contracts', `Contracts (${r.contract_report.length})`], ['suppliers', `Suppliers (${r.preferred.length})`]]} />
      <div className="pad">
        {tab === 'overview' && (
          <>
            <div className="why"><b>Why this decision:</b> {r.reason}</div>
            {r.relied_on && <div className="small muted" style={{ marginBottom: 8 }}>Relied on: {r.relied_on}</div>}
            {r.flags.length > 0 && <div className="chips">{r.flags.map((f, i) => <span key={i} className="chip warn wrap"><Icon name="alert" size={13} />{f}</span>)}</div>}
            {r.skipped_rules?.length > 0 && <Banner kind="info">{r.skipped_rules.join('; ')}</Banner>}
          </>
        )}
        {tab === 'lines' && (
          <div className="tablewrap"><table className="tight" aria-label="PR lines"><thead><tr><th>PR / line</th><th>Created</th><th className="num">Qty</th><th>Need by</th><th>Matched by</th></tr></thead>
            <tbody>{r.lines.map((l) => <tr key={l.pr_no + l.pr_line}><td className="mono nowrap">{l.pr_no}/{l.pr_line}</td><td className="small">{l.created_at}</td><td className="num">{l.quantity}</td><td>{l.need_by}</td>
              <td className="small">{l.match_method.replace('_', ' ')}{l.urgency === 'Emergency' && <span className="chip bad" style={{ marginLeft: 4 }}>Emergency</span>}</td></tr>)}</tbody></table></div>
        )}
        {tab === 'contracts' && (r.contract_report.length ? (
          <div className="tablewrap"><table className="tight" aria-label="Contracts considered"><thead><tr><th>Contract</th><th className="num">Rate</th><th className="num">Ceiling left</th><th className="num">Needs</th><th>Result</th></tr></thead>
            <tbody>{r.contract_report.map((c) => <tr key={c.contract_id}><td className="mono">{c.contract_id}</td><td className="num">{inr(c.rate)}</td><td className="num">{inr(c.ceiling_left)}</td><td className="num">{inr(c.needs)}</td><td>{c.usable ? <span className="chip po"><i />Usable</span> : <span className="chip bad"><i />No ceiling</span>}</td></tr>)}</tbody></table></div>
        ) : <Empty icon="file" title="No applicable contract">No active rate contract covers this item on {r.date}.</Empty>)}
        {tab === 'suppliers' && (r.preferred.length ? (
          <div className="tablewrap"><table className="tight" aria-label="Preferred suppliers"><thead><tr><th>#</th><th>Supplier</th><th className="num">POs</th><th>Last PO</th><th>Contract</th><th className="num">On-time</th><th className="num">Qual.</th><th>Score</th></tr></thead>
            <tbody>{r.preferred.map((p) => <tr key={p.supplier_id}><td>{p.rank}</td><td><b className="mono">{p.supplier_id}</b><div className="small muted">{p.name}</div></td><td className="num">{p.po_count}</td><td className="small">{p.last_po_date || '–'}</td><td>{p.has_contract ? 'Yes' : 'No'}</td><td className="num">{p.on_time_pct}%</td><td className="num">{p.quality}</td>
              <td style={{ minWidth: 90 }}><b>{p.score}</b><div className="score-bar" aria-hidden="true"><i style={{ width: `${Math.min(100, p.score * 100)}%` }} /></div></td></tr>)}</tbody></table></div>
        ) : <Empty icon="star" title="No preferred supplier">Nobody on the list: no PO in 548 days and no contract.</Empty>)}

        <div className="sticky-actions">
          {actioned ? (
            <Banner kind="ok">
              <b>{actioned.status === 'approved' ? 'Approved' : 'Overridden'}</b> by {actioned.actor} · {String(actioned.at || '').replace('T', ' ')} → <b className="mono">{actioned.document_id}</b>
              {actioned.comment && <div>“{actioned.comment}”</div>}
              {actioned.override && <div className="small">Changed to {actioned.override.route} {actioned.override.supplier_id || ''}. System decision kept: {actioned.original.route}.</div>}
            </Banner>
          ) : override ? (
            <div>
              <h4 style={{ marginTop: 0 }}>Override decision</h4>
              <div className="row">
                <Field label="New route"><select value={route} onChange={(e) => setRoute(e.target.value)}>{ROUTES.map((x) => <option key={x} value={x}>{ROUTE_LABEL[x]}</option>)}</select></Field>
                {isPO && <Field label="Supplier (Active only)"><input value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="e.g. S014" /></Field>}
              </div>
              <Field label="Reason (required, kept with the original decision)"><textarea value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
              <div className="row" style={{ marginTop: 10 }}><Button variant="primary" loading={busy} disabled={comment.trim().length < 5} onClick={submitOverride}>Save override</Button><Button onClick={() => setOverride(false)}>Cancel</Button></div>
            </div>
          ) : (
            <div className="row">
              <Button variant="primary" icon="check" loading={busy} onClick={doApprove}>{r.decision === 'PO' ? 'Approve & create PO' : `Approve & create ${r.route === 'CAPEX_SOURCING' ? 'capex request' : r.route === 'NEW_ITEM_SOURCING' ? 'sourcing request' : r.route}`}</Button>
              <Button onClick={() => setOverride(true)}>Override…</Button>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
