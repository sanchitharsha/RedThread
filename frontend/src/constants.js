const env = import.meta.env || {}  // empty under plain Node (unit tests)
export const API = env.VITE_API_URL || 'http://localhost:8000'
export const DEFAULT_RECALL = env.VITE_RECALL_REF || '26419'
export const DEFAULT_SHOP = env.VITE_SHOP_URL || 'http://localhost:8001'

export const TIERS = ['CONFIRMED', 'LIKELY', 'RELATED', 'CONFLICT', 'NO_MATCH', 'UNRESOLVED']

// Fixed colours. Never green. Colour is never the only signal: every chip carries text.
export const TIER_STYLE = {
  CONFIRMED: { label: 'Confirmed', long: 'Confirmed match', bg: '#b3261e', fg: '#ffffff' },
  LIKELY: { label: 'Likely', long: 'Likely match', bg: '#d9660b', fg: '#ffffff' },
  RELATED: { label: 'Related', long: 'Related, not confirmed', bg: '#f0b429', fg: '#1b1b1b' },
  CONFLICT: { label: 'Conflict', long: 'Conflict between official sources', bg: '#6b3fa0', fg: '#ffffff' },
  NO_MATCH: { label: 'No match found', long: 'No match found in checked sources', bg: '#5a6779', fg: '#ffffff' },
  UNRESOLVED: { label: 'Unresolved', long: 'Unresolved', bg: '#d5dae1', fg: '#1b1b1b' },
}

export const NODE_COLOR = {
  Recall: '#14305a', ProductModel: '#2f7db8', Identifier: '#8a5a9e', Listing: '#4b5563',
  Seller: '#a0691e', Brand: '#5b6b8a', Hazard: '#9a3b5b', Remedy: '#6b6f8d',
}

export const REASON_TEXT = {
  ID_MODEL_EXACT: 'The model number matches the recall exactly, ignoring spaces, hyphens and capitals.',
  ID_GTIN_EXACT: 'The barcode (GTIN) is valid and matches one named in the recall.',
  BRAND_EQ: 'The brand agrees with the recall.',
  BRAND_DIFF: 'The brand differs from the recalled brand, so this cannot be matched.',
  SCOPE_ALL_UNITS: 'The notice covers all units of this model.',
  SCOPE_IN_RANGE: 'The listing shows a date or lot inside the recall range.',
  SCOPE_UNVERIFIED: 'The notice limits scope by date or lot and the listing does not show enough to check. A person needs to check the label.',
  SCOPE_OUTSIDE: 'The listing shows a date or lot outside the recall range.',
  NAME_ONLY: 'Only the name or brand looks similar. No identifier overlaps.',
  SRC_TIER_NOT_A: 'The recall record is not from an official authority, so the result is capped at Likely.',
  QUOTE_UNVERIFIED: 'A quote could not be found in the page text, so that field was dropped.',
  CONFLICT_MODELS: 'Official sources list different models.',
  CONFLICT_SCOPE: 'Official sources give different date or lot ranges.',
  CONFLICT_HAZARD: 'Official sources describe the hazard differently.',
  CONFLICT_REMEDY: 'Official sources give different remedies.',
  CONFLICT_STATUS: 'Official sources disagree on the status of the notice.',
  BLOCKED: 'The page blocked the agent with a bot check. Redthread does not try to get around blocks.',
  EXTRACT_FAIL: 'Extraction failed or found nothing it could verify.',
}

export const STAGES = [
  ['official', 'Official record'], ['harvest', 'Harvest notice'], ['discover', 'Discover'],
  ['inspect', 'Inspect'], ['extract', 'Extract'], ['match', 'Match'], ['report', 'Report'],
]

// Fallback only. The API sends the authoritative disclaimer in ReportJSON.
export const DISCLAIMER =
  "Redthread reports what was matched in the sources it checked. 'No match found in checked sources' is not a statement about product safety. Always follow the official notice and remedy."
