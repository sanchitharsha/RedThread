import { useState } from 'react'
import { DEFAULT_RECALL, DEFAULT_SHOP } from '../constants.js'
import { getReplays } from '../api.js'
import { Badges } from './Badges.jsx'

export function StartScreen({ onLive, onReplay, onDemo }) {
  const [recall, setRecall] = useState(DEFAULT_RECALL)
  const [shop, setShop] = useState(DEFAULT_SHOP)
  const [note, setNote] = useState('')
  const replay = async () => {
    setNote('')
    try {
      const list = await getReplays()
      const first = Array.isArray(list) ? (list[0]?.run_id || list[0]?.id || (typeof list[0] === 'string' ? list[0] : null)) : null
      if (!first) return setNote('No recorded run is available yet. Finish one live run first.')
      onReplay(recall, first)
    } catch (e) { setNote(`Could not reach the backend: ${e.message}`) }
  }
  return (
    <main className="start">
      <h1>Redthread</h1>
      <p className="lede">Follow the thread from an official recall to the evidence. A browser agent reads the notice and inspects the listings, strict rules rate each one, and every link shows its proof.</p>
      <Badges />
      <div className="card form">
        <label>Recall reference<input value={recall} onChange={(e) => setRecall(e.target.value)} placeholder="CPSC recall number" /></label>
        <label>Shop URL<input value={shop} onChange={(e) => setShop(e.target.value)} /></label>
        <div className="row">
          <button className="primary" onClick={() => onLive(recall, shop)}>Investigate</button>
          <button onClick={replay}>Replay recorded run</button>
          <button className="ghost" onClick={onDemo}>Use demo data</button>
        </div>
        {note && <p className="err" role="status">{note}</p>}
        <p className="muted small">The shop is a sandbox we built for testing. A replay always carries a Recorded run badge and is never shown as live.</p>
      </div>
    </main>
  )
}
