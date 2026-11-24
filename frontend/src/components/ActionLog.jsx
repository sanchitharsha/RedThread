import React, { useRef, useEffect } from 'react';
import { Terminal, CheckCircle2, Circle, ArrowRight, Compass, Wrench, Globe, Clock } from 'lucide-react';

const PIPELINE_STEPS = [
  { id: 'official_record', label: 'Official Record' },
  { id: 'harvest_notice', label: 'Harvest Notice' },
  { id: 'discover', label: 'Discover' },
  { id: 'inspect', label: 'Inspect' },
  { id: 'extract', label: 'Extract' },
  { id: 'match', label: 'Match' },
  { id: 'report', label: 'Report' }
];

export default function ActionLog({
  events = [],
  currentStepIndex = 0,
  pagesVisitedCount = 0
}) {
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="card flex flex-col h-full overflow-hidden border-slate-800">
      {/* Panel Header */}
      <div className="px-3.5 py-2.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal size={15} className="text-amber-400" />
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-slate-200">
            Action Log & Stepper
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-950/40 border border-amber-800/40 text-amber-300">
            <span className="font-bold">{pagesVisitedCount}</span> pages visited
          </span>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
            {events.length} events
          </span>
        </div>
      </div>

      {/* Pipeline Stepper */}
      <div className="px-3 py-2 bg-slate-950/80 border-b border-slate-800/80 overflow-x-auto">
        <div className="flex items-center gap-1.5 min-w-max text-[11px] font-mono">
          {PIPELINE_STEPS.map((step, idx) => {
            const isCompleted = idx < currentStepIndex;
            const isCurrent = idx === currentStepIndex;
            return (
              <React.Fragment key={step.id}>
                <div
                  className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
                    isCurrent
                      ? 'bg-red-950 border border-red-600 text-red-200 font-bold'
                      : isCompleted
                      ? 'bg-slate-900 border border-slate-700 text-slate-300'
                      : 'bg-transparent text-slate-600'
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 size={11} className="text-red-400" />
                  ) : isCurrent ? (
                    <Circle size={11} className="text-red-500 fill-red-500" />
                  ) : (
                    <Circle size={11} className="text-slate-600" />
                  )}
                  <span>{step.label}</span>
                </div>
                {idx < PIPELINE_STEPS.length - 1 && (
                  <ArrowRight size={10} className="text-slate-700 shrink-0" />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-950/40 font-mono text-xs">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-600 p-6">
            <Compass size={28} className="mb-2 opacity-50" />
            <p>Awaiting investigation stream...</p>
          </div>
        ) : (
          events.map((ev, idx) => {
            const type = ev.type || 'event';
            const payload = ev.payload || {};
            const ts = ev.ts ? new Date(ev.ts).toLocaleTimeString() : '';

            let icon = <Clock size={12} className="text-slate-500" />;
            let badgeBg = 'bg-slate-800 text-slate-400';

            if (type === 'tool_call') {
              icon = <Wrench size={12} className="text-amber-400" />;
              badgeBg = 'bg-amber-950/60 border border-amber-700/50 text-amber-300';
            } else if (type === 'page_visited') {
              icon = <Globe size={12} className="text-sky-400" />;
              badgeBg = 'bg-sky-950/60 border border-sky-700/50 text-sky-300';
            } else if (type === 'match_result') {
              icon = <CheckCircle2 size={12} className="text-red-400" />;
              badgeBg = 'bg-red-950/60 border border-red-700/50 text-red-300';
            } else if (type === 'run_started' || type === 'run_finished') {
              badgeBg = 'bg-purple-950/60 border border-purple-700/50 text-purple-300';
            }

            return (
              <div
                key={idx}
                className="p-2 rounded bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 transition"
              >
                <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                  <div className="flex items-center gap-1.5">
                    {icon}
                    <span className={`px-1.5 py-0.2 rounded font-semibold uppercase ${badgeBg}`}>
                      {type}
                    </span>
                    {ev.seq && <span className="text-slate-600">#{ev.seq}</span>}
                  </div>
                  <span>{ts}</span>
                </div>

                {/* Specific Event Content */}
                {type === 'tool_call' && (
                  <div className="space-y-0.5 text-slate-300">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-amber-400 font-bold">{payload.tool || payload.name}</span>
                      <span className="text-slate-500 text-[11px] truncate">
                        {JSON.stringify(payload.args || {})}
                      </span>
                    </div>
                    {payload.reason && (
                      <p className="text-[11px] text-slate-400 italic">
                        ↳ Reason: "{payload.reason}"
                      </p>
                    )}
                  </div>
                )}

                {type === 'page_visited' && (
                  <div className="text-slate-300">
                    <p className="truncate font-semibold text-sky-300">{payload.url}</p>
                    {payload.title && <p className="text-slate-400 text-[11px] truncate">{payload.title}</p>}
                  </div>
                )}

                {type === 'match_result' && (
                  <div className="flex items-center justify-between gap-2 text-slate-300">
                    <span className="font-bold">{payload.listing_id}</span>
                    <span className="text-red-400 font-semibold">{payload.tier}</span>
                    <span className="text-[10px] text-slate-500 truncate max-w-[140px]">
                      {(payload.reasons || []).join(', ')}
                    </span>
                  </div>
                )}

                {type !== 'tool_call' && type !== 'page_visited' && type !== 'match_result' && (
                  <div className="text-[11px] text-slate-400 truncate">
                    {payload.title || payload.message || payload.status || JSON.stringify(payload)}
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
