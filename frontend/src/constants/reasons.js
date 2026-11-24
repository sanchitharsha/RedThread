export const REASON_DESCRIPTIONS = {
  ID_MODEL_EXACT: "Exact product model number matches official recall notice",
  ID_GTIN_EXACT: "Exact GTIN/UPC barcode matches official recall notice",
  BRAND_EQ: "Brand matches official recall notice",
  BRAND_DIFF: "Brand differs from official notice",
  SCOPE_ALL_UNITS: "All manufactured units are covered by recall scope",
  SCOPE_IN_RANGE: "Production date or lot number falls within recall range",
  SCOPE_UNVERIFIED: "Production date or lot number could not be verified on listing",
  SCOPE_OUTSIDE: "Production date or lot number is outside recall scope",
  NAME_ONLY: "Brand matches with similar product name, but no identifier overlap",
  SRC_TIER_NOT_A: "Source is non-authoritative",
  QUOTE_UNVERIFIED: "Field dropped because evidence quote was not found verbatim in page text",
  CONFLICT_MODELS: "Conflicting model numbers reported between official authorities",
  CONFLICT_SCOPE: "Conflicting scope dates or ranges between sources",
  CONFLICT_HAZARD: "Conflicting hazard descriptions between sources",
  CONFLICT_REMEDY: "Conflicting remedy instructions between sources",
  CONFLICT_STATUS: "Conflicting recall status between sources",
  BLOCKED: "Investigation halted due to anti-bot challenge or verification gate",
  EXTRACT_FAIL: "Automated field extraction encountered an error on page content"
};

export const TIER_CONFIG = {
  CONFIRMED: {
    label: "CONFIRMED",
    bg: "#450a0a",
    text: "#fca5a5",
    border: "#991b1b",
    badge: "border-red-700 bg-red-950/80 text-red-300",
    color: "#ef4444"
  },
  LIKELY: {
    label: "LIKELY",
    bg: "#431407",
    text: "#fdba74",
    border: "#c2410c",
    badge: "border-orange-700 bg-orange-950/80 text-orange-300",
    color: "#f97316"
  },
  RELATED: {
    label: "RELATED",
    bg: "#451a03",
    text: "#fcd34d",
    border: "#b45309",
    badge: "border-amber-700 bg-amber-950/80 text-amber-300",
    color: "#f59e0b"
  },
  CONFLICT: {
    label: "CONFLICT",
    bg: "#3b0764",
    text: "#d8b4fe",
    border: "#7e22ce",
    badge: "border-purple-700 bg-purple-950/80 text-purple-300",
    color: "#a855f7"
  },
  NO_MATCH: {
    label: "NO MATCH",
    bg: "#1e293b",
    text: "#cbd5e1",
    border: "#475569",
    badge: "border-slate-600 bg-slate-800 text-slate-300",
    color: "#64748b"
  },
  UNRESOLVED: {
    label: "UNRESOLVED",
    bg: "#27272a",
    text: "#e4e4e7",
    border: "#52525b",
    badge: "border-zinc-600 bg-zinc-800 text-zinc-300",
    color: "#a1a1aa"
  }
};

export const NODE_COLORS = {
  Recall: "#dc2626",
  ProductModel: "#2563eb",
  Identifier: "#0891b2",
  Listing: "#d97706",
  Seller: "#7c3aed",
  Brand: "#0284c7",
  Hazard: "#b91c1c",
  Remedy: "#059669"
};
