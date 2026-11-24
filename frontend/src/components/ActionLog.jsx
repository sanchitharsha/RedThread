import { useEffect, useRef } from 'react'

const ICON = { step: '◆', tool: '▸', page: '▤', official: '§', error: '!' }

export function ActionLog({ log }) {
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [log.length])
  return (
    <section className="panel log" aria-label="Agent action log">
      <h2>Agent action log</h2>
      <ol>
        {log.length === 0 && <li className="muted">No actions yet.</li>}
        {log.map((l, i) => (
          <li key={i} className={`l-${l.kind} ${l.allowed === false ? 'refused' : ''}`}>
            <span className="ico" aria-hidden="true">{ICON[l.kind]}</span>
            {l.kind === 'tool' && (<span><b>{l.tool}</b> <code>{Object.values(l.args).join(' ')}</code>
              {l.allowed === false && <em className="refusal"> refused by guard</em>}
              {l.reason && <span className="why"> {l.reason}</span>}</span>)}
            {l.kind === 'page' && (<span>Visited <a href={l.url} target="_blank" rel="noreferrer">{l.title || l.url}</a>{l.status === 'blocked' ? ' (blocked)' : ''}</span>)}
            {(l.kind === 'step' || l.kind === 'official' || l.kind === 'error') && <span>{l.text}</span>}
          </li>
        ))}
        <li ref={end} aria-hidden="true" />
      </ol>
    </section>
  )
}
