import { API } from './constants.js'

async function j(url, opts) {
  const r = await fetch(url, opts)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`)
  return r.json()
}

export const startRun = (recall_ref, shop_url, replay_id) =>
  j(`${API}/api/investigations`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(replay_id ? { recall_ref, replay_id } : { recall_ref, shop_url }),
  })
export const getReplays = () => j(`${API}/api/replays`)
export const getGraph = (id) => j(`${API}/api/investigations/${id}/graph`)
export const getReport = (id) => j(`${API}/api/investigations/${id}/report`)
export const getEvidence = (id) => j(`${API}/api/evidence/${encodeURIComponent(id)}`)
export const exportUrl = (id) => `${API}/api/investigations/${id}/export.json`
export const eventsUrl = (id) => `${API}/api/investigations/${id}/events`
export const getJson = (path) => j(path)
