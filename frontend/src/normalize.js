// Adapters so the UI accepts BOTH the contract shapes (contracts/models.py) and the shapes in
// fixtures/events_canned.json / graph_fixture.json. Remove branches once the team settles on one.
import { API } from './constants.js'

export function shotUrl(p) {
  if (!p) return null
  if (/^https?:\/\//.test(p)) return p
  const i = p.lastIndexOf('runs/')
  const rest = i >= 0 ? p.slice(i + 5) : p.replace(/^\/+/, '')
  return `${API}/shots/${rest}`
}

export function normEvent(raw) {
  const p = raw.payload || {}
  return { run_id: raw.run_id, seq: raw.seq, ts: raw.ts || raw.timestamp || null, type: raw.type, payload: p }
}

export function normNode(n) {
  return { id: n.id, type: n.type || n.kind || 'Listing', label: n.label || n.id, props: n.props || n.properties || {} }
}

export function normLink(l) {
  const props = l.props || l.properties || {}
  return {
    id: l.id,
    source: typeof l.source === 'object' ? l.source.id : l.source,
    target: typeof l.target === 'object' ? l.target.id : l.target,
    type: l.type || l.kind || 'RELATED_TO',
    tier: l.tier || props.tier || null,
    reasons: l.reasons || props.reasons || [],
    evidence: l.evidence || l.evidence_ids || [],
  }
}

export function normDelta(p) {
  return {
    nodes: (p.nodes || p.nodes_added || []).map(normNode),
    links: (p.links || p.edges || p.links_added || p.edges_added || []).map(normLink),
  }
}

export function normGraph(g) {
  return { nodes: (g.nodes || []).map(normNode), links: (g.links || g.edges || []).map(normLink) }
}

// A field may be a contract Quoted {value, evidence_quote, verified} or a plain string (canned data).
export function fieldOf(v) {
  if (v == null) return null
  if (typeof v === 'object' && 'value' in v) {
    return { value: v.value, quote: v.evidence_quote, verified: v.verified, evidence_id: v.evidence_id }
  }
  return { value: String(v), quote: null, verified: null }
}

export function normExtraction(p) {
  const rows = []
  const add = (label, v) => { const f = fieldOf(v); if (f) rows.push({ label, ...f }) }
  add('Brand', p.brand)
  add('Product', p.product_name)
  ;(p.model_numbers || []).forEach((q) => add('Model', q))
  if (p.model) add('Model', p.model)
  ;(p.gtins || []).forEach((q) => add('GTIN', q))
  if (p.gtin) add('GTIN', p.gtin)
  ;(p.lot_or_date_info || []).forEach((q) => add('Date or lot', q))
  add('Seller', p.seller)
  ;(p.variants || []).forEach((q) => add('Variant', q))
  return { listing_id: p.listing_id, source_url: p.source_url, status: p.capture_status || 'ok', rows }
}

export function normMatch(p) {
  return {
    listing_id: p.listing_id,
    recall_id: p.recall_id || p.recall_number || '',
    tier: p.tier,
    reasons: p.reasons || [],
    evidence_ids: p.evidence_ids || (p.evidence || []).map((e) => e.id),
  }
}

export function normRecall(p) {
  return {
    number: p.number || p.recall_number || '',
    authority: p.authority || '',
    title: p.title || '',
    brand: p.brand || '',
    models: p.models || [],
    hazard: p.hazard || '',
    remedy: p.remedy || '',
    url: p.url || '',
    scope: p.scope_type || (p.scope && p.scope.kind) || 'unknown',
  }
}

export const tierOrder = ['CONFIRMED', 'LIKELY', 'CONFLICT', 'RELATED', 'UNRESOLVED', 'NO_MATCH']
export const sortByTier = (a, b) => tierOrder.indexOf(a.tier) - tierOrder.indexOf(b.tier)

// Which pipeline stages have been reached, derived from events (the contract has no stage field).
export function stagesFrom(events) {
  const s = { official: false, harvest: false, discover: false, inspect: false, extract: false, match: false, report: false }
  for (const e of events) {
    const p = e.payload
    if (e.type === 'official_record') s.official = true
    if (e.type === 'step_started' && (p.step === 'harvest_notice' || p.stage === 'harvest')) s.harvest = true
    if (e.type === 'step_started' && (p.step === 'discover_and_inspect' || p.stage === 'discover')) s.discover = true
    if (e.type === 'page_visited' && p.source_tier === 'A') s.harvest = true
    if (e.type === 'page_visited' && /\/(listings|product)\//.test(p.url || '')) { s.discover = true; s.inspect = true }
    if (e.type === 'extraction') s.extract = true
    if (e.type === 'match_result') s.match = true
    if (e.type === 'run_finished') s.report = true
  }
  return s
}

export function countsOf(results) {
  const c = { CONFIRMED: 0, LIKELY: 0, RELATED: 0, CONFLICT: 0, NO_MATCH: 0, UNRESOLVED: 0 }
  Object.values(results).forEach((r) => { if (c[r.tier] != null) c[r.tier] += 1 })
  return c
}
