"""
Stub match engine — returns fixture data when USE_STUBS=1.
M2 replaces this file.
Signature MUST stay: def rate(listing, recall) -> MatchResult
THE LLM NEVER ASSIGNS TIERS — this code does.
"""
from __future__ import annotations

from contracts.models import (
    Evidence,
    ExtractedListing,
    MatchResult,
    Quoted,
    ReasonCode,
    RecallRecord,
    Tier,
)


def _canon(s: str) -> str:
    """Canonical form for comparison: lowercase, strip spaces/hyphens."""
    return s.lower().replace(" ", "").replace("-", "").replace(".", "")


def _verify_quote(quoted: Quoted | None, page_text: str) -> Quoted | None:
    """Return the Quoted only if the evidence_quote appears in the page text."""
    if quoted is None:
        return None
    if quoted.evidence_quote and quoted.evidence_quote in page_text:
        return Quoted(
            value=quoted.value,
            evidence_quote=quoted.evidence_quote,
            verified=True,
        )
    return None  # Drop unverified fields — they cannot influence the verdict


def rate(listing: ExtractedListing, recall: RecallRecord) -> MatchResult:
    """
    Deterministic rule engine: compare listing fields to recall fields,
    build evidence, assign a tier. The LLM is never involved here.
    """
    reasons: list[ReasonCode] = []
    evidence: list[Evidence] = []
    page_text = listing.page_text or ""

    # --- Verify quotes before using fields ---
    v_model = _verify_quote(listing.model, page_text)
    v_brand = _verify_quote(listing.brand, page_text)
    v_gtin = _verify_quote(listing.gtin, page_text)
    v_lot = _verify_quote(listing.lot_code, page_text)
    v_mfg_date = _verify_quote(listing.manufacture_date, page_text)

    model_match = False
    gtin_match = False
    brand_match = False
    brand_diff = False

    # --- Model comparison ---
    if v_model and recall.models:
        listing_model_canon = _canon(v_model.value)
        for rm in recall.models:
            if _canon(rm) == listing_model_canon:
                model_match = True
                reasons.append(ReasonCode.ID_MODEL_EXACT)
                evidence.append(Evidence(
                    field="model",
                    listing_value=v_model.value,
                    recall_value=rm,
                    comparison="exact_canonical",
                    evidence_quote=v_model.evidence_quote,
                    page_url=listing.source_url,
                ))
                break

    # --- GTIN comparison ---
    if v_gtin and recall.gtins:
        listing_gtin_canon = _canon(v_gtin.value)
        for rg in recall.gtins:
            if _canon(rg) == listing_gtin_canon:
                gtin_match = True
                reasons.append(ReasonCode.ID_GTIN_EXACT)
                evidence.append(Evidence(
                    field="gtin",
                    listing_value=v_gtin.value,
                    recall_value=rg,
                    comparison="exact_canonical",
                    evidence_quote=v_gtin.evidence_quote,
                    page_url=listing.source_url,
                ))
                break

    # --- Brand comparison ---
    if v_brand and recall.brand:
        if _canon(v_brand.value) == _canon(recall.brand):
            brand_match = True
            reasons.append(ReasonCode.BRAND_EQ)
            evidence.append(Evidence(
                field="brand",
                listing_value=v_brand.value,
                recall_value=recall.brand,
                comparison="exact_canonical",
                evidence_quote=v_brand.evidence_quote,
                page_url=listing.source_url,
            ))
        else:
            brand_diff = True
            reasons.append(ReasonCode.BRAND_DIFF)

    # --- Scope evaluation ---
    scope = recall.scope
    scope_ok = False
    scope_unverified = False
    scope_outside = False

    if scope.kind == "all_units":
        scope_ok = True
        reasons.append(ReasonCode.SCOPE_ALL_UNITS)
    elif scope.kind in ("date_range", "lot_range"):
        # Need manufacture_date or lot_code from listing
        if scope.kind == "date_range":
            if v_mfg_date:
                # Stub: simple in-range check would go here in real impl
                scope_ok = True
                reasons.append(ReasonCode.SCOPE_IN_RANGE)
            else:
                scope_unverified = True
                reasons.append(ReasonCode.SCOPE_UNVERIFIED)
        elif scope.kind == "lot_range":
            if v_lot and v_lot.value in scope.lot_codes:
                scope_ok = True
                reasons.append(ReasonCode.SCOPE_IN_RANGE)
            elif v_lot:
                scope_outside = True
                reasons.append(ReasonCode.SCOPE_OUTSIDE)
            else:
                scope_unverified = True
                reasons.append(ReasonCode.SCOPE_UNVERIFIED)
    else:
        scope_unverified = True
        reasons.append(ReasonCode.SCOPE_UNVERIFIED)

    # --- Tier decision ---
    if not evidence:
        # No verified fields matched at all
        if listing.title and listing.title.verified:
            reasons.append(ReasonCode.NAME_ONLY)
            tier = Tier.RELATED
        else:
            tier = Tier.NO_MATCH
    elif model_match and brand_match and (scope_ok or scope.kind == "all_units"):
        tier = Tier.CONFIRMED
    elif model_match and brand_match and scope_unverified:
        tier = Tier.LIKELY
    elif model_match and brand_match and scope_outside:
        tier = Tier.RELATED
        reasons.append(ReasonCode.SCOPE_OUTSIDE)
    elif (model_match or gtin_match) and brand_diff:
        tier = Tier.RELATED
    elif model_match or gtin_match:
        tier = Tier.CONFIRMED if scope_ok else Tier.LIKELY
    else:
        # Brand match only, or partial
        tier = Tier.RELATED

    return MatchResult(
        listing_id=listing.listing_id,
        recall_number=recall.recall_number,
        tier=tier,
        reasons=reasons,
        evidence=evidence,
        explanation=f"Stub match engine: tier={tier.value}, reasons={[r.value for r in reasons]}",
    )
