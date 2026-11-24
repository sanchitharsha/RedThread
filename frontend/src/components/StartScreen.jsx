import React, { useState } from 'react';
import { Search, Play, RotateCcw, AlertTriangle, ExternalLink, Globe } from 'lucide-react';

export default function StartScreen({
  onStartInvestigation,
  onStartReplay,
  isLoading,
  replays = []
}) {
  const [recallRef, setRecallRef] = useState('26419');
  const [shopUrl, setShopUrl] = useState('http://localhost:8001');
  const [selectedReplay, setSelectedReplay] = useState('demo_run');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (recallRef.trim()) {
      onStartInvestigation(recallRef.trim(), shopUrl.trim());
    }
  };

  const handleReplaySubmit = (e) => {
    e.preventDefault();
    if (selectedReplay) {
      onStartReplay(selectedReplay);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 animate-fade-in space-y-8">
      {/* Hero Notice */}
      <div className="card p-6 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 border border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-red-600/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-start gap-4 mb-4">
          <div className="p-3 rounded-lg bg-red-950/60 border border-red-800/50 text-red-400">
            <AlertTriangle size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Investigate Product Recall Exposure
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Autonomous browser agent inspects retailer listings against official CPSC recall notices.
              Verdicts are computed strictly by deterministic rule code; LLMs only extract fields with verbatim quotes.
            </p>
          </div>
        </div>

        {/* Start Live Investigation Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-1 space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
                Official Recall Ref / ID
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={recallRef}
                  onChange={(e) => setRecallRef(e.target.value)}
                  placeholder="e.g. 26419 or CPSC:26419"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-md text-sm text-white font-mono focus:outline-none focus:border-red-500 transition"
                  required
                />
              </div>
              <div className="flex gap-2 text-[11px] text-slate-400">
                <span>Hero Recalls:</span>
                <button
                  type="button"
                  onClick={() => setRecallRef('26419')}
                  className="text-red-400 hover:underline font-mono"
                >
                  26419
                </button>
                <button
                  type="button"
                  onClick={() => setRecallRef('26755')}
                  className="text-red-400 hover:underline font-mono"
                >
                  26755
                </button>
                <button
                  type="button"
                  onClick={() => setRecallRef('27096')}
                  className="text-red-400 hover:underline font-mono"
                >
                  27096
                </button>
              </div>
            </div>

            <div className="md:col-span-2 space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
                Target Retailer / Shop URL (Allowlisted)
              </label>
              <div className="relative flex items-center">
                <Globe size={16} className="absolute left-3 text-slate-500" />
                <input
                  type="url"
                  value={shopUrl}
                  onChange={(e) => setShopUrl(e.target.value)}
                  placeholder="http://localhost:8001"
                  className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-700 rounded-md text-sm text-white font-mono focus:outline-none focus:border-red-500 transition"
                  required
                />
              </div>
              <p className="text-[11px] text-slate-500">
                Strict domain allowlist: only allowlisted hosts and ports are permissible.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800">
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary text-sm"
            >
              <Play size={16} />
              <span>{isLoading ? 'Starting Investigation...' : 'Investigate'}</span>
            </button>

            <span className="text-xs text-slate-500 font-mono">
              Mode A: Official Recall to Shop Exposure
            </span>
          </div>
        </form>
      </div>

      {/* Replay Section */}
      <div className="card p-5 bg-slate-900/60 border border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-md bg-purple-950/60 border border-purple-800/40 text-purple-400">
              <RotateCcw size={20} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                Offline Replay / Recorded Runs
              </h3>
              <p className="text-xs text-slate-400">
                Stream previous runs from recorded event logs and screenshots without live network or LLM tokens.
              </p>
            </div>
          </div>

          <form onSubmit={handleReplaySubmit} className="flex items-center gap-2">
            <select
              value={selectedReplay}
              onChange={(e) => setSelectedReplay(e.target.value)}
              className="px-3 py-1.5 bg-slate-950 border border-slate-700 rounded text-xs text-white font-mono focus:outline-none focus:border-purple-500"
            >
              <option value="demo_run">demo_run (Golden Run)</option>
              {replays
                .filter((r) => r !== 'demo_run')
                .map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
            </select>

            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-1.5 rounded bg-purple-900/70 border border-purple-600 text-xs font-semibold text-purple-200 hover:bg-purple-800 transition flex items-center gap-1.5"
            >
              <RotateCcw size={13} />
              <span>Replay recorded run</span>
            </button>
          </form>
        </div>
      </div>

      {/* Non-Negotiable Architecture Rules Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-400">
        <div className="card p-3 border-slate-800/80">
          <div className="font-semibold text-slate-200 font-mono mb-1">Rule 1 & 2: Code Decides</div>
          <p>
            The LLM never assigns a verdict tier. Rule code decides CONFIRMED, LIKELY, RELATED, CONFLICT, NO MATCH, or UNRESOLVED.
          </p>
        </div>
        <div className="card p-3 border-slate-800/80">
          <div className="font-semibold text-slate-200 font-mono mb-1">Rule 3: Verbatim Evidence</div>
          <p>
            Every extracted model, GTIN, or scope text requires a verbatim quote verified directly against raw page text.
          </p>
        </div>
        <div className="card p-3 border-slate-800/80">
          <div className="font-semibold text-slate-200 font-mono mb-1">Rule 5 & 6: Sandboxed Agent</div>
          <p>
            LLM-driven browser agent strictly bound to domain allowlist, zero credential/purchase submissions, and untrusted page text handling.
          </p>
        </div>
      </div>
    </div>
  );
}
