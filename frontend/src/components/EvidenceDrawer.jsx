import { useEffect, useState } from 'react'
import { getEvidence } from '../api.js'
import { shotUrl } from '../normalize.js'
import { Chip, ReasonList, Verified } from './Chip.jsx'

export function EvidenceDrawer({ sel, demo, onClose }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState('')
  const ids = sel?.evidenceIds || []
  useEffect(() => {
    setItems([]); setErr('')
    if (!sel) return undefined
    if (demo) { setItems(ids.map((i) => ({ id: i, demo: true }))); return undefined }
    let live = true
    Promise.all(ids.map((i) => getEvidence(i).catch((e) => ({ id: i, error: e.message }))))
      .then((r) => { if (live) setItems(r) }).catch((e) => live && setErr(e.message))
    return () => { live = false }
  }, [sel]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!sel) return null
  return (
    <aside className="drawer" role="dialog" aria-label="Evidence" >
      <header>
        <div><h2>{sel.title}</h2>{sel.subtitle && <p className="muted">{sel.subtitle}</p>}</div>
        <button className="x" onClick={onClose} aria-label="Close evidence drawer">Close</button>
      </header>
      {sel.tier && <p><Chip tier={sel.tier} long /></p>}
      <ReasonList reasons={sel.reasons} />
      <h3>Evidence ({ids.length})</h3>
      {ids.length === 0 && <p className="muted">No evidence ids are attached to this item.</p>}
      {err && <p className="err">{err}</p>}
      {items.map((e) => (
        <article className="ev" key={e.id}>
          {e.demo && <p className="muted">Demo data: the canned fixtures carry evidence ids but no quotes. Live runs fill this in.</p>}
          {e.error && <p className="err">Could not load {e.id}: {e.error}</p>}
          {e.source_url && <p><a href={e.source_url} target="_blank" rel="noreferrer">{e.source_url}</a></p>}
          {e.quote && <blockquote>{e.quote}</blockquote>}
          <dl>
            <dt>Evidence id</dt><dd><code>{e.id}</code></dd>
            {e.retrieved_at && (<><dt>Retrieved</dt><dd>{new Date(e.retrieved_at).toLocaleString()}</dd></>)}
            {e.source_tier && (<><dt>Source tier</dt><dd>{e.source_tier}{e.source_tier === 'A' ? ' (official authority)' : ''}</dd></>)}
            {e.method && (<><dt>Method</dt><dd>{e.method}</dd></>)}
          </dl>
          {'quote_verified' in e && <Verified ok={e.quote_verified} />}
          {e.screenshot_path && <img className="thumb" src={shotUrl(e.screenshot_path)} alt="Screenshot of the page this quote came from" />}
        </article>
      ))}
    </aside>
  )
}
