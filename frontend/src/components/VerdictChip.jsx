import React, { useState } from 'react';
import { TIER_CONFIG, REASON_DESCRIPTIONS } from '../constants/reasons';

export default function VerdictChip({ tier, reasons = [], className = '', showDetails = false }) {
  const [expanded, setExpanded] = useState(false);
  const normalizedTier = (tier || 'UNRESOLVED').toUpperCase();
  const config = TIER_CONFIG[normalizedTier] || TIER_CONFIG.UNRESOLVED;

  return (
    <div className={`inline-flex flex-col gap-1 ${className}`}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold tracking-wide border transition-all focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400"
        style={{
          backgroundColor: config.bg,
          color: config.text,
          borderColor: config.border
        }}
        title={reasons.map(r => REASON_DESCRIPTIONS[r] || r).join(' • ') || config.label}
        aria-label={`Verdict: ${config.label}`}
      >
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: config.color }}
        />
        <span>{config.label}</span>
        {reasons && reasons.length > 0 && (
          <span className="text-[10px] opacity-75 ml-0.5">({reasons.length})</span>
        )}
      </button>

      {(expanded || showDetails) && reasons && reasons.length > 0 && (
        <div
          className="p-2 rounded bg-slate-900/95 border border-slate-700 text-[11px] text-slate-200 shadow-xl max-w-xs space-y-1 z-20 animate-fade-in"
          style={{ borderLeftColor: config.color, borderLeftWidth: '3px' }}
        >
          <div className="font-semibold text-slate-400 text-[10px] uppercase tracking-wider">
            Deterministic Reason Codes
          </div>
          {reasons.map((r, idx) => (
            <div key={idx} className="flex flex-col gap-0.5">
              <span className="font-mono text-[10px] font-bold text-slate-300">{r}</span>
              <span className="text-slate-400 leading-tight">
                {REASON_DESCRIPTIONS[r] || r}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
