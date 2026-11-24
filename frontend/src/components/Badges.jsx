export function Badges({ mode }) {
  const text = mode === 'live' ? 'Live run' : mode === 'recorded' ? 'Recorded run' : mode === 'demo' ? 'Demo data' : null
  return (
    <span className="badges">
      <span className="badge sandbox">Sandbox shop</span>
      {text && <span className={`badge ${mode}`}>{text}</span>}
    </span>
  )
}
