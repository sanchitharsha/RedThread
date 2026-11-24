import { DISCLAIMER, TIERS, TIER_STYLE } from '../constants.js'
import { exportUrl } from '../api.js'
import { sortByTier } from '../normalize.js'
import { Chip } from './Chip.jsx'
import { Badges } from './Badges.jsx'

export function ReportView({ report, mode, runId, onBack, onEvidence }) {
  const badge = mode === 'demo' ? 'demo' : report.mode_badge === 'recorded' ? 'recorded' : 'live'
  const rows = [...(report.listings || [])].sort(sortByTier)
  const download = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'redthread-report.json'; a.click()
  }
  const r = report.recall || {}
  return (
    <div className="report">
      <div className="noprint toolbar"><button onClick={onBack}>Back to investigation</button>
        {mode === 'demo' ? <button onClick={download}>Export JSON</button> : <a className="btn" href={exportUrl(runId)}>Export JSON</a>}
        <button onClick={() => window.print()}>Print</button></div>
      <h1>Exposure report</h1>
      <Badges mode={badge} />
      <section className="card">
        <h2>Official record</h2>
        <p><b>{r.authority} {r.number}</b> {r.title}</p>
        <p className="muted">{r.brand}{r.models?.length ? ` · ${r.models.length} model numbers named` : ''}</p>
        {r.hazard && <p><b>Hazard.</b> {r.hazard}</p>}
        {r.remedy && <p><b>Official remedy.</b> {r.remedy}</p>}
        {r.url && <p><a href={r.url} target="_blank" rel="noreferrer">Read the official notice</a></p>}
      </section>
      <section aria-label="Counts per verdict" className="counts">
        {TIERS.map((t) => (<div key={t} className="count"><span className="n">{report.counts?.[t] ?? 0}</span><Chip tier={t} long /></div>))}
      </section>
      <section className="card">
        <h2>Listings</h2>
        <table className="vt">
          <thead><tr><th>Listing</th><th>Verdict</th><th>Reasons</th><th className="noprint" /></tr></thead>
          <tbody>
            {rows.map((l) => (
              <tr key={l.listing_id}>
                <td><b>{l.title || l.listing_id}</b><div className="muted small">{l.url}</div></td>
                <td><Chip tier={l.tier} long /></td>
                <td className="codes">{(l.reasons || []).map((c) => <code key={c}>{c}</code>)}</td>
                <td className="noprint"><button className="link" onClick={() => onEvidence({ title: `Evidence for ${l.title || l.listing_id}`, tier: l.tier, reasons: l.reasons, evidenceIds: l.evidence_ids || [] })}>Evidence</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {(report.conflicts || []).length > 0 && (
        <section className="card"><h2>Conflicts</h2>
          {report.conflicts.map((c, i) => (<p key={i}><Chip tier="CONFLICT" /> {c.detail || c.field || JSON.stringify(c)}</p>))}
        </section>)}
      {(report.unresolved || []).length > 0 && (
        <section className="card"><h2>Unresolved</h2>
          {report.unresolved.map((u, i) => (<p key={i}><Chip tier="UNRESOLVED" /> {u.listing_id || u.url} {(u.reasons || []).map((c) => <code key={c}>{c}</code>)}</p>))}
        </section>)}
      <section className="card coverage">
        <h2>Coverage</h2>
        <h3>Sources checked</h3>
        <ul>{(report.sources_checked || []).map((s, i) => (<li key={i}>{s.name}{s.retrieved_at ? ` · ${new Date(s.retrieved_at).toLocaleString()}` : ''}{s.url ? ` · ${s.url}` : ''}</li>))}
          {!(report.sources_checked || []).length && <li className="muted">None listed.</li>}</ul>
        <h3>Not checked</h3>
        <ul>{(report.not_checked || []).map((s, i) => <li key={i}>{s}</li>)}</ul>
      </section>
      <p className="disclaimer">{report.disclaimer || DISCLAIMER}</p>
      <p className="muted small">{TIER_STYLE.NO_MATCH.long} means nothing matched in the sources listed above.</p>
    </div>
  )
}
