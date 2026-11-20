import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, inr } from '../api.js'
import { Avatar, Banner, Button, Err, Icon, Next, PageHeader, RouteChip } from '../components.jsx'
import RichText from '../richText.jsx'
import ManualPr from './ManualPr.jsx'

const HELLO = { role: 'assistant', text: 'Hi! Tell me what you need, for example: “need 200 nitrile gloves for Chakan by next Friday”. I will ask for anything that is missing, and I only use items from the item master.' }
const EXAMPLES = ['need 200 nitrile gloves for Chakan by next Friday', 'brg 6205 2rs 50 nos for Pune by 28 Nov', 'need 2 ultrasonic thickness gauge for Chakan by 10 Dec']

const initialsOf = (name) => (name || 'You').split(/\s+/).map((s) => s[0]).join('').slice(0, 2).toUpperCase()

/** Compact decision summary shown inside the "PR raised" message. */
function DecisionCard({ d }) {
  return (
    <div className="msg-decision">
      <div className="row"><RouteChip route={d.route} /><span className="grow" /><b className="rt-money">{inr(d.value)}</b></div>
      <div className="msg-decision-kv">
        {d.supplier_id && <><span>Supplier</span><span><code className="rt-tag">{d.supplier_id}</code> {d.supplier_name}</span></>}
        {d.unit_price != null && d.unit_price !== '' && <><span>Unit price</span><span>{inr(d.unit_price)}</span></>}
        <span>Policy</span><span>v{d.policy_version}</span>
      </div>
    </div>
  )
}

function Message({ role, text, user, decision }) {
  const mine = role === 'user'
  return (
    <div className={`msg-row ${role}`}>
      <Avatar kind={role} label={initialsOf(user)} />
      <div className="msg-body">
        <div className="msg-name">{mine ? (user || 'You') : 'Corvo assistant'}</div>
        <div className={`msg ${role}`}>
          {mine ? text : <RichText text={text} />}
          {decision && <DecisionCard d={decision} />}
        </div>
      </div>
    </div>
  )
}

function Thinking({ label }) {
  return (
    <div className="msg-row assistant" role="status" aria-label={label}>
      <Avatar kind="assistant" />
      <div className="msg-body">
        <div className="msg-name">Corvo assistant</div>
        <div className="msg assistant typing"><span className="dots"><i /><i /><i /></span><span className="typing-label">{label}</span></div>
      </div>
    </div>
  )
}

export default function Chat({ user }) {
  const [msgs, setMsgs] = useState([HELLO])
  const [text, setText] = useState('')
  const [sid, setSid] = useState(null)
  const [card, setCard] = useState(null)
  const [options, setOptions] = useState(null)
  const [state, setState] = useState('need_item')
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const [mode, setMode] = useState('chat') // chat | form
  const end = useRef()
  const input = useRef()
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy, confirming, options])

  async function send(message) {
    if (!message.trim() || busy) return
    setBusy(true); setError(null); setDone(null)
    setMsgs((m) => [...m, { role: 'user', text: message }]); setText('')
    try {
      const r = await api.post('/api/chat', { message, session_id: sid })
      setSid(r.session_id)
      if (r.pr_no) return raised(r) // the user confirmed by typing "yes"
      setCard(r.card); setOptions(r.options); setState(r.state)
      setMsgs((m) => [...m, { role: 'assistant', text: r.reply }])
    } catch (e) { setError(e) } finally { setBusy(false); input.current?.focus() }
  }

  async function confirm() {
    setConfirming(true); setError(null)
    try {
      raised(await api.post('/api/chat/confirm', { session_id: sid }))
    } catch (e) { setError(e) } finally { setConfirming(false) }
  }

  function raised(r) {
    setMsgs((m) => [...m, { role: 'assistant', text: r.reply, decision: r.decision }])
    setDone(r); setCard(null); setOptions(null); setState('need_item')
  }
  // A PR from the form is shown in the conversation too, so there is one history of what was raised.
  function raisedFromForm(r) {
    setMsgs((m) => [...m, { role: 'user', text: `Raised manually: ${r.card.quantity} ${r.card.uom} of ${r.card.description} for ${r.card.plant} by ${r.card.need_by}${r.card.urgency === 'Emergency' ? ' (emergency)' : ''}` }])
    raised(r); setMode('chat')
  }

  const reset = () => { setMsgs([HELLO]); setSid(null); setCard(null); setOptions(null); setDone(null); setError(null); setText(''); setState('need_item'); input.current?.focus() }

  return (
    <div>
      <PageHeader icon="chat" title="Raise a purchase request" subtitle="Describe what you need in plain language. The assistant matches it to the item master, asks for anything missing, and shows how procurement policy will treat it.">
        {mode === 'chat' && (msgs.length > 1 || done) && <Button icon="refresh" disabled={busy || confirming} onClick={reset}>Start over</Button>}
        {mode === 'chat'
          ? <Button variant="primary" icon="edit" disabled={busy || confirming} onClick={() => { setMode('form'); setDone(null) }}>Raise PR manually</Button>
          : <Button icon="chat" onClick={() => setMode('chat')}>Use the chat instead</Button>}
      </PageHeader>
      <div className="split">
        {mode === 'form' ? <ManualPr onRaised={raisedFromForm} onCancel={() => setMode('chat')} /> : (
        <section className="card" aria-label="Conversation">
          <div className="chat" role="log" aria-live="polite" aria-label="Chat messages">
            {msgs.map((m, i) => <Message key={i} role={m.role} text={m.text} decision={m.decision} user={user} />)}
            {busy && <Thinking label="Thinking…" />}
            {confirming && <Thinking label="Raising your purchase request…" />}
            {options?.length > 0 && state === 'choose_item' && (
              <div className="opts">
                {options.map((o, i) => <Button key={o.item_code} size="sm" onClick={() => send(String(i + 1))}>{i + 1}. {o.description}</Button>)}
                <Button size="sm" onClick={() => send('none')}>None of these</Button>
              </div>
            )}
            {state === 'need_plant' && <div className="opts"><Button size="sm" onClick={() => send('PUN1')}>PUN1 · Pune</Button><Button size="sm" onClick={() => send('CHK1')}>CHK1 · Chakan</Button></div>}
            {state === 'unknown_item' && <div className="opts"><Button size="sm" onClick={() => send('new item')}>Raise as a new item</Button></div>}
            {msgs.length === 1 && (
              <div className="opts" aria-label="Example requests">
                {EXAMPLES.map((x) => <button key={x} className="btn sm" onClick={() => send(x)}>{x}</button>)}
              </div>
            )}
            <div ref={end} />
          </div>
          <Err e={error} />
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text) }}>
            <label className="sr-only" htmlFor="chat-input">Your message</label>
            <input id="chat-input" ref={input} className="grow" value={text} onChange={(e) => setText(e.target.value)}
              placeholder={busy ? 'Assistant is replying…' : 'Type your request…'} autoComplete="off" autoFocus />
            <Button variant="primary" icon="send" loading={busy} disabled={!text.trim()}>Send</Button>
          </form>
        </section>
        )}

        <div>
          {card && mode === 'chat' && (
            <section className="card" aria-label="Confirm request">
              <div className="sec-head"><span className="sec-ic" aria-hidden="true"><Icon name="cart" size={18} /></span><h3 className="grow">Review your request</h3><span className="chip warn"><i />Not yet raised</span></div>
              <div className="kv">
                <div>Item</div><div>{card.is_new ? <><b>{card.description}</b> <span className="chip warn">new item</span></> : <><b className="mono">{card.item_code}</b> {card.description}</>}</div>
                <div>Quantity</div><div><b>{card.quantity}</b> {card.uom}</div>
                <div>Plant</div><div>{card.plant}</div>
                <div>Need by</div><div>{card.need_by}</div>
                <div>Urgency</div><div>{card.urgency === 'Emergency' ? <span className="chip bad"><i />Emergency</span> : 'Normal'}</div>
                {card.est_unit_price != null && <><div>Est. unit price</div><div>{inr(card.est_unit_price)}</div></>}
              </div>
              <div className="row"><Button variant="primary" icon="check" loading={confirming} disabled={busy} onClick={confirm}>Confirm PR</Button><span className="muted small">or tell me what to change, e.g. “make it 300”</span></div>
            </section>
          )}
          {done && (
            <section className="card" aria-label="Request raised">
              <Banner kind="ok"><b>{done.pr_no}</b> has been raised.</Banner>
              <div className="kv">
                <div>Decision</div><div><RouteChip route={done.decision.route} /></div>
                <div>Requirement value</div><div><b>{inr(done.decision.value)}</b></div>
                {done.decision.supplier_id && <><div>Supplier</div><div><b className="mono">{done.decision.supplier_id}</b> {done.decision.supplier_name}</div></>}
                <div>Policy</div><div>v{done.decision.policy_version}</div>
              </div>
              <div className="why">{done.decision.reason}</div>
              {done.decision.flags?.length > 0 && <div className="chips" style={{ marginBottom: 10 }}>{done.decision.flags.map((f, i) => <span key={i} className="chip warn wrap"><Icon name="alert" size={13} />{f}</span>)}</div>}
              <div className="row"><Link className="btn primary" to="/workspace">Open buyer workspace<Icon name="arrow" size={16} /></Link><Button onClick={reset}>Raise another</Button></div>
            </section>
          )}
          {(mode === 'form' || !card) && !done && <Next>{mode === 'form' ? <>pick the item, quantity, plant and need-by date, then press <b>Raise PR</b>.</> : 'describe what you need. I will ask for the item, quantity, plant and need-by date if they are missing.'}</Next>}
          {!card && !done && (
            <div className="card">
              <div className="sec-head"><span className="sec-ic" aria-hidden="true"><Icon name="shieldCheck" size={18} /></span><h3 className="grow">How decisions are made</h3></div>
              <p className="muted" style={{ margin: '6px 0 0' }}>Similar requests for the same item and plant within 14 days are combined into one requirement, so limits apply to the total. A usable rate contract is always preferred; otherwise value, urgency and purchase history choose between a PO and a sourcing request.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
