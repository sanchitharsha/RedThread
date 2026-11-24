import { useState } from 'react'
import { useRun } from './useRun.js'
import { stagesFrom } from './normalize.js'
import { StartScreen } from './components/StartScreen.jsx'
import { Badges } from './components/Badges.jsx'
import { Stepper } from './components/Stepper.jsx'
import { BrowserPanel } from './components/BrowserPanel.jsx'
import { ActionLog } from './components/ActionLog.jsx'
import { GraphPanel } from './components/GraphPanel.jsx'
import { EvidenceDrawer } from './components/EvidenceDrawer.jsx'
import { ExtractionPanel } from './components/ExtractionPanel.jsx'
import { VerdictTable } from './components/VerdictTable.jsx'
import { ReportView } from './components/ReportView.jsx'

export default function App() {
  const run = useRun()
  const { state, mode, status, error, report, runId } = run
  const [view, setView] = useState('start')
  const [tab, setTab] = useState('verdicts')
  const [sel, setSel] = useState(null)

  const go = (fn) => (...a) => { setSel(null); setView('run'); fn(...a) }
  const select = (s) => {
    if (s.kind === 'link') {
      const l = s.link
      setSel({ title: `${l.type.replace('_', ' ').toLowerCase()} link`, subtitle: `${l.source.id || l.source} to ${l.target.id || l.target}`, tier: l.tier, reasons: l.reasons, evidenceIds: l.evidence })
    } else if (s.kind === 'node') {
      const n = s.node
      const ids = state.graph.links.filter((l) => [l.source, l.target].map((x) => x.id || x).includes(n.id)).flatMap((l) => l.evidence)
      setSel({ title: n.label, subtitle: n.type, evidenceIds: [...new Set(ids)] })
    } else setSel(s)
  }
  const nResults = Object.keys(state.results).length

  if (view === 'start') return <StartScreen onLive={go(run.startLive)} onReplay={go((r, id) => run.startLive(r, null, id))} onDemo={go(run.startDemo)} />

  if (view === 'report' && report) {
    return (<>
      <ReportView report={report} mode={mode} runId={runId} onBack={() => setView('run')} onEvidence={select} />
      <EvidenceDrawer sel={sel} demo={mode === 'demo'} onClose={() => setSel(null)} />
    </>)
  }

  return (
    <div className="run">
      <header className="bar">
        <button className="ghost" onClick={() => { run.stop(); setView('start') }}>Redthread</button>
        <Badges mode={mode} />
        <Stepper stages={stagesFrom(state.events)} />
        <span className="barend">
          {status === 'running' && <span className="pulse" role="status">Investigating</span>}
          {report && <button className="primary" onClick={() => setView('report')}>View exposure report</button>}
        </span>
      </header>
      {error && <p className="err banner" role="alert">{error}</p>}
      {state.recall && (
        <p className="recallline"><b>{state.recall.authority} {state.recall.number}</b> {state.recall.title}
          {state.recall.brand ? <span className="muted"> · {state.recall.brand}</span> : null}</p>)}
      <div className="grid">
        <div className="col">
          <BrowserPanel page={state.page} step={state.step} maxSteps={state.maxSteps} running={status === 'running'} />
          <ActionLog log={state.log} />
        </div>
        <div className="col">
          <GraphPanel graph={state.graph} onSelect={select} />
          <section className="panel tabs">
            <div role="tablist" aria-label="Results">
              <button role="tab" aria-selected={tab === 'verdicts'} onClick={() => setTab('verdicts')}>Verdicts ({nResults})</button>
              <button role="tab" aria-selected={tab === 'extraction'} onClick={() => setTab('extraction')}>Extraction ({state.extractions.length})</button>
            </div>
            <div role="tabpanel">
              {tab === 'verdicts' ? <VerdictTable results={state.results} onOpen={select} /> : <ExtractionPanel extractions={state.extractions} results={state.results} />}
            </div>
          </section>
        </div>
      </div>
      <EvidenceDrawer sel={sel} demo={mode === 'demo'} onClose={() => setSel(null)} />
    </div>
  )
}
