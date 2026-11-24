import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import StartScreen from './components/StartScreen';
import BrowserView from './components/BrowserView';
import ActionLog from './components/ActionLog';
import GraphView from './components/GraphView';
import EvidenceDrawer from './components/EvidenceDrawer';
import ExtractionPanel from './components/ExtractionPanel';
import ReportView from './components/ReportView';

export default function App() {
  const [activeTab, setActiveTab] = useState('investigation');
  const [runId, setRunId] = useState(null);
  const [runMode, setRunMode] = useState('live'); // 'live' | 'recorded'
  const [isDemoData, setIsDemoData] = useState(false);
  const [replays, setReplays] = useState(['demo_run']);
  const [isLoading, setIsLoading] = useState(false);

  // Investigation streaming state
  const [events, setEvents] = useState([]);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [latestScreenshot, setLatestScreenshot] = useState(null);
  const [currentUrl, setCurrentUrl] = useState('http://localhost:8001');
  const [stepNumber, setStepNumber] = useState(0);
  const [pagesVisitedCount, setPagesVisitedCount] = useState(0);
  const [agentStatus, setAgentStatus] = useState('idle'); // 'idle' | 'running' | 'blocked' | 'completed' | 'error'
  const [blockReason, setBlockReason] = useState(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  // Extraction & Match results
  const [extractions, setExtractions] = useState([]);
  const [matchResults, setMatchResults] = useState({});
  const [report, setReport] = useState(null);

  // Evidence Drawer state
  const [selectedItem, setSelectedItem] = useState(null);
  const [evidenceList, setEvidenceList] = useState([]);

  const eventSourceRef = useRef(null);

  // Load replays list on mount
  useEffect(() => {
    fetch('/api/replays')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setReplays(data.map(r => typeof r === 'string' ? r : r.run_id));
        }
      })
      .catch(() => {});
  }, []);

  // Handle Demo Data toggle
  useEffect(() => {
    if (isDemoData) {
      handleStartReplay('demo_run');
    }
  }, [isDemoData]);

  // Clean up SSE on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const resetState = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setEvents([]);
    setGraphData({ nodes: [], links: [] });
    setLatestScreenshot(null);
    setCurrentUrl('http://localhost:8001');
    setStepNumber(0);
    setPagesVisitedCount(0);
    setAgentStatus('running');
    setBlockReason(null);
    setCurrentStepIndex(0);
    setExtractions([]);
    setMatchResults({});
    setReport(null);
    setSelectedItem(null);
    setEvidenceList([]);
  };

  const handleStartInvestigation = async (recallRef, shopUrl) => {
    setIsLoading(true);
    resetState();
    setRunMode('live');

    try {
      const res = await fetch('/api/investigations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recall_ref: recallRef, shop_url: shopUrl })
      });
      const data = await res.json();
      const newRunId = data.run_id;
      setRunId(newRunId);
      setIsLoading(false);
      connectEventSource(newRunId);
    } catch (err) {
      console.error('Failed to start investigation', err);
      setIsLoading(false);
      setAgentStatus('error');
    }
  };

  const handleStartReplay = async (replayId) => {
    setIsLoading(true);
    resetState();
    setRunMode('recorded');

    try {
      const res = await fetch('/api/investigations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ replay_id: replayId })
      });
      const data = await res.json();
      const newRunId = data.run_id;
      setRunId(newRunId);
      setIsLoading(false);
      connectEventSource(newRunId);
    } catch (err) {
      console.error('Failed to start replay', err);
      setIsLoading(false);
      setAgentStatus('error');
    }
  };

  const connectEventSource = (id) => {
    if (eventSourceRef.current) eventSourceRef.current.close();

    const es = new EventSource(`/api/investigations/${id}/events`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const ev = JSON.parse(event.data);
        handleStreamEvent(ev, id);
      } catch (err) {
        console.error('Failed to parse SSE event', err);
      }
    };

    es.onerror = () => {
      es.close();
    };
  };

  const handleStreamEvent = (ev, currentRunId) => {
    setEvents(prev => [...prev, ev]);

    const type = ev.type;
    const payload = ev.payload || {};

    if (type === 'step_started') {
      const stepIdx = payload.step_index || 0;
      setStepNumber(stepIdx);
      if (stepIdx < 2) setCurrentStepIndex(1); // harvest notice
      else if (stepIdx < 5) setCurrentStepIndex(2); // discover
      else setCurrentStepIndex(3); // inspect
    } else if (type === 'page_visited') {
      setPagesVisitedCount(prev => prev + 1);
      if (payload.url) setCurrentUrl(payload.url);
      if (payload.screenshot_path) setLatestScreenshot(payload.screenshot_path);
      if (payload.status === 'blocked') {
        setAgentStatus('blocked');
        setBlockReason(payload.block_reason || 'Anti-bot challenge barrier');
      }
    } else if (type === 'extraction') {
      setCurrentStepIndex(4); // extract
      if (payload.listing) {
        setExtractions(prev => [...prev, payload.listing]);
      }
    } else if (type === 'match_result') {
      setCurrentStepIndex(5); // match
      if (payload.listing_id) {
        setMatchResults(prev => ({ ...prev, [payload.listing_id]: payload }));
      }
    } else if (type === 'graph_delta') {
      const newNodes = payload.nodes || [];
      const newLinks = payload.links || [];

      setGraphData(prev => {
        const existingNodeIds = new Set(prev.nodes.map(n => n.id));
        const existingLinkIds = new Set(prev.links.map(l => l.id));

        const updatedNodes = [...prev.nodes];
        newNodes.forEach(n => {
          if (!existingNodeIds.has(n.id)) {
            updatedNodes.push(n);
            existingNodeIds.add(n.id);
          }
        });

        const updatedLinks = [...prev.links];
        newLinks.forEach(l => {
          if (!existingLinkIds.has(l.id)) {
            updatedLinks.push(l);
            existingLinkIds.add(l.id);
          }
        });

        return { nodes: updatedNodes, links: updatedLinks };
      });
    } else if (type === 'run_finished') {
      setCurrentStepIndex(6); // report
      setAgentStatus('completed');
      if (eventSourceRef.current) eventSourceRef.current.close();

      // Fetch final report & complete graph
      fetch(`/api/investigations/${currentRunId}/report`)
        .then(res => res.json())
        .then(data => setReport(data))
        .catch(() => {});

      fetch(`/api/investigations/${currentRunId}/graph`)
        .then(res => res.json())
        .then(data => setGraphData(data))
        .catch(() => {});
    }
  };

  // Fetch Evidence details when a node or link is clicked
  const handleSelectElement = async (elem) => {
    setSelectedItem(elem);
    setEvidenceList([]);

    const evidenceIds = elem.evidence || elem.evidence_ids || [];
    if (evidenceIds.length > 0) {
      try {
        const promises = evidenceIds.map(eid =>
          fetch(`/api/evidence/${eid}`).then(res => res.ok ? res.json() : null)
        );
        const results = await Promise.all(promises);
        setEvidenceList(results.filter(Boolean));
      } catch (err) {
        console.error('Failed to fetch evidence', err);
      }
    }
  };

  const handleExportJson = () => {
    if (!runId) return;
    window.open(`/api/investigations/${runId}/export.json`, '_blank');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        runMode={runMode}
        isDemoData={isDemoData}
        setIsDemoData={setIsDemoData}
        runId={runId}
        status={agentStatus}
      />

      {/* Main Screen Content */}
      <main className="flex-1 flex flex-col p-4 max-w-7xl mx-auto w-full">
        {!runId && events.length === 0 ? (
          <StartScreen
            onStartInvestigation={handleStartInvestigation}
            onStartReplay={handleStartReplay}
            isLoading={isLoading}
            replays={replays}
          />
        ) : (
          <>
            {/* Quick Status Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 mb-4 text-xs font-mono">
              <div className="flex items-center gap-3">
                <span className="text-slate-400">Run:</span>
                <span className="font-bold text-white">{runId || 'preview'}</span>
                <span className="text-slate-600">|</span>
                <span className="text-slate-400">Status:</span>
                <span className={`font-semibold uppercase ${agentStatus === 'running' ? 'text-amber-400' : agentStatus === 'blocked' ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {agentStatus}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => { resetState(); setRunId(null); }}
                  className="text-slate-400 hover:text-white underline text-[11px]"
                >
                  New Investigation
                </button>
              </div>
            </div>

            {/* Tab Views */}
            {activeTab === 'investigation' && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-[640px]">
                {/* Left: Live Browser View */}
                <div className="lg:col-span-5 h-[480px] lg:h-auto">
                  <BrowserView
                    latestScreenshot={latestScreenshot}
                    currentUrl={currentUrl}
                    stepNumber={stepNumber}
                    status={agentStatus}
                    blockReason={blockReason}
                  />
                </div>

                {/* Middle: Action Log */}
                <div className="lg:col-span-4 h-[480px] lg:h-auto">
                  <ActionLog
                    events={events}
                    currentStepIndex={currentStepIndex}
                    pagesVisitedCount={pagesVisitedCount}
                  />
                </div>

                {/* Right: Field Extractions */}
                <div className="lg:col-span-3 h-[480px] lg:h-auto">
                  <ExtractionPanel
                    extractions={extractions}
                    matchResults={matchResults}
                  />
                </div>
              </div>
            )}

            {activeTab === 'graph' && (
              <div className="flex-1 h-[700px]">
                <GraphView
                  graphData={graphData}
                  onSelectNode={handleSelectElement}
                  onSelectLink={handleSelectElement}
                  selectedElement={selectedItem}
                />
              </div>
            )}

            {activeTab === 'report' && (
              <ReportView
                report={report}
                runId={runId}
                modeBadge={runMode}
                onExportJson={handleExportJson}
              />
            )}
          </>
        )}
      </main>

      {/* Slide-out Evidence Drawer */}
      <EvidenceDrawer
        selectedItem={selectedItem}
        evidenceList={evidenceList}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
