import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { normEvent, normDelta, normGraph, normExtraction, normMatch, stagesFrom, countsOf, shotUrl } from './normalize.js'

const events = JSON.parse(readFileSync(new URL('../public/demo/events_canned.json', import.meta.url))).map(normEvent)
const graph = JSON.parse(readFileSync(new URL('../public/demo/graph_fixture.json', import.meta.url)))

test('canned events normalise (timestamp -> ts) and cover the key types', () => {
  assert.ok(events.every((e) => e.ts))
  const types = new Set(events.map((e) => e.type))
  for (const t of ['run_started', 'tool_call', 'page_visited', 'extraction', 'match_result', 'graph_delta', 'run_finished']) assert.ok(types.has(t), t)
})
test('graph_delta from nodes_added/edges_added becomes nodes/links with tier + evidence', () => {
  const d = normDelta(events.find((e) => e.type === 'graph_delta').payload)
  assert.equal(d.nodes[0].type, 'Listing')
  assert.equal(d.links[0].tier, 'CONFIRMED')
  assert.deepEqual(d.links[0].evidence, ['ev-L01-model', 'ev-L01-gtin'])
})
test('fixture graph: every link has evidence and a valid tier when MATCHES', () => {
  const g = normGraph(graph)
  assert.ok(g.links.every((l) => l.evidence.length > 0))
  assert.ok(g.links.filter((l) => l.type === 'MATCHES').every((l) => l.tier))
})
test('contract-shaped Quoted fields keep quote + verified flag; flat strings have none', () => {
  const a = normExtraction({ listing_id: 'l01', model_numbers: [{ value: 'X-1', evidence_quote: 'Model: X-1', verified: true }] })
  assert.equal(a.rows[0].verified, true)
  const b = normExtraction({ listing_id: 'lst', model: 'X-1' })
  assert.equal(b.rows[0].verified, null)
})
test('match_result accepts recall_id or recall_number', () => {
  assert.equal(normMatch({ listing_id: 'a', recall_number: '5', tier: 'LIKELY' }).recall_id, '5')
})
test('stages and counts', () => {
  const s = stagesFrom(events)
  assert.ok(s.official && s.match && s.report)
  assert.equal(countsOf({ a: { tier: 'CONFIRMED' }, b: { tier: 'NO_MATCH' } }).CONFIRMED, 1)
})
test('shotUrl maps runs/ paths to /shots/', () => {
  assert.match(shotUrl('runs/r1/shots/s1.jpg'), /\/shots\/r1\/shots\/s1\.jpg$/)
  assert.equal(shotUrl(null), null)
})
