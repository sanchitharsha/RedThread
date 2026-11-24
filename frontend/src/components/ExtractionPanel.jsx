import React from 'react';
import { CheckCircle2, XCircle, FileCode, Tag, Calendar, User, Package } from 'lucide-react';
import VerdictChip from './VerdictChip';

export default function ExtractionPanel({
  extractions = [],
  matchResults = {}
}) {
  return (
    <div className="card flex flex-col h-full overflow-hidden border-slate-800">
      <div className="px-3.5 py-2.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileCode size={15} className="text-purple-400" />
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-slate-200">
            Field Extraction & Verifications
          </span>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
          {extractions.length} listings extracted
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 font-mono text-xs">
        {extractions.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-600 p-6">
            <Package size={28} className="mb-2 opacity-50" />
            <p>Extracted listings will appear here as pages are parsed.</p>
          </div>
        ) : (
          extractions.map((ext, idx) => {
            const result = matchResults[ext.listing_id];
            return (
              <div
                key={ext.listing_id || idx}
                className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-2.5"
              >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">
                      {ext.listing_id}
                    </span>
                    <span className="text-[11px] text-slate-400 truncate max-w-[220px]">
                      {ext.source_url}
                    </span>
                  </div>
                  {result && (
                    <VerdictChip tier={result.tier} reasons={result.reasons} />
                  )}
                </div>

                {/* Fields Table */}
                <div className="space-y-1.5 text-[11px]">
                  {/* Brand */}
                  {ext.brand && (
                    <div className="flex items-start justify-between gap-2 p-1.5 rounded bg-slate-950/60 border border-slate-900">
                      <div className="flex items-center gap-1.5 text-slate-400">
                        <Tag size={12} className="text-sky-400" />
                        <span>Brand:</span>
                        <span className="font-bold text-slate-200">{ext.brand.value}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {ext.brand.verified ? (
                          <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                            <CheckCircle2 size={11} /> Verified Quote
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                            <XCircle size={11} /> Dropped
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Product Name */}
                  {ext.product_name && (
                    <div className="flex items-start justify-between gap-2 p-1.5 rounded bg-slate-950/60 border border-slate-900">
                      <div className="flex items-center gap-1.5 text-slate-400">
                        <Package size={12} className="text-amber-400" />
                        <span>Product:</span>
                        <span className="text-slate-200 truncate max-w-[200px]">{ext.product_name.value}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {ext.product_name.verified ? (
                          <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                            <CheckCircle2 size={11} /> Verified
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                            <XCircle size={11} /> Dropped
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Model Numbers */}
                  {ext.model_numbers && ext.model_numbers.length > 0 && (
                    <div className="p-1.5 rounded bg-slate-950/60 border border-slate-900 space-y-1">
                      <span className="text-slate-400 text-[10px] uppercase font-semibold">
                        Model Numbers:
                      </span>
                      {ext.model_numbers.map((m, mIdx) => (
                        <div key={mIdx} className="flex items-center justify-between text-slate-300 pl-2">
                          <span className="font-bold">{m.value}</span>
                          {m.verified ? (
                            <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                              <CheckCircle2 size={11} />
                            </span>
                          ) : (
                            <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                              <XCircle size={11} />
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* GTINs */}
                  {ext.gtins && ext.gtins.length > 0 && (
                    <div className="p-1.5 rounded bg-slate-950/60 border border-slate-900 space-y-1">
                      <span className="text-slate-400 text-[10px] uppercase font-semibold">
                        GTINs / UPCs:
                      </span>
                      {ext.gtins.map((g, gIdx) => (
                        <div key={gIdx} className="flex items-center justify-between text-slate-300 pl-2">
                          <span>{g.value}</span>
                          {g.verified ? (
                            <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                              <CheckCircle2 size={11} />
                            </span>
                          ) : (
                            <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                              <XCircle size={11} />
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Scope / Date Info */}
                  {ext.lot_or_date_info && ext.lot_or_date_info.length > 0 && (
                    <div className="p-1.5 rounded bg-slate-950/60 border border-slate-900 space-y-1">
                      <span className="text-slate-400 text-[10px] uppercase font-semibold">
                        Date / Lot Info:
                      </span>
                      {ext.lot_or_date_info.map((d, dIdx) => (
                        <div key={dIdx} className="flex items-center justify-between text-slate-300 pl-2">
                          <span>{d.value}</span>
                          {d.verified ? (
                            <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                              <CheckCircle2 size={11} />
                            </span>
                          ) : (
                            <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                              <XCircle size={11} />
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
