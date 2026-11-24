export function BrowserPanel({ page, step, maxSteps, running }) {
  return (
    <section className="panel browser" aria-label="Live browser view">
      <div className="chrome">
        <span className="dots" aria-hidden="true"><i /><i /><i /></span>
        <span className="urlbar" title={page.url}>{page.url || 'Waiting for the agent to open a page'}</span>
        <span className="stepno">Step {step || 0}{maxSteps ? ` of ${maxSteps}` : ''}</span>
      </div>
      <div className="viewport">
        {page.shot ? <img src={page.shot} alt={`Latest screenshot of ${page.title || page.url}`} />
          : <div className="noshot">{running ? 'No screenshot for this step yet' : 'The agent has not opened a page yet'}</div>}
      </div>
      <div className="pagecount"><strong>{page.count}</strong> pages visited{page.status === 'blocked' ? ' · latest page blocked the agent' : ''}</div>
    </section>
  )
}
