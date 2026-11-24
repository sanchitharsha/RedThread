import { Chip } from './Chip.jsx'
import { sortByTier } from '../normalize.js'

export function VerdictTable({ results, onOpen }) {
  const rows = Object.values(results).sort(sortByTier)
  if (!rows.length) return <p className="muted pad">Verdicts appear here as listings are rated.</p>
  return (
    <table className="vt">
      <thead><tr><th>Listing</th><th>Verdict</th><th>Why</th><th /></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.listing_id}>
            <td>{r.listing_id}</td>
            <td><Chip tier={r.tier} /></td>
            <td className="codes">{r.reasons.map((c) => <code key={c}>{c}</code>)}</td>
            <td><button className="link" onClick={() => onOpen({ title: `Evidence for ${r.listing_id}`, tier: r.tier, reasons: r.reasons, evidenceIds: r.evidence_ids })}>Open evidence</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
