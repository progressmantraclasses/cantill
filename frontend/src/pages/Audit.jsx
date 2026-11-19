import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { Empty, Err, Icon, PageHeader, Skeleton } from '../components.jsx'

function summarize(a) {
  const d = a.detail || {}
  switch (a.action) {
    case 'process_batch': case 'reprocess_batch': return d.lines != null ? `${d.lines} lines → ${d.requirements} requirements, ${d.pos} POs · policy v${(d.policy_versions || []).join(', v')}` : null
    case 'approve': return `Created ${d.kind || 'document'} ${d.document || ''} · rule ${d.rule || ''} · policy v${d.policy_version || ''}`
    case 'override': return d.from && d.to ? `${d.from.route} → ${d.to.route}${d.to.supplier_id ? ' · ' + d.to.supplier_id : ''}` : null
    case 'policy_approved': return `Effective ${d.effective_from} · ${d.changes} change(s)`
    case 'policy_draft_created': return `Source: ${d.source}`
    case 'raise_pr': return `Route ${d.route}`
    case 'add_contract': return `Source: ${d.source}`
    default: return null
  }
}

const KIND = { approve: 'po', override: 'warn', policy_approved: 'po', policy_rejected: 'bad' }

export default function Audit() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  useEffect(() => { api.get('/api/audit').then(setRows).catch((e) => { setError(e); setRows([]) }) }, [])
  const shown = useMemo(() => (rows || []).filter((a) => !q || `${a.actor} ${a.action} ${a.entity} ${a.comment || ''}`.toLowerCase().includes(q.toLowerCase())), [rows, q])
  return (
    <div>
      <PageHeader title="Audit log" subtitle="Every action with who and when. Overrides keep the original decision and the written reason." />
      <Err e={error} />
      <section className="card flush">
        <div className="row" style={{ padding: 12 }}>
          <div className="search grow"><Icon name="search" size={16} /><input aria-label="Search audit log" placeholder="Search actor, action, entity, comment…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <span className="muted small">{shown.length} {shown.length === 1 ? 'entry' : 'entries'}</span>
        </div>
        {rows === null ? <div style={{ padding: 16 }}><Skeleton rows={6} /></div> : !shown.length ? <Empty icon="history" title="Nothing recorded yet">Actions appear here as people use the app.</Empty> : (
          <div className="tablewrap scroll" style={{ maxHeight: '70vh' }}>
            <table aria-label="Audit log">
              <thead><tr><th>When</th><th>Who</th><th>Action</th><th>On</th><th>Comment / detail</th></tr></thead>
              <tbody>{shown.map((a) => (
                <tr key={a.id}><td className="small nowrap">{String(a.at).replace('T', ' ')}</td>
                  <td>{a.actor} <span className="muted small">({a.role})</span></td>
                  <td><span className={`chip ${KIND[a.action] || 'gray'}`}>{a.action.replace(/_/g, ' ')}</span></td>
                  <td className="small">{a.entity}</td>
                  <td className="small" style={{ minWidth: 240 }}>{a.comment && <div>“{a.comment}”</div>}{summarize(a) ? <span className="muted">{summarize(a)}</span> : a.detail && <span className="muted mono">{JSON.stringify(a.detail).slice(0, 160)}</span>}</td></tr>))}</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
