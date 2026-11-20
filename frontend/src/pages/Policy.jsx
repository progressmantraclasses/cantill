import React, { useEffect, useState } from 'react'
import { api, session } from '../api.js'
import { Banner, Button, ConfirmButton, Empty, Err, Field, FileDrop, Next, PageHeader, RoleNotice, SectionHead, Skeleton, SkeletonTable, Tabs } from '../components.jsx'

export default function Policy() {
  const [versions, setVersions] = useState(null)
  const [active, setActive] = useState(null)
  const [draft, setDraft] = useState(null)
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [eff, setEff] = useState('')
  const [tab, setTab] = useState('changes')
  const [json, setJson] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [note, setNote] = useState(null)
  const isProc = session.role === 'Procurement'

  const load = () => {
    api.get('/api/policies').then(setVersions).catch(setError)
    api.get('/api/policies/active').then(setActive).catch(setError)
  }
  useEffect(load, [])

  async function propose() {
    setBusy(true); setError(null); setNote(null)
    try {
      const d = file ? await api.upload('/api/policies/drafts', file, eff ? { effective_from: eff } : {}) : await api.post('/api/policies/drafts', { text, effective_from: eff || undefined })
      setDraft(d); setJson(JSON.stringify(d.document, null, 2)); setTab('changes'); setNote(d.warnings || null); setFile(null); setText('')
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function saveJson() {
    let doc
    try { doc = JSON.parse(json) } catch (e) { setError(new Error(`The JSON is not valid: ${e.message}`)); return }
    setBusy(true); setError(null)
    try { const d = await api.patch(`/api/policies/drafts/${draft.id}`, { document: doc }); setDraft(d); setJson(JSON.stringify(d.document, null, 2)); setTab('changes') }
    catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function manualFromActive() {
    if (!active) return
    const d = JSON.parse(JSON.stringify(active.document))
    d.version = bump(d.version); d.effective_from = eff || new Date().toISOString().slice(0, 10)
    setBusy(true); setError(null)
    try { const r = await api.post('/api/policies/drafts', { document: d }); setDraft(r); setJson(JSON.stringify(r.document, null, 2)); setTab('json') } catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function approve() {
    setBusy(true); setError(null)
    try { await api.post(`/api/policies/drafts/${draft.id}/approve`); setNote(`Policy v${draft.version} approved. It applies to requirements dated ${draft.effective_from} or later.`); setDraft(null); load() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function review(id) {
    setError(null)
    try { const d = await api.get(`/api/policies/${id}`); setDraft(d); setJson(JSON.stringify(d.document, null, 2)); setTab('changes'); window.scrollTo({ top: 0, behavior: 'smooth' }) } catch (e) { setError(e) }
  }
  async function reject() {
    setBusy(true); setError(null)
    try { await api.post(`/api/policies/drafts/${draft.id}/reject`); setNote(`Draft v${draft.version} discarded.`); setDraft(null); load() } catch (e) { setError(e) } finally { setBusy(false) }
  }

  return (
    <div>
      <PageHeader icon="shield" title="Policy" subtitle="Rules live as versioned data. Upload an amendment or describe a change, review it in plain language, then approve to activate it from its effective date. No code change, no redeploy." />
      <Err e={error} />
      {note && !draft && <Banner kind="ok">{note}</Banner>}
      <RoleNotice role={session.role} allowed={['Procurement']} action="change the policy" />

      {!draft && isProc && (
        <section className="card" aria-label="Propose change">
          <SectionHead icon="sparkles" title="Propose a policy change" sub="The reader turns the amendment into rule changes. Nothing is active until you approve it." />
          <Next>upload an amendment (PDF, DOCX, TXT) or describe the change, then press <b>Read amendment</b>.</Next>
          <div className="upload-grid">
            <FileDrop id="policy-file" accept={['.pdf', '.docx', '.txt', '.md']} file={file} onFile={setFile} busy={busy && !!file}
              busyLabel="Reading amendment…" title="Drag & drop the amendment document" />
            <div className="upload-side">
              <Field label="Effective date (if the document has none)"><input type="date" value={eff} onChange={(e) => setEff(e.target.value)} /></Field>
            </div>
          </div>
          <div className="or-divider"><span>or describe it</span></div>
          <div><Field label="Describe the change in plain language">
            <textarea placeholder="e.g. From 1 Dec 2026 the spot PO limit is ₹1,50,000, and at Chakan plant Safety & PPE under ₹50,000 is always a spot PO." value={text} onChange={(e) => setText(e.target.value)} /></Field></div>
          <div className="row" style={{ marginTop: 12 }}>
            <Button variant="primary" icon="sparkles" loading={busy} disabled={!file && !text.trim()} onClick={propose}>{busy ? 'Reading…' : 'Read amendment'}</Button>
            <Button icon="edit" disabled={busy || !active} onClick={manualFromActive}>Edit rules manually</Button>
          </div>
        </section>
      )}

      {draft && (
        <section className="card flush" aria-label="Draft review">
          <div style={{ padding: 16 }}>
            <div className="row"><div className="grow"><h3 style={{ fontSize: 17 }}>Proposed v{draft.version}</h3><div className="muted small">Effective {draft.effective_from} · based on v{draft.base_version} · <span className="chip warn"><i />Draft, not active</span></div></div>
              <ConfirmButton confirmLabel="Discard draft" loading={busy} onConfirm={reject}>Discard</ConfirmButton></div>
            {note && <div style={{ marginTop: 10 }}><Banner kind="info">Reader note: {note}</Banner></div>}
          </div>
          <Tabs label="Draft sections" value={tab} onChange={setTab} tabs={[['changes', `What will change (${draft.changes.length})`], ['impact', 'Impact on latest batch'], ['json', 'Edit as JSON']]} />
          <div style={{ padding: 16 }}>
            {tab === 'changes' && (draft.changes.length ? draft.changes.map((c, i) => <div key={i} className={`change ${c.kind}`}>{c.text}</div>) : <Empty icon="info" title="No differences">This draft is identical to the current policy.</Empty>)}
            {tab === 'impact' && (draft.impact?.lines != null ? <div>
              <p style={{ marginTop: 0 }}><b>{draft.impact.lines_changed}</b> of {draft.impact.lines} lines in batch #{draft.impact.batch_id} would change.</p>
              {Object.entries(draft.impact.moves).map(([k, v]) => <div key={k} className="change">{k}: <b>{v}</b> lines</div>)}
              {draft.impact.lines_changed === 0 && <div className="muted">No decisions change for that batch.</div>}
            </div> : <Empty icon="layers" title="No preview available">{draft.impact?.error || 'Upload a PR batch first to preview the impact.'}</Empty>)}
            {tab === 'json' && <>
              <textarea aria-label="Policy JSON" spellCheck={false} style={{ minHeight: 340, fontFamily: 'var(--mono)', fontSize: 12 }} value={json} onChange={(e) => setJson(e.target.value)} />
              <div className="row" style={{ marginTop: 10 }}><Button icon="shieldCheck" loading={busy} onClick={saveJson}>Validate & update preview</Button></div></>}
          </div>
          <div className="pager"><span className="muted small">Approving activates this version for requirements dated {draft.effective_from} or later.</span>
            <Button variant="primary" icon="check" loading={busy} onClick={approve}>Approve and activate</Button></div>
        </section>
      )}

      <div className="split">
        <section className="card" aria-label="Active rules">
          <SectionHead icon="shieldCheck" title={`Active rules${active ? ` · v${active.version}` : ''}`} sub="First matching rule wins, from top to bottom." />
          {!active ? <Skeleton rows={6} heading={false} /> : active.rules_text.map((r, i) => <div key={r.id} className="change"><b>{i + 1}. Rule {r.id}</b> · {r.title}<div className="small muted">{r.text}</div></div>)}
        </section>
        <section className="card flush" aria-label="Versions">
          <div className="pad-head"><SectionHead icon="history" title="Version history" /></div>
          {!versions ? <SkeletonTable rows={3} cols={5} /> : (
            <div className="tablewrap"><table aria-label="Versions"><thead><tr><th>Version</th><th>Effective</th><th>Status</th><th>By</th><th /></tr></thead>
              <tbody>{versions.map((v) => <tr key={v.id}><td><b>v{v.version}</b>{v.is_active && <span className="chip po" style={{ marginLeft: 6 }}><i />Active</span>}</td><td>{v.effective_from}</td>
                <td><span className={`chip ${v.status === 'approved' ? 'po' : v.status === 'rejected' ? 'bad' : 'warn'}`}>{v.status}</span></td>
                <td className="small">{v.approved_by || v.created_by}<div className="muted">{v.source_kind}{v.change_count ? ` · ${v.change_count} changes` : ''}</div></td>
                <td>{v.status === 'draft' && isProc && <Button size="sm" icon="arrow" onClick={() => review(v.id)}>Review</Button>}</td></tr>)}</tbody></table></div>
          )}
        </section>
      </div>
    </div>
  )
}

function bump(v) { const p = v.split('.'); return `${p[0]}.${(parseInt(p[1] || '0', 10) + 1)}` }
