import React, { useEffect, useState } from 'react'
import { api, download, inr } from '../api.js'
import { Banner, Button, Empty, Err, Field, Icon, PageHeader, Skeleton } from '../components.jsx'

export default function Preferred() {
  const [asOf, setAsOf] = useState('2026-11-01')
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [q, setQ] = useState('')
  const [error, setError] = useState(null)
  useEffect(() => { setData(null); api.get(`/api/preferred-suppliers?as_of=${asOf}`).then(setData).catch(setError) }, [asOf])
  const codes = data ? Object.keys(data.detail).filter((c) => !q || (c + data.items[c].description + data.items[c].category).toLowerCase().includes(q.toLowerCase())) : []
  const w = data?.weights
  return (
    <div>
      <PageHeader title="Preferred suppliers" subtitle="Built from PO history (548 days) and contracts as of the date you choose. Blocked and Inactive suppliers never appear.">
        <Button variant="primary" icon="download" onClick={() => download(`/api/preferred-suppliers?as_of=${asOf}&format=csv`, `preferred_suppliers_${asOf}.csv`)}>Export top 3 as CSV</Button>
      </PageHeader>
      <Err e={error} />
      <section className="card" aria-label="Controls">
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <Field label="As of date"><input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></Field>
          <div className="search grow"><Icon name="search" size={16} /><input aria-label="Filter items" placeholder="Filter by item code, name or category…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        </div>
        {w && <div style={{ marginTop: 12 }}><Banner kind="info"><b>How the score works:</b> {Object.entries(w).map(([k, v]) => `${k.replace('_', ' ')} ×${v}`).join(' + ')}. PO count is relative to the busiest supplier for that item; recency is 1 (last PO ≤ 90 days), 0.5 (≤ 1 year) or 0; contract means it ever held a contract for the item; on-time and quality are scaled to 0–1. Ties go to the more recent PO.</Banner></div>}
      </section>

      {!data && !error && <div className="card"><Skeleton rows={8} /></div>}
      {data && !codes.length && <div className="card"><Empty icon="search" title="No items match">Try a different filter.</Empty></div>}
      {data && codes.length > 0 && (
        <section className="card flush" aria-label="Items">
          {codes.map((c) => {
            const list = data.detail[c]
            const isOpen = open === c
            return (
              <div key={c} style={{ borderBottom: '1px solid var(--line)' }}>
                <button className="btn ghost" style={{ width: '100%', justifyContent: 'flex-start', textAlign: 'left', borderRadius: 0, minHeight: 48 }} aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c)}>
                  <Icon name="arrow" size={14} style={{ transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform 150ms' }} />
                  <b className="mono">{c}</b><span className="grow" style={{ fontWeight: 400 }}>{data.items[c].description} <span className="muted small">· {data.items[c].category}</span></span>
                  {list.length ? <span className="chips">{list.slice(0, 3).map((p, i) => <span key={p.supplier_id} className={`chip ${i === 0 ? 'po' : 'gray'}`}>{i + 1} · {p.supplier_id}</span>)}</span> : <span className="chip warn">No preferred supplier</span>}
                </button>
                {isOpen && list.length > 0 && (
                  <div className="tablewrap" style={{ padding: '0 16px 14px' }}>
                    <table className="tight" aria-label={`Ranking for ${c}`}>
                      <thead><tr><th>Rank</th><th>Supplier</th><th className="num">POs</th><th>Last PO</th><th className="num">Recency</th><th>Contract</th><th className="num">On-time</th><th className="num">Quality</th><th className="num">Ref. price</th><th>Score</th></tr></thead>
                      <tbody>{list.map((p) => (
                        <tr key={p.supplier_id}><td><b>{p.rank}</b></td><td><span className="mono">{p.supplier_id}</span><div className="muted small">{p.name}</div></td><td className="num">{p.po_count}</td><td className="small">{p.last_po_date || '–'}</td><td className="num">{p.recency}</td>
                          <td className="small">{p.has_contract ? p.contract_id : 'No'}</td><td className="num">{p.on_time_pct}%</td><td className="num">{p.quality}</td>
                          <td className="num">{inr(p.reference_price)}<div className="small muted">{p.reference_source}</div></td>
                          <td style={{ minWidth: 90 }}><b>{p.score}</b><div className="score-bar" aria-hidden="true"><i style={{ width: `${Math.min(100, p.score * 100)}%` }} /></div></td></tr>))}</tbody>
                    </table>
                  </div>
                )}
              </div>
            )
          })}
        </section>
      )}
    </div>
  )
}
