import React from 'react';
import { X, ExternalLink, CheckCircle, XCircle, FileText, Camera, Shield, Calendar } from 'lucide-react';
import VerdictChip from './VerdictChip';

export default function EvidenceDrawer({
  selectedItem, // can be a node, link, or list of evidence
  evidenceList = [],
  onClose
}) {
  if (!selectedItem) return null;

  const isLink = selectedItem.source !== undefined && selectedItem.target !== undefined;
  const isNode = !isLink;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-slate-950 border-l border-slate-800 shadow-2xl z-50 flex flex-col animate-fade-in">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-red-400" />
          <div>
            <h3 className="text-sm font-bold text-white font-mono">
              {isLink ? `Edge: ${selectedItem.type}` : `Node: ${selectedItem.label || selectedItem.id}`}
            </h3>
            <p className="text-[11px] text-slate-400">
              {isLink ? `${typeof selectedItem.source === 'object' ? selectedItem.source.id : selectedItem.source} ➔ ${typeof selectedItem.target === 'object' ? selectedItem.target.id : selectedItem.target}` : `Type: ${selectedItem.type}`}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
        >
          <X size={18} />
        </button>
      </div>

      {/* Tier & Reasons for links */}
      {isLink && selectedItem.tier && (
        <div className="px-4 py-3 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between">
          <span className="text-xs text-slate-400 font-mono">Verdict Tier:</span>
          <VerdictChip tier={selectedItem.tier} reasons={selectedItem.reasons || []} showDetails={true} />
        </div>
      )}

      {/* Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs">
        <div className="flex items-center justify-between text-slate-400">
          <span className="uppercase text-[11px] font-semibold text-slate-500">
            Associated Evidence ({evidenceList.length})
          </span>
          <span className="text-[10px] text-slate-500">Rule 3: Verbatim Quotes Verified</span>
        </div>

        {evidenceList.length === 0 ? (
          <div className="card p-6 text-center text-slate-500">
            <p>No direct Evidence objects linked to this element.</p>
          </div>
        ) : (
          evidenceList.map((ev, idx) => (
            <div
              key={ev.id || idx}
              className="card p-3.5 bg-slate-900/80 border-slate-800 space-y-2.5 hover:border-slate-700 transition"
            >
              {/* Top metadata */}
              <div className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-bold">
                    Tier {ev.source_tier || 'C'}
                  </span>
                  <span className="text-slate-400 truncate max-w-[200px]" title={ev.id}>
                    {ev.id}
                  </span>
                </div>

                {/* Quote Verified Tick/Cross */}
                {ev.quote_verified ? (
                  <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px]">
                    <CheckCircle size={13} />
                    <span>Verified</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-rose-400 text-[11px]">
                    <XCircle size={13} />
                    <span>Unverified (Dropped)</span>
                  </span>
                )}
              </div>

              {/* Verbatim Quote */}
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800/80 text-slate-200">
                <span className="text-[10px] uppercase text-slate-500 font-semibold block mb-1">
                  Verbatim Evidence Quote:
                </span>
                <p className="font-mono text-xs leading-relaxed text-amber-200/90 whitespace-pre-wrap">
                  "{ev.quote}"
                </p>
              </div>

              {/* Source URL & Timestamp */}
              <div className="space-y-1 text-[11px] text-slate-400">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="text-slate-500">URL:</span>
                  <a
                    href={ev.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-400 hover:underline truncate flex items-center gap-1"
                  >
                    <span>{ev.source_url}</span>
                    <ExternalLink size={11} className="shrink-0" />
                  </a>
                </div>

                {ev.retrieved_at && (
                  <div className="flex items-center gap-1.5 text-slate-500 text-[10px]">
                    <Calendar size={11} />
                    <span>{new Date(ev.retrieved_at).toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Screenshot Thumbnail if present */}
              {ev.screenshot_path && (
                <div className="mt-2 pt-2 border-t border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block mb-1">
                    Captured Screenshot:
                  </span>
                  <img
                    src={ev.screenshot_path.startsWith('/') ? ev.screenshot_path : `/${ev.screenshot_path}`}
                    alt="Evidence thumbnail"
                    className="w-full max-h-32 object-cover rounded border border-slate-800"
                  />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
