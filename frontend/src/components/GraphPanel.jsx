import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { NODE_COLOR, TIER_STYLE } from '../constants.js'

const linkColor = (l) => (l.type === 'MATCHES' && l.tier ? TIER_STYLE[l.tier]?.bg : '#9aa5b4')
const id = (x) => (typeof x === 'object' ? x.id : x)

export function GraphPanel({ graph, onSelect }) {
  const box = useRef(null)
  const [size, setSize] = useState({ w: 600, h: 380 })
  useEffect(() => {
    if (!box.current) return undefined
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.max(300, e.contentRect.width), h: Math.max(260, e.contentRect.height) }))
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [])
  const data = useMemo(() => {
    const ids = new Set(graph.nodes.map((n) => n.id))
    return { nodes: graph.nodes, links: graph.links.filter((l) => ids.has(id(l.source)) && ids.has(id(l.target))) }
  }, [graph])

  return (
    <section className="panel graph" aria-label="Evidence graph">
      <h2>Evidence graph <span className="muted">click a line or node to open its evidence</span></h2>
      <div className="graphbox" ref={box}>
        <ForceGraph2D
          graphData={data} width={size.w} height={size.h} backgroundColor="#fbfcfd"
          nodeRelSize={6} linkWidth={(l) => (l.type === 'MATCHES' ? 3 : 1.2)} linkColor={linkColor}
          linkDirectionalParticles={(l) => (l.type === 'MATCHES' ? 2 : 0)} linkDirectionalParticleSpeed={0.006}
          linkHoverPrecision={8} cooldownTicks={120}
          onLinkClick={(l) => onSelect({ kind: 'link', link: l })}
          onNodeClick={(n) => onSelect({ kind: 'node', node: n })}
          nodeCanvasObject={(n, ctx, scale) => {
            const r = n.type === 'Recall' ? 9 : 6
            ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
            ctx.fillStyle = NODE_COLOR[n.type] || '#4b5563'; ctx.fill()
            ctx.lineWidth = 1.5 / scale; ctx.strokeStyle = '#fff'; ctx.stroke()
            if (scale > 0.9) {
              ctx.font = `${11 / scale}px system-ui, sans-serif`; ctx.fillStyle = '#151a22'; ctx.textAlign = 'center'
              ctx.fillText(String(n.label).slice(0, 26), n.x, n.y + r + 10 / scale)
            }
          }}
          nodePointerAreaPaint={(n, color, ctx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, 10, 0, 2 * Math.PI); ctx.fill() }}
        />
        {graph.nodes.length === 0 && <div className="emptyg">The graph grows as the agent finds evidence.</div>}
      </div>
      <ul className="legend" aria-label="Graph legend">
        {Object.entries(NODE_COLOR).slice(0, 5).map(([k, c]) => (<li key={k}><i style={{ background: c }} />{k}</li>))}
        {['CONFIRMED', 'LIKELY', 'RELATED', 'NO_MATCH'].map((t) => (<li key={t}><u style={{ background: TIER_STYLE[t].bg }} />{TIER_STYLE[t].label}</li>))}
      </ul>
    </section>
  )
}
