import React from 'react'

/**
 * Formats assistant replies without innerHTML (so a message can never inject markup):
 *   **bold**, `code`, numbered / bulleted lists, paragraphs,
 *   and highlights item codes (ITM-1022), PR numbers, plant codes, ₹ amounts and “quoted text”.
 */
const INLINE = new RegExp([
  /\*\*(?<bold>[^*]+)\*\*/.source,
  /`(?<code>[^`]+)`/.source,
  /(?<item>\bITM-\d{4}\b)/.source,
  /(?<pr>\bPR-(?:[A-Z]+-)?\d+\b)/.source,
  /(?<plant>\b(?:PUN1|CHK1)\b)/.source,
  /(?<money>₹\s?[\d,]+(?:\.\d+)?)/.source,
  /(?<quote>“[^”]+”)/.source,
].join('|'), 'g')

function inline(text, keyBase) {
  const out = []
  let last = 0
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const g = m.groups
    const key = `${keyBase}-${m.index}`
    if (g.bold) out.push(<strong key={key}>{inline(g.bold, key)}</strong>)
    else if (g.code) out.push(<code key={key} className="rt-code">{g.code}</code>)
    else if (g.item) out.push(<code key={key} className="rt-tag item">{g.item}</code>)
    else if (g.pr) out.push(<code key={key} className="rt-tag pr">{g.pr}</code>)
    else if (g.plant) out.push(<code key={key} className="rt-tag plant">{g.plant}</code>)
    else if (g.money) out.push(<strong key={key} className="rt-money">{g.money}</strong>)
    else if (g.quote) out.push(<q key={key} className="rt-quote">{g.quote.slice(1, -1)}</q>)
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

const LIST_RE = { ol: /^\s*(\d+)[.)]\s+(.*)$/, ul: /^\s*[-•*]\s+(.*)$/ }

/** Group lines into paragraphs and lists. */
function blocks(text) {
  const out = []
  for (const line of text.split('\n')) {
    const ol = line.match(LIST_RE.ol), ul = !ol && line.match(LIST_RE.ul)
    const kind = ol ? 'ol' : ul ? 'ul' : 'p'
    const body = ol ? ol[2] : ul ? ul[1] : line
    const prev = out[out.length - 1]
    if (kind !== 'p' && prev?.kind === kind) prev.items.push(body)
    else if (kind !== 'p') out.push({ kind, items: [body] })
    else if (line.trim()) out.push({ kind: 'p', text: line })
  }
  return out
}

export default function RichText({ text }) {
  return (
    <div className="rt">
      {blocks(text || '').map((b, i) => {
        if (b.kind === 'p') return <p key={i}>{inline(b.text, i)}</p>
        const List = b.kind
        return <List key={i}>{b.items.map((it, j) => <li key={j}>{inline(it, `${i}-${j}`)}</li>)}</List>
      })}
    </div>
  )
}
