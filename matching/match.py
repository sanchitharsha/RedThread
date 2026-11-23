"""Deterministic match engine. CODE decides verdicts; no LLM output ever sets a tier.

Only VERIFIED listing fields count (verify.py). Text similarity can only ever produce
RELATED. Reason codes follow the shared contract list.

Ladder (exactly as specified):
  model_hit = canon(listing models) & canon(recall models)
  gtin_hit  = valid listing GTINs   & valid recall GTINs
  brand_ok  = brand_norm equal
  (model_hit or gtin_hit) and not brand_ok                  -> RELATED   [BRAND_DIFF]
  (model_hit or gtin_hit) and brand_ok:
      recall.source_tier != "A"                             -> LIKELY    [SRC_TIER_NOT_A]
      scope outside                                         -> RELATED   [SCOPE_OUTSIDE]
      scope all_units / in_range                            -> CONFIRMED [ID_*, BRAND_EQ, SCOPE_*]
      scope unverified                                      -> LIKELY    [SCOPE_UNVERIFIED]
  brand_ok and similarity >= 0.6                            -> RELATED   [NAME_ONLY]
  otherwise                                                 -> NO_MATCH

Additions that can only make a result MORE cautious (documented in the M2 notes):
  * capture_status != ok                  -> UNRESOLVED [BLOCKED] or [EXTRACT_FAIL]
  * page ok but nothing identifying verified -> UNRESOLVED [EXTRACT_FAIL]
  * brand missing on either side with an identifier hit -> RELATED [..., QUOTE_UNVERIFIED]
    (BRAND_DIFF is only used when both brands are present and different)
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from contracts.models import Evidence, ExtractedListing, MatchResult, Quoted, RecallRecord, Tier
from matching import capture_index as ci
from matching.normalise import (brand_norm, canon, digits, find_dates, gtin_ok,
                                model_similarity, similarity)
from matching.verify import evidence_id, norm_text, quote_ok

NAME_SIM_THRESHOLD = 0.6
MIN_MODEL_CANON_LEN = 3   # a 1-2 character "model" is not an identifier worth matching on

# Display / dedupe order for several results about the same listing. CONFLICT outranks
# LIKELY so disagreement between official sources is never hidden; UNRESOLVED outranks
# NO_MATCH because "could not check" is not "no match".
TIER_ORDER: list[str] = ["CONFIRMED", "CONFLICT", "LIKELY", "RELATED", "UNRESOLVED", "NO_MATCH"]
_RANK = {t: i for i, t in enumerate(TIER_ORDER)}


# ------------------------------------------------------------------- helpers

def recall_id_of(recall: RecallRecord) -> str:
    return f"{recall.authority}:{recall.number}"


def base_listing_id(listing_id: str) -> str:
    """'l08#v2' -> 'l08' (page-level id)."""
    return listing_id.split("#", 1)[0]


def _verified(qs: Iterable[Quoted]) -> list[Quoted]:
    return [q for q in qs if q.verified]


def _brand_ok(listing_brand: Optional[Quoted], recall: RecallRecord) -> Optional[bool]:
    """True/False, or None when either side has no brand (cannot compare)."""
    if listing_brand is None or not listing_brand.verified or not recall.brand:
        return None
    lb = brand_norm(listing_brand.value)
    if not lb:
        return None
    if lb == brand_norm(recall.brand):
        return True
    for key in recall.quotes:                       # brands named in the official notice
        if key.startswith("brand_alt:") and lb == brand_norm(key[len("brand_alt:"):]):
            return True
    return False


def check_scope(listing: ExtractedListing, recall: RecallRecord) -> str:
    """-> 'all_units' | 'in_range' | 'unverified' | 'outside' (verified listing data only)."""
    if recall.scope_type == "all_units":
        return "all_units"
    if recall.scope_type != "range":
        return "unverified"
    try:
        lo = date.fromisoformat(recall.scope_from) if recall.scope_from else None
        hi = date.fromisoformat(recall.scope_to) if recall.scope_to else None
    except ValueError:
        return "unverified"
    if lo is None and hi is None:
        return "unverified"
    spans: list[tuple[date, date]] = []
    for q in _verified(listing.lot_or_date_info):
        spans += find_dates(q.evidence_quote)
    if not spans:
        return "unverified"
    inside = outside = 0
    for s, e in spans:
        if (lo is None or s >= lo) and (hi is None or e <= hi):
            inside += 1
        elif (lo is not None and e < lo) or (hi is not None and s > hi):
            outside += 1
    if inside == len(spans):
        return "in_range"
    if outside == len(spans):
        return "outside"
    return "unverified"          # mixed or straddling dates: do not guess


# ------------------------------------------------------------------ evidence

def _ev_listing(listing: ExtractedListing, q: Quoted) -> Evidence:
    cap = ci.get_capture(listing.source_url)
    return Evidence(
        id=q.evidence_id or evidence_id(listing.source_url, q.evidence_quote),
        source_url=listing.source_url,
        source_tier=cap.source_tier if cap else "C",
        quote=q.evidence_quote,
        retrieved_at=cap.fetched_at if cap else ci.now(),
        quote_verified=q.verified,
        screenshot_path=cap.screenshot_path if cap else None,
    )


def _ev_recall(recall: RecallRecord, kind: str, key: str, raw_value: str) -> Evidence:
    quote = recall.quotes.get(f"{kind}:{key}")
    method = "notice_extract+quote_check" if quote else "official_api_record"
    quote = quote or raw_value
    return Evidence(
        id=evidence_id(recall.url, f"{kind}:{quote}"),
        source_url=recall.url,
        source_tier=recall.source_tier,
        quote=quote,
        retrieved_at=ci.recall_fetched_at(recall_id_of(recall)),
        quote_verified=True,      # official record data, or a quote already verified by code
        method=method,
    )


def _dedupe(evs: list[Evidence]) -> list[Evidence]:
    seen, out = set(), []
    for e in evs:
        if e.id not in seen:
            seen.add(e.id)
            out.append(e)
    return out


def _scope_evidence(listing: ExtractedListing, recall: RecallRecord, scope: str) -> list[Evidence]:
    evs: list[Evidence] = []
    q = recall.quotes.get("scope") or recall.scope_text
    if q:
        evs.append(Evidence(
            id=evidence_id(recall.url, f"scope:{q}"), source_url=recall.url,
            source_tier=recall.source_tier, quote=q,
            retrieved_at=ci.recall_fetched_at(recall_id_of(recall)), quote_verified=True,
            method="notice_extract+quote_check" if recall.quotes.get("scope") else "official_api_record"))
    if scope in ("in_range", "outside"):
        evs += [_ev_listing(listing, x) for x in _verified(listing.lot_or_date_info)]
    return evs


def _fallback_evidence(listing: ExtractedListing, status_note: str) -> Evidence:
    cap = ci.get_capture(listing.source_url)
    if cap and cap.block_reason:
        quote = cap.block_reason
        ok = quote_ok(quote, cap.text + "\n" + cap.spec_text)
        method = "agent_block_detect"
    else:
        quote = status_note
        ok = False
        method = "page_status"
    return Evidence(
        id=evidence_id(listing.source_url, quote), source_url=listing.source_url,
        source_tier=cap.source_tier if cap else "C", quote=quote,
        retrieved_at=cap.fetched_at if cap else ci.now(), quote_verified=ok, method=method,
        screenshot_path=cap.screenshot_path if cap else None)


# ---------------------------------------------------------------------- rate

def rate(listing: ExtractedListing, recall: RecallRecord) -> MatchResult:
    rid = recall_id_of(recall)

    def result(tier: Tier, reasons: list[str], evs: list[Evidence]) -> MatchResult:
        return MatchResult(listing_id=listing.listing_id, recall_id=rid, tier=tier,
                           reasons=reasons, evidence=_dedupe(evs))

    # ---- could not read the page: never a verdict about the product
    if listing.capture_status != "ok":
        code = "BLOCKED" if listing.capture_status == "blocked" else "EXTRACT_FAIL"
        return result("UNRESOLVED", [code],
                      [_fallback_evidence(listing, f"Capture status: {listing.capture_status}")])

    brand_q = listing.brand if (listing.brand and listing.brand.verified) else None
    name_q = listing.product_name if (listing.product_name and listing.product_name.verified) else None
    models_l = [q for q in _verified(listing.model_numbers) if len(canon(q.value)) >= MIN_MODEL_CANON_LEN]
    gtins_l = [q for q in _verified(listing.gtins) if gtin_ok(q.value)]

    if not (brand_q or name_q or models_l or gtins_l):
        return result("UNRESOLVED", ["EXTRACT_FAIL"],
                      [_fallback_evidence(listing, "No identifying field could be verified on this page")])

    recall_models = {canon(m): m for m in recall.models if len(canon(m)) >= MIN_MODEL_CANON_LEN}
    recall_gtins = {digits(g): g for g in recall.gtins if gtin_ok(g)}
    model_hits = [q for q in models_l if canon(q.value) in recall_models]
    gtin_hits = [q for q in gtins_l if digits(q.value) in recall_gtins]
    brand_ok = _brand_ok(brand_q, recall)

    id_reasons: list[str] = []
    id_evs: list[Evidence] = []
    if model_hits:
        id_reasons.append("ID_MODEL_EXACT")
        for q in model_hits:
            id_evs += [_ev_listing(listing, q),
                       _ev_recall(recall, "model", canon(q.value), recall_models[canon(q.value)])]
    if gtin_hits:
        id_reasons.append("ID_GTIN_EXACT")
        for q in gtin_hits:
            id_evs += [_ev_listing(listing, q),
                       _ev_recall(recall, "gtin", digits(q.value), recall_gtins[digits(q.value)])]
    brand_evs = [_ev_listing(listing, brand_q)] if brand_q else []

    if id_reasons:
        if brand_ok is not True:
            code = "BRAND_DIFF" if brand_ok is False else "QUOTE_UNVERIFIED"
            return result("RELATED", id_reasons + [code], id_evs + brand_evs)
        if recall.source_tier != "A":
            return result("LIKELY", id_reasons + ["BRAND_EQ", "SRC_TIER_NOT_A"], id_evs + brand_evs)
        scope = check_scope(listing, recall)
        evs = id_evs + brand_evs + _scope_evidence(listing, recall, scope)
        base = id_reasons + ["BRAND_EQ"]
        if scope == "outside":
            return result("RELATED", base + ["SCOPE_OUTSIDE"], evs)
        if scope == "all_units":
            return result("CONFIRMED", base + ["SCOPE_ALL_UNITS"], evs)
        if scope == "in_range":
            return result("CONFIRMED", base + ["SCOPE_IN_RANGE"], evs)
        return result("LIKELY", base + ["SCOPE_UNVERIFIED"], evs)

    # ---- no identifier overlap: text similarity may only suggest RELATED
    if brand_ok is True:
        sim = similarity(name_q.value, recall.title) if name_q else 0.0
        for q in models_l:
            for rm in recall_models.values():
                sim = max(sim, model_similarity(q.value, rm))
        if sim >= NAME_SIM_THRESHOLD:
            evs = brand_evs + ([_ev_listing(listing, name_q)] if name_q else []) \
                + [_ev_listing(listing, q) for q in models_l]
            return result("RELATED", ["NAME_ONLY"], evs)

    shown = brand_evs + ([_ev_listing(listing, name_q)] if name_q else []) \
        + [_ev_listing(listing, q) for q in models_l[:1]] + [_ev_listing(listing, q) for q in gtins_l[:1]]
    return result("NO_MATCH", [], shown)


# ----------------------------------------------------- post-processing helpers

def annotate_dropped(result: MatchResult) -> MatchResult:
    """Add QUOTE_UNVERIFIED when extraction dropped unverifiable fields for this listing.

    Annotation only: it appends a reason code and never changes the tier.
    """
    if ci.get_dropped(result.listing_id) and "QUOTE_UNVERIFIED" not in result.reasons:
        return result.model_copy(update={"reasons": result.reasons + ["QUOTE_UNVERIFIED"]})
    return result


def apply_conflicts(result: MatchResult, conflicts: list[dict]) -> MatchResult:
    """If two official records disagree, a CONFIRMED/LIKELY result becomes CONFLICT.

    RELATED / NO_MATCH / UNRESOLVED are left alone. Conflict quotes are attached as evidence.
    """
    if not conflicts or result.tier not in ("CONFIRMED", "LIKELY"):
        return result
    reasons = list(result.reasons)
    evs = list(result.evidence)
    for c in conflicts:
        if c["code"] not in reasons:
            reasons.append(c["code"])
        for side in ("a", "b"):
            s = c[side]
            if s.get("quote"):
                evs.append(Evidence(
                    id=evidence_id(s["url"], f"{c['field']}:{s['quote']}"), source_url=s["url"],
                    source_tier="A", quote=s["quote"], retrieved_at=ci.recall_fetched_at(s["recall_id"]),
                    quote_verified=s.get("quote_verified", False), method="official_record_compare"))
    return MatchResult(listing_id=result.listing_id, recall_id=result.recall_id, tier="CONFLICT",
                       reasons=reasons, evidence=_dedupe(evs))


def best_per_listing(results: Iterable[MatchResult]) -> dict[str, MatchResult]:
    """One result per listing_id (variant ids stay separate): best by TIER_ORDER."""
    best: dict[str, MatchResult] = {}
    for r in results:
        cur = best.get(r.listing_id)
        if cur is None or (_RANK[r.tier], -len(r.evidence)) < (_RANK[cur.tier], -len(cur.evidence)):
            best[r.listing_id] = r
    return best
