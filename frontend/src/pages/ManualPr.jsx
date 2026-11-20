import React, { useEffect, useMemo, useState } from 'react'
import { api, inr } from '../api.js'
import { Button, Err, Field, Icon, SectionHead } from '../components.jsx'

const isoDay = (offset = 0) => new Date(Date.now() + offset * 864e5).toISOString().slice(0, 10)
const EMPTY = { item_code: '', is_new: false, description: '', uom: 'NOS', quantity: '', plant: '', need_by: isoDay(7), urgency: 'Normal', est_unit_price: '' }

function validate(f, item) {
  const p = []
  if (f.is_new ? f.description.trim().length < 3 : !item) p.push(f.is_new ? 'Describe the new item (at least 3 characters).' : 'Choose an item from the item master.')
  if (!(Number(f.quantity) > 0)) p.push('Quantity must be greater than zero.')
  if (!f.plant) p.push('Choose a plant.')
  if (!f.need_by) p.push('Choose a need-by date.')
  else if (f.need_by < isoDay()) p.push('Need-by date cannot be in the past.')
  if (f.est_unit_price !== '' && !(Number(f.est_unit_price) >= 0)) p.push('Estimated unit price must be a number.')
  return p
}

/** Form alternative to the chat: the same fields the assistant collects, sent to POST /api/prs. */
export default function ManualPr({ onRaised, onCancel }) {
  const [form, setForm] = useState(EMPTY)
  const [items, setItems] = useState([])
  const [plants, setPlants] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [problems, setProblems] = useState([])
  const [query, setQuery] = useState('')

  useEffect(() => {
    api.get('/api/items').then(setItems).catch(setError)
    api.get('/api/plants').then((p) => { setPlants(p); if (p.length === 1) setForm((f) => ({ ...f, plant: p[0].code })) }).catch(setError)
  }, [])

  const item = items.find((i) => i.item_code === form.item_code)
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (q ? items.filter((i) => `${i.item_code} ${i.description} ${i.category}`.toLowerCase().includes(q)) : items).slice(0, 8)
  }, [items, query])
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const estValue = (Number(form.quantity) || 0) * (form.is_new ? Number(form.est_unit_price) || 0 : item?.standard_price || 0)

  async function submit(e) {
    e.preventDefault()
    const found = validate(form, item)
    setProblems(found)
    if (found.length) return
    setBusy(true); setError(null)
    try {
      const body = { ...form, item_code: form.is_new ? '' : form.item_code, quantity: Number(form.quantity),
        est_unit_price: form.est_unit_price === '' ? null : Number(form.est_unit_price) }
      onRaised(await api.post('/api/prs', body))
      setForm(EMPTY); setQuery('')
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <section className="card" aria-label="Raise a PR manually">
      <SectionHead icon="edit" title="Raise a PR manually" sub="Fill in the request yourself. Policy decides it exactly as it would for the chat or a CSV batch.">
        <Button variant="ghost" icon="chat" onClick={onCancel}>Back to chat</Button>
      </SectionHead>
      <form onSubmit={submit} noValidate>
        <div className="form-section">
          <div className="form-section-title"><Icon name="package" size={15} />Item</div>
          <label className="check"><input type="checkbox" checked={form.is_new} onChange={set('is_new')} />This is a new item (not in the item master)</label>
          {form.is_new ? (
            <div className="form-grid">
              <Field label="Item description"><input value={form.description} onChange={set('description')} placeholder="e.g. Custom welding jig for line 3" /></Field>
              <Field label="Unit of measure"><input value={form.uom} onChange={set('uom')} placeholder="NOS" maxLength={16} /></Field>
              <Field label="Estimated unit price (₹)" hint="Optional. The buyer estimates it if empty."><input value={form.est_unit_price} onChange={set('est_unit_price')} inputMode="decimal" placeholder="4500" /></Field>
            </div>
          ) : (
            <div className="item-picker">
              <div className="search"><Icon name="search" size={16} /><input aria-label="Search items" placeholder="Search by code, name or category…" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
              <div className="item-options" role="listbox" aria-label="Items">
                {matches.map((i) => (
                  <button type="button" key={i.item_code} role="option" aria-selected={form.item_code === i.item_code}
                    className={`item-option ${form.item_code === i.item_code ? 'on' : ''}`} onClick={() => setForm({ ...form, item_code: i.item_code })}>
                    <code className="rt-tag item">{i.item_code}</code>
                    <span className="grow">{i.description}<span className="muted small"> · {i.category}</span></span>
                    <span className="muted small nowrap">{i.uom} · {inr(i.standard_price)}</span>
                    {form.item_code === i.item_code && <Icon name="tick" size={16} />}
                  </button>
                ))}
                {!matches.length && <div className="muted small" style={{ padding: 10 }}>No item matches “{query}”. Tick “new item” above if it is not in the master.</div>}
              </div>
            </div>
          )}
        </div>

        <div className="form-section">
          <div className="form-section-title"><Icon name="cart" size={15} />Quantity and delivery</div>
          <div className="form-grid">
            <Field label={`Quantity${item && !form.is_new ? ` (${item.uom})` : form.is_new ? ` (${form.uom || 'NOS'})` : ''}`}>
              <input value={form.quantity} onChange={set('quantity')} inputMode="decimal" placeholder="e.g. 200" /></Field>
            <Field label="Plant">
              <select value={form.plant} onChange={set('plant')}>
                <option value="">Choose a plant…</option>
                {plants.map((p) => <option key={p.code} value={p.code}>{p.code} · {p.name}</option>)}
              </select></Field>
            <Field label="Need by"><input type="date" min={isoDay()} value={form.need_by} onChange={set('need_by')} /></Field>
          </div>
          <div className="seg" role="radiogroup" aria-label="Urgency">
            {['Normal', 'Emergency'].map((u) => (
              <button type="button" key={u} role="radio" aria-checked={form.urgency === u} className={`seg-btn ${form.urgency === u ? `on ${u === 'Emergency' ? 'bad' : ''}` : ''}`}
                onClick={() => setForm({ ...form, urgency: u })}><Icon name={u === 'Emergency' ? 'zap' : 'clock'} size={14} />{u}</button>
            ))}
          </div>
        </div>

        {problems.length > 0 && <div className="banner err" role="alert"><Icon name="x" size={18} /><div>{problems.join('\n')}</div></div>}
        <Err e={error} />
        <div className="form-foot">
          <span className="muted small">{estValue > 0 ? <>Estimated value <b className="rt-money">{inr(estValue)}</b> (the final price comes from contracts and policy)</> : 'The decision appears on the right once raised.'}</span>
          <Button variant="primary" icon="send" loading={busy}>Raise PR</Button>
        </div>
      </form>
    </section>
  )
}
