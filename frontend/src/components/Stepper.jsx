import { STAGES } from '../constants.js'

export function Stepper({ stages }) {
  const idx = STAGES.reduce((a, [k], i) => (stages[k] ? i : a), -1)
  return (
    <ol className="stepper" aria-label="Pipeline progress">
      {STAGES.map(([k, label], i) => (
        <li key={k} className={stages[k] ? 'done' : i === idx + 1 ? 'next' : ''}>
          <span className="bead" aria-hidden="true" />
          <span className="stlabel">{label}{stages[k] ? <span className="sr"> (reached)</span> : null}</span>
        </li>
      ))}
    </ol>
  )
}
