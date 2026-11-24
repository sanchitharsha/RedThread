import React from 'react';
import { Download, Printer, AlertTriangle, ShieldCheck, Check, HelpCircle, Layers, ShieldAlert, ExternalLink } from 'lucide-react';
import VerdictChip from './VerdictChip';
import { TIER_CONFIG } from '../constants/reasons';

export default function ReportView({
  report,
  runId,
  modeBadge = 'live',
  onExportJson
}) {
  if (!report) {
    return (
      <div className="card p-12 text-center text-slate-500 font-mono text-sm max-w-4xl mx-auto my-8">
        <AlertTriangle size={32} className="mx-auto mb-3 text-slate-600" />
        <p>No final report available yet for this investigation.</p>
        <p className="text-xs text-slate-600 mt-1">Complete an investigation run to generate the exposure report.</p>
      </div>
    );
  }

  const counts = report.counts || {};
  const listings = report.listings || [];
  const conflicts = report.conflicts || [];
  const unresolved = report.unresolved || [];
  const sourcesChecked = report.sources_checked || [];
  const notChecked = report.not_checked || ['Other global authorities (EU Safety Gate, Health Canada)', 'External marketplace merchants'];
  const disclaimer = report.disclaimer ||
    "Redthread reports what was matched in the sources it checked. 'No match found in checked sources' is not a statement about product safety. Always follow the official notice and remedy.";

  // Sort listings by priority: CONFIRMED, LIKELY, RELATED, CONFLICT, UNRESOLVED, NO_MATCH
  const tierOrder = { CONFIRMED: 0, LIKELY: 1, RELATED: 2, CONFLICT: 3, UNRESOLVED: 4, NO_MATCH: 5 };
  const sortedListings = [...listings].sort((a, b) => {
    const orderA = tierOrder[a.tier] !== undefined ? tierOrder[a.tier] : 99;
    const orderB = tierOrder[b.tier] !== undefined ? tierOrder[b.tier] : 99;
    return orderA - orderB;
  });

  return (
    <div className="max-w-5xl mx-auto py-6 px-4 space-y-6 animate-fade-in font-sans">
      {/* Top Banner & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-white tracking-tight font-mono">
              Recall Exposure Report
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase bg-slate-800 border border-slate-700 text-slate-300">
              {modeBadge || 'live'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            Run ID: {runId || report.run_id || 'run-preview'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onExportJson}
            className="btn-secondary text-xs"
          >
            <Download size={14} />
            <span>Export JSON</span>
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="btn-secondary text-xs"
          >
            <Printer size={14} />
            <span>Print Report</span>
          </button>
        </div>
      </div>

      {/* Official Recall Summary */}
      {report.recall && (
        <div className="card p-4 bg-slate-900/90 border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono border-b border-slate-800/80 pb-2">
            <span className="text-red-400 font-bold">
              {report.recall.authority || 'CPSC'} #{report.recall.number || report.recall.recall_number}
            </span>
            <span className="text-slate-400">{report.recall.date}</span>
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              {report.recall.title}
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              <span className="text-slate-300 font-semibold">Brand:</span> {report.recall.brand || 'N/A'} •{' '}
              <span className="text-slate-300 font-semibold">Scope:</span> {report.recall.scope_type}
            </p>
          </div>
        </div>
      )}

      {/* Tier Counts Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Object.entries(TIER_CONFIG).map(([tierKey, config]) => {
          const count = counts[tierKey] || 0;
          return (
            <div
              key={tierKey}
              className="card p-3 border-slate-800 text-center flex flex-col items-center justify-center space-y-1"
              style={{ borderTop: `3px solid ${config.color}` }}
            >
              <span className="text-2xl font-mono font-bold text-white">
                {count}
              </span>
              <span
                className="text-[11px] font-mono font-semibold"
                style={{ color: config.text }}
              >
                {config.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Listings Table */}
      <div className="card overflow-hidden border-slate-800">
        <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-slate-200">
            Assessed Listings Table ({sortedListings.length})
          </h3>
          <span className="text-[11px] font-mono text-slate-500">
            Sorted by Verdict Priority
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 text-[11px]">
              <tr>
                <th className="py-2.5 px-4 font-semibold">Listing ID</th>
                <th className="py-2.5 px-4 font-semibold">Verdict Tier</th>
                <th className="py-2.5 px-4 font-semibold">Product Title / URL</th>
                <th className="py-2.5 px-4 font-semibold">Rule Reason Codes</th>
                <th className="py-2.5 px-4 font-semibold text-right">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {sortedListings.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    No listings assessed in this run.
                  </td>
                </tr>
              ) : (
                sortedListings.map((l, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/50 transition">
                    <td className="py-2.5 px-4 font-bold text-white">
                      {l.listing_id}
                    </td>
                    <td className="py-2.5 px-4">
                      <VerdictChip tier={l.tier} reasons={l.reasons || []} />
                    </td>
                    <td className="py-2.5 px-4">
                      <div className="truncate max-w-xs text-slate-200">
                        {l.title || l.url}
                      </div>
                      <a
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-sky-400 hover:underline truncate block max-w-xs"
                      >
                        {l.url}
                      </a>
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 text-[11px]">
                      {(l.reasons || []).join(', ') || '—'}
                    </td>
                    <td className="py-2.5 px-4 text-right text-slate-400">
                      {(l.evidence_ids || []).length} id(s)
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Conflicts & Unresolved Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Conflicts Panel */}
        <div className="card p-4 border-slate-800 space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-purple-400 flex items-center gap-2">
            <AlertTriangle size={14} />
            Official Notice Conflicts ({conflicts.length})
          </h3>
          {conflicts.length === 0 ? (
            <p className="text-xs text-slate-500 font-mono">
              No cross-record discrepancies identified across official sources.
            </p>
          ) : (
            <div className="space-y-2 font-mono text-xs">
              {conflicts.map((c, i) => (
                <div key={i} className="p-2.5 rounded bg-purple-950/40 border border-purple-800/40 space-y-1">
                  <span className="font-bold text-purple-300">{c.field || 'Discrepancy'}</span>
                  <p className="text-slate-300">{c.description || JSON.stringify(c)}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Unresolved Panel */}
        <div className="card p-4 border-slate-800 space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-zinc-400 flex items-center gap-2">
            <HelpCircle size={14} />
            Unresolved Determinations ({unresolved.length})
          </h3>
          {unresolved.length === 0 ? (
            <p className="text-xs text-slate-500 font-mono">
              Zero listings encountered anti-bot barriers or extraction faults.
            </p>
          ) : (
            <div className="space-y-2 font-mono text-xs">
              {unresolved.map((u, i) => (
                <div key={i} className="p-2.5 rounded bg-zinc-900 border border-zinc-700 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-200">{u.listing_id || `Item #${i + 1}`}</span>
                    <span className="text-amber-400 text-[10px] uppercase font-bold">{u.reason || 'BLOCKED'}</span>
                  </div>
                  <p className="text-slate-400 text-[11px]">{u.details || u.message || 'Page challenge encountered'}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Coverage Panel */}
      <div className="card p-4 border-slate-800 space-y-3 font-mono text-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
          Source Coverage Panel
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase">
              Sources Checked ({sourcesChecked.length}):
            </span>
            <div className="space-y-1">
              {sourcesChecked.map((s, idx) => (
                <div key={idx} className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] flex justify-between">
                  <span className="text-slate-300 truncate max-w-[240px]">{s.name || s.url}</span>
                  <span className="text-slate-500 text-[10px]">{s.retrieved_at ? new Date(s.retrieved_at).toLocaleTimeString() : ''}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-500 uppercase">
              Not Checked (Out of Scope):
            </span>
            <div className="space-y-1">
              {notChecked.map((n, idx) => (
                <div key={idx} className="p-2 rounded bg-slate-950/60 border border-slate-900 text-[11px] text-slate-500">
                  {n}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Mandatory Regulatory Disclaimer */}
      <div className="p-4 rounded-lg bg-amber-950/30 border border-amber-800/60 text-amber-200/90 text-xs space-y-1.5">
        <div className="flex items-center gap-2 font-bold font-mono text-amber-400">
          <ShieldAlert size={16} />
          <span>Notice Regarding Product Safety Determinations</span>
        </div>
        <p className="leading-relaxed">
          {disclaimer}
        </p>
      </div>
    </div>
  );
}
