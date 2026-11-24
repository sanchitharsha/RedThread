import React from 'react';
import { Camera, ExternalLink, ShieldCheck, ShieldAlert, AlertCircle } from 'lucide-react';

export default function BrowserView({
  latestScreenshot,
  currentUrl,
  stepNumber,
  status,
  blockReason
}) {
  return (
    <div className="card flex flex-col h-full overflow-hidden border-slate-800">
      {/* Panel Header */}
      <div className="px-3.5 py-2.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Camera size={15} className="text-red-400" />
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-slate-200">
            Live Browser View
          </span>
        </div>
        <div className="flex items-center gap-2">
          {status === 'blocked' ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-950 border border-red-700 text-red-300">
              <ShieldAlert size={11} />
              BLOCKED
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 border border-slate-700 text-slate-300">
              <ShieldCheck size={11} className="text-slate-400" />
              SANDBOX
            </span>
          )}
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
            Step #{stepNumber || 0}
          </span>
        </div>
      </div>

      {/* URL bar */}
      <div className="px-3 py-1.5 bg-slate-950/70 border-b border-slate-800/80 flex items-center gap-2 text-xs">
        <span className="text-[10px] font-mono text-slate-500 uppercase">URL:</span>
        <span className="font-mono text-slate-300 truncate flex-1 text-[11px]">
          {currentUrl || 'http://localhost:8001/'}
        </span>
        {currentUrl && (
          <a
            href={currentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-slate-300 transition"
            title="Open in new tab"
          >
            <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Screenshot Container */}
      <div className="flex-1 bg-slate-950 flex items-center justify-center relative overflow-hidden min-h-[300px]">
        {latestScreenshot ? (
          <div className="w-full h-full flex flex-col items-center justify-center p-2">
            <img
              src={latestScreenshot.startsWith('/') || latestScreenshot.startsWith('http') ? latestScreenshot : `/${latestScreenshot}`}
              alt={`Browser state at step ${stepNumber}`}
              className="max-w-full max-h-[420px] object-contain rounded border border-slate-800 shadow-md"
              onError={(e) => {
                e.target.onerror = null;
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
            <div className="hidden flex-col items-center justify-center p-8 text-center text-slate-500">
              <Camera size={36} className="mb-2 opacity-40" />
              <p className="text-xs font-mono">Screenshot available at {latestScreenshot}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 space-y-2">
            <div className="p-4 rounded-full bg-slate-900/80 border border-slate-800 text-slate-400">
              <Camera size={32} />
            </div>
            <p className="text-xs font-mono text-slate-400">Awaiting agent screenshot</p>
            <p className="text-[11px] text-slate-600 max-w-xs">
              Screenshots captured via Chromium at 1280x800 will display live here.
            </p>
          </div>
        )}

        {/* Blocked overlay banner */}
        {status === 'blocked' && (
          <div className="absolute inset-x-0 bottom-0 p-3 bg-red-950/90 border-t border-red-800 text-red-200 text-xs backdrop-blur flex items-center gap-2">
            <AlertCircle size={16} className="text-red-400 shrink-0" />
            <div>
              <span className="font-semibold font-mono">BLOCKED: </span>
              <span>{blockReason || 'Investigation halted on challenge/bot-check page (UNRESOLVED).'}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
