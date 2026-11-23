# M2 notes (matching/, tests/golden/)

Run (repo root, Python 3.11+): `pip install -r matching/requirements-m2.txt`
- `pytest tests/golden tests/test_normalise.py tests/test_verify.py` (offline) or `pytest tests` (all M2 tests)
- `LLM_PROVIDER=fake OFFLINE=1 python -m matching.demo`   (regex stand-in, no key)
- `python -m matching.connectors.cpsc <number> --fields --save-sample`   (ONLINE: saves the real hero fixture, prints real field names)
- `python scripts/pick_hero.py`   (ONLINE: hero-recall candidates)

## Contract changes proposed to M3 (none made; models.py untouched)
1. `ExtractedListing`: add `retrieved_at: Optional[datetime]`, `source_tier: SourceTier = "C"`,
   `screenshot_path: Optional[str]`. Evidence needs them; today `matching/capture_index.py` carries them
   process-locally (keyed by source_url), which breaks across processes/replays.
2. `RecallRecord`: add `status: Optional[str]` (needed for CONFLICT_STATUS) and `fetched_at: Optional[datetime]`.
3. Optional: `ExtractedListing.dropped: list[str]` so QUOTE_UNVERIFIED does not rely on the same side channel.

## Integration notes
- `rate()` is pure on verified fields. Optional post-steps for the orchestrator: `annotate_dropped(result)`
  (adds QUOTE_UNVERIFIED if extraction dropped fields; never changes the tier) and
  `apply_conflicts(result, find_conflicts(a, b))` when a second official record exists.
- Listing ids: `<slug>` for a single listing, `<slug>#v1..` for variants (slug from the URL path, e.g. `l01`).
- Capture status != ok -> `extract_listings` returns one empty listing with that status, no LLM call; `rate` -> UNRESOLVED [BLOCKED | EXTRACT_FAIL].
- Evidence ids are `ev_<sha1(url+normalised quote)[:12]>` (stable; same id on Quoted.evidence_id and Evidence.id).
- Recall-side evidence: `method="official_api_record"` (value straight from the CPSC record) or `"notice_extract+quote_check"`.

## Deliberate deviations (all only make results MORE cautious)
- Missing/unverified brand on either side with an identifier hit -> RELATED [.., QUOTE_UNVERIFIED] (BRAND_DIFF only when both brands present and different).
- Page ok but nothing identifying verified -> UNRESOLVED [EXTRACT_FAIL], not NO_MATCH.
- Models shorter than 3 alphanumerics are never matched on.
- NAME_ONLY similarity = max(token-set similarity of product name vs recall title, fuzzy ratio of model strings); only ever RELATED.
- Range scope compares only verified listing dates; mixed/straddling dates -> SCOPE_UNVERIFIED.
