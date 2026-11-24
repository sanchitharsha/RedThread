import { Chip, Verified } from './Chip.jsx'

export function ExtractionPanel({ extractions, results }) {
  if (!extractions.length) return <p className="muted pad">Extracted fields appear here, one card per listing.</p>
  return (
    <div className="xgrid">
      {extractions.map((x) => {
        const r = results[x.listing_id]
        return (
          <article className="xcard" key={x.listing_id}>
            <header><b>{x.listing_id}</b>{r && <Chip tier={r.tier} reasons={r.reasons} />}</header>
            {x.source_url && <p className="muted small">{x.source_url}</p>}
            {x.status !== 'ok' && <p className="small">Capture status: {x.status}. Nothing was extracted.</p>}
            <table><tbody>
              {x.rows.map((f, i) => (
                <tr key={i}>
                  <th scope="row">{f.label}</th>
                  <td><span className="val">{f.value}</span><Verified ok={f.verified} />{f.quote && <q>{f.quote}</q>}</td>
                </tr>
              ))}
              {x.rows.length === 0 && x.status === 'ok' && <tr><td className="muted">No field survived quote verification.</td></tr>}
            </tbody></table>
          </article>
        )
      })}
    </div>
  )
}
