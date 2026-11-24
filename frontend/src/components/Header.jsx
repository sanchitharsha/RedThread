import React from 'react';
import { ShieldAlert, Radio, Database, FileText, Share2, Layers } from 'lucide-react';

export default function Header({
  activeTab,
  setActiveTab,
  runMode, // 'live' | 'recorded'
  isDemoData,
  setIsDemoData,
  runId,
  status
}) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-30 px-4 py-3">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-red-600/20 border border-red-500/40 flex items-center justify-center text-red-500">
            <ShieldAlert size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-lg tracking-tight text-white font-mono">
                REDTHREAD
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                v0.1.0-proto
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Product Recall Investigation Engine
            </p>
          </div>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2">
          {/* Sandbox Shop Badge */}
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-amber-950/40 border border-amber-600/50 text-amber-300">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Sandbox shop
          </span>

          {/* Live run / Recorded run badge */}
          {runMode === 'live' ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-red-950/60 border border-red-500/50 text-red-300">
              <span className="pulse-dot bg-red-500" />
              Live run
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-purple-950/50 border border-purple-500/50 text-purple-300">
              <Radio size={12} className="text-purple-400" />
              Recorded run
            </span>
          )}

          {/* Demo Data Toggle */}
          <label className="flex items-center gap-2 ml-2 px-3 py-1 rounded-md bg-slate-900 border border-slate-700 text-xs text-slate-300 cursor-pointer hover:bg-slate-800 transition">
            <input
              type="checkbox"
              checked={isDemoData}
              onChange={(e) => setIsDemoData(e.target.checked)}
              className="rounded bg-slate-800 border-slate-600 text-red-600 focus:ring-0 cursor-pointer"
            />
            <Database size={13} className="text-slate-400" />
            <span>Use demo data</span>
          </label>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-800">
          <button
            type="button"
            onClick={() => setActiveTab('investigation')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'investigation'
                ? 'bg-red-950/80 border border-red-600/50 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers size={14} />
            Investigation
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'graph'
                ? 'bg-red-950/80 border border-red-600/50 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Share2 size={14} />
            Evidence Graph
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('report')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'report'
                ? 'bg-red-950/80 border border-red-600/50 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText size={14} />
            Exposure Report
          </button>
        </nav>
      </div>
    </header>
  );
}
