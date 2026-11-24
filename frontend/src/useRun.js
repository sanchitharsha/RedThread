import { useCallback, useReducer, useRef, useState } from 'react'
import * as api from './api.js'
import { DISCLAIMER } from './constants.js'
import {
  normEvent, normDelta, normGraph, normExtraction, normMatch, normRecall, shotUrl, countsOf, sortByTier,
} from './normalize.js'

const empty = () => ({
  events: [], recall: null, page: { url: '', title: '', shot: null, count: 0 }, step: 0, maxSteps: null,
  log: [], extractions: [], results: {}, graph: { nodes: [], links: [] }, conflicts: [],
  finished: null, errors: [], seed: {},
})

function mergeGraph(g, delta, seed) {
  const nodes = [...g.nodes]
  const links = [...g.links]
  const has = (id) => nodes.some((n) => n.id === id)
  delta.nodes.forEach((n) => { if (!has(n.id)) nodes.push({ ...n }) })
  delta.links.forEach((l) => {
    ;[l.source, l.target].forEach((id) => { if (!has(id) && seed[id]) nodes.push({ ...seed[id] }) })
    if (!links.some((x) => x.id === l.id)) links.push({ ...l })
  })
  return { nodes, links }
}

function reducer(s, a) {
  if (a.type === 'reset') return { ...empty(), seed: a.seed || {} }
  if (a.type === 'graph') return { ...s, graph: mergeGraph(s.graph, { nodes: a.graph.nodes, links: a.graph.links }, s.seed) }
  if (a.type !== 'event') return s
  const e = a.ev
  const p = e.payload
  const next = { ...s, events: [...s.events, e] }
  switch (e.type) {
    case 'run_started': break
    case 'step_started': {
      const n = typeof p.step === 'number' ? p.step : s.step
      next.step = n
      if (p.max_steps) next.maxSteps = p.max_steps
      next.log = [...s.log, { kind: 'step', seq: e.seq, text: typeof p.step === 'string' ? p.step.replace(/_/g, ' ') : `Step ${n}`, url: p.url }]
      break
    }
    case 'tool_call':
      next.log = [...s.log, { kind: 'tool', seq: e.seq, tool: p.tool, args: p.args || {}, reason: p.reason || p.reasoning_summary || '', allowed: p.allowed !== false }]
      break
    case 'page_visited':
      next.page = { url: p.url, title: p.title || '', shot: shotUrl(p.screenshot_url || p.screenshot_path) || s.page.shot, count: s.page.count + 1, status: p.status }
      next.log = [...s.log, { kind: 'page', seq: e.seq, url: p.url, title: p.title, status: p.status }]
      break
    case 'official_record':
      next.recall = { ...(s.recall || {}), ...normRecall(p) }
      next.log = [...s.log, { kind: 'official', seq: e.seq, text: `Official record ${next.recall.number || ''}`.trim() }]
      break
    case 'extraction': {
      const x = normExtraction(p)
      next.extractions = [...s.extractions.filter((y) => y.listing_id !== x.listing_id), x]
      break
    }
    case 'match_result': {
      const m = normMatch(p)
      next.results = { ...s.results, [m.listing_id]: m }
      break
    }
    case 'conflict':
      next.conflicts = [...s.conflicts, p]
      break
    case 'graph_delta':
      next.graph = mergeGraph(s.graph, normDelta(p), s.seed)
      break
    case 'run_finished':
      next.finished = p
      break
    case 'run_error':
      next.errors = [...s.errors, p.message || p.code || 'Non-fatal error']
      next.log = [...s.log, { kind: 'error', seq: e.seq, text: p.message || p.code || 'Non-fatal error' }]
      break
    default: break
  }
  return next
}

export function useRun() {
  const [state, dispatch] = useReducer(reducer, undefined, empty)
  const [mode, setMode] = useState(null)        // 'live' | 'recorded' | 'demo'
  const [runId, setRunId] = useState(null)
  const [status, setStatus] = useState('idle')  // idle | running | done | error
  const [error, setError] = useState('')
  const [report, setReport] = useState(null)
  const seen = useRef(new Set())
  const closer = useRef(() => {})

  const ingest = useCallback((raw) => {
    const ev = normEvent(raw)
    if (ev.seq != null) { if (seen.current.has(ev.seq)) return; seen.current.add(ev.seq) }
    dispatch({ type: 'event', ev })
  }, [])

  const reset = useCallback((seed) => {
    closer.current(); seen.current = new Set()
    dispatch({ type: 'reset', seed }); setReport(null); setError(''); setStatus('running')
  }, [])

  const finishLive = useCallback(async (id) => {
    try {
      const [g, r] = await Promise.all([api.getGraph(id), api.getReport(id)])
      dispatch({ type: 'graph', graph: normGraph(g) }); setReport(r)
      setMode((m) => (m === 'live' && r.mode_badge === 'recorded' ? 'recorded' : m))
    } catch (e) { setError(`Could not load the final report: ${e.message}`) }
    setStatus('done')
  }, [])

  const follow = useCallback((id) => {
    const es = new EventSource(api.eventsUrl(id))
    let done = false
    closer.current = () => { done = true; es.close() }
    es.onmessage = (m) => {
      let raw; try { raw = JSON.parse(m.data) } catch { return }
      ingest(raw)
      if (raw.type === 'run_finished') { done = true; es.close(); finishLive(id) }
    }
    es.onerror = () => { if (!done) { es.close(); setError('Lost the live event stream. Check that the backend is running on port 8000.'); setStatus('error') } }
  }, [ingest, finishLive])

  const startLive = useCallback(async (recall, shop, replayId) => {
    reset(); setMode(replayId ? 'recorded' : 'live')
    try { const { run_id } = await api.startRun(recall, shop, replayId); setRunId(run_id); follow(run_id) }
    catch (e) { setError(`Could not start the run: ${e.message}`); setStatus('error') }
  }, [reset, follow])

  const startDemo = useCallback(async () => {
    setMode('demo'); setRunId('demo')
    const [evs, g] = await Promise.all([api.getJson('/demo/events_canned.json'), api.getJson('/demo/graph_fixture.json')])
    const seed = {}; normGraph(g).nodes.forEach((n) => { seed[n.id] = n })
    reset(seed)
    let stop = false; closer.current = () => { stop = true }
    for (const raw of evs) {
      if (stop) return
      await new Promise((r) => setTimeout(r, 450))
      if (stop) return
      ingest(raw)
    }
    setStatus('done')
  }, [reset, ingest])

  // Report for demo data (live runs get it from the API).
  const demoReport = () => {
    const rows = Object.values(state.results).map((m) => {
      const key = 'listing-' + String(m.listing_id).split('-').pop()
      const node = state.graph.nodes.find((n) => n.id === key)
      return { listing_id: m.listing_id, url: node?.props?.url || '', title: node?.label || m.listing_id, tier: m.tier, reasons: m.reasons, evidence_ids: m.evidence_ids }
    }).sort(sortByTier)
    return {
      run_id: 'demo', mode_badge: 'recorded', demo: true, recall: state.recall, counts: countsOf(state.results), listings: rows,
      conflicts: state.conflicts, unresolved: rows.filter((r) => r.tier === 'UNRESOLVED').map((r) => ({ listing_id: r.listing_id, reasons: r.reasons })),
      sources_checked: state.page.url ? [{ name: 'Pages visited in this demo', url: state.page.url }] : [],
      not_checked: ['Other authorities', 'Other shops'], disclaimer: DISCLAIMER,
    }
  }

  const stop = useCallback(() => { closer.current(); setStatus('idle') }, [])
  return { state, mode, runId, status, error, report: report || (mode === 'demo' && status === 'done' ? demoReport() : null), startLive, startDemo, stop }
}
