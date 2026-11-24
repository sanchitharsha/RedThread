import { useState } from 'react'
import { TIER_STYLE, REASON_TEXT } from '../constants.js'

export function Chip({ tier, reasons = [], expandable = false, long = false }) {
  const [open, setOpen] = useState(false)
  const s = TIER_STYLE[tier] || { label: tier, long: tier, bg: '#d5dae1', fg: '#1b1b1b' }
  const tip = reasons.map((r) => REASON_TEXT[r] || r).join(' ')
  const Tag = expandable ? 'button' : 'span'
  return (
    <span className="chipwrap">
      <Tag className="chip" style={{ background: s.bg, color: s.fg }} title={tip || s.long}
        onClick={expandable ? () => setOpen((o) => !o) : undefined} aria-expanded={expandable ? open : undefined}>
        {long ? s.long : s.label}
      </Tag>
      {(open || false) && <ReasonList reasons={reasons} />}
    </span>
  )
}

export function ReasonList({ reasons }) {
  if (!reasons?.length) return null
  return (
    <ul className="reasons">
      {reasons.map((r) => (<li key={r}><code>{r}</code> {REASON_TEXT[r] || ''}</li>))}
    </ul>
  )
}

// Verified-quote mark. Blue tick / dark cross plus words, never green.
export function Verified({ ok }) {
  if (ok == null) return <span className="vmark vnone">no quote supplied</span>
  return ok ? <span className="vmark vok">✓ quote verified</span> : <span className="vmark vbad">✗ quote not verified</span>
}
