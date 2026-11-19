import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, inr } from '../api.js'
import { Banner, Button, Err, Icon, Next, PageHeader, RouteChip } from '../components.jsx'

const HELLO = { role: 'assistant', text: 'Hi! Tell me what you need, for example: “need 200 nitrile gloves for Chakan by next Friday”. I will ask for anything that is missing, and I only use items from the item master.' }
const EXAMPLES = ['need 200 nitrile gloves for Chakan by next Friday', 'brg 6205 2rs 50 nos for Pune by 28 Nov', 'need 2 ultrasonic thickness gauge for Chakan by 10 Dec']

export default function Chat() {
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
  const end = useRef()
  const input = useRef()
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy, options])

  async function send(message) {
    if (!message.trim() || busy) return
    setBusy(true); setError(null); setDone(null)
    setMsgs((m) => [...m, { role: 'user', text: message }]); setText('')
    try {
      const r = await api.post('/api/chat', { message, session_id: sid })
      setSid(r.session_id); setCard(r.card); setOptions(r.options); setState(r.state)
      setMsgs((m) => [...m, { role: 'assistant', text: r.reply }])
    } catch (e) { setError(e) } finally { setBusy(false); input.current?.focus() }
  }

  async function confirm() {
    setConfirming(true); setError(null)
    try {
      const r = await api.post('/api/chat/confirm', { session_id: sid })
      setMsgs((m) => [...m, { role: 'assistant', text: r.reply }])
      setDone(r); setCard(null); setOptions(null); setState('need_item')
    } catch (e) { setError(e) } finally { setConfirming(false) }
  }

  const reset = () => { setMsgs([HELLO]); setSid(null); setCard(null); setOptions(null); setDone(null); setState('need_item'); input.current?.focus() }

  return (
    <div>
      <PageHeader title="Raise a purchase request" subtitle="Describe what you need in plain language. The assistant matches it to the item master, asks for anything missing, and shows how procurement policy will treat it.">
        {(msgs.length > 1 || done) && <Button icon="refresh" onClick={reset}>Start over</Button>}
      </PageHeader>
      <div className="split">
        <section className="card" aria-label="Conversation">
          <div className="chat" role="log" aria-live="polite" aria-label="Chat messages">
            {msgs.map((m, i) => <div key={i} className={`msg ${m.role}`}>{m.text}</div>)}
            {busy && <div className="msg assistant typing" aria-label="Assistant is typing"><i /><i /><i /></div>}
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
          <form className="row" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); send(text) }}>
            <label className="sr-only" htmlFor="chat-input">Your message</label>
            <input id="chat-input" ref={input} className="grow" value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your request…" autoComplete="off" autoFocus />
            <Button variant="primary" icon="send" disabled={!text.trim() || busy}>Send</Button>
          </form>
        </section>

        <div>
          {card && (
            <section className="card" aria-label="Confirm request">
              <div className="card-head"><h3>Review your request</h3><span className="chip warn"><i />Not yet raised</span></div>
              <div className="kv">
                <div>Item</div><div>{card.is_new ? <><b>{card.description}</b> <span className="chip warn">new item</span></> : <><b className="mono">{card.item_code}</b> {card.description}</>}</div>
                <div>Quantity</div><div><b>{card.quantity}</b> {card.uom}</div>
                <div>Plant</div><div>{card.plant}</div>
                <div>Need by</div><div>{card.need_by}</div>
                <div>Urgency</div><div>{card.urgency === 'Emergency' ? <span className="chip bad"><i />Emergency</span> : 'Normal'}</div>
                {card.est_unit_price != null && <><div>Est. unit price</div><div>{inr(card.est_unit_price)}</div></>}
              </div>
              <div className="row"><Button variant="primary" icon="check" loading={confirming} onClick={confirm}>Confirm PR</Button><span className="muted small">or tell me what to change, e.g. “make it 300”</span></div>
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
          {!card && !done && <Next>describe what you need. I will ask for the item, quantity, plant and need-by date if they are missing.</Next>}
          {!card && !done && (
            <div className="card">
              <h3>How decisions are made</h3>
              <p className="muted" style={{ margin: '6px 0 0' }}>Similar requests for the same item and plant within 14 days are combined into one requirement, so limits apply to the total. A usable rate contract is always preferred; otherwise value, urgency and purchase history choose between a PO and a sourcing request.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
