"""
Report builder — creates ReportJSON from match results and graph.
Owned by M3.
"""
from __future__ import annotations

from datetime import datetime

from contracts.models import (
    MatchResult,
    RecallRecord,
    ReportJSON,
    ReportListingRow,
    SourceChecked,
    Tier,
    ExtractedListing,
)


def build_report(
    run_id: str,
    recall: RecallRecord,
    listings: list[ExtractedListing],
    results: list[MatchResult],
    *,
    mode: str = "live",
    sources_checked: list[SourceChecked] | None = None,
) -> ReportJSON:
    """Build the exposure report from final data."""

    # Tier counts — all tiers must appear even if zero
    tier_counts: dict[str, int] = {t.value: 0 for t in Tier}
    for r in results:
        t_val = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        tier_counts[t_val] = tier_counts.get(t_val, 0) + 1

    # Build listing rows — best tier per listing
    listing_map = {lst.listing_id: lst for lst in listings}
    # Group results by listing_id, pick best tier
    best_per_listing: dict[str, MatchResult] = {}
    for r in results:
        existing = best_per_listing.get(r.listing_id)
        if existing is None or _tier_rank(r.tier) < _tier_rank(existing.tier):
            best_per_listing[r.listing_id] = r

    rows: list[ReportListingRow] = []
    for listing_id, result in best_per_listing.items():
        lst = listing_map.get(listing_id)
        model_str = ""
        if lst:
            if lst.model:
                model_str = lst.model.value
            elif lst.model_numbers:
                model_str = lst.model_numbers[0].value
        rows.append(ReportListingRow(
            listing_id=listing_id,
            url=lst.source_url if lst else "",
            title=(lst.title.value if lst.title else (lst.product_name.value if lst.product_name else "")) if lst else "",
            brand=lst.brand.value if lst and lst.brand else "",
            model=model_str,
            best_tier=result.tier,
            reasons=result.reasons,
            evidence_ids=[ev.id or ev.evidence_id for ev in result.evidence],
        ))

    # Conflicts: results with CONFLICT tier or conflict reason codes
    conflicts = []
    for r in results:
        t_val = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        if t_val == "CONFLICT":
            conflicts.append({
                "listing_id": r.listing_id,
                "tier": t_val,
                "reasons": [rc.value if hasattr(rc, "value") else str(rc) for rc in r.reasons],
                "explanation": r.explanation,
            })

    # Unresolved
    unresolved = []
    for r in results:
        t_val = r.tier.value if hasattr(r.tier, "value") else str(r.tier)
        if t_val == "UNRESOLVED":
            unresolved.append({
                "listing_id": r.listing_id,
                "reasons": [rc.value if hasattr(rc, "value") else str(rc) for rc in r.reasons],
                "explanation": r.explanation,
            })

    # Coverage
    coverage = sources_checked or []
    # Always include "not checked" for other authorities and shops
    if not any(s.source == "CPSC" for s in coverage):
        coverage.append(SourceChecked(
            source="CPSC",
            url=recall.url,
            checked_at=datetime.utcnow(),
            status="checked",
        ))
    # Note sources NOT checked
    for label in ["Health Canada", "EU RAPEX", "Other shops"]:
        if not any(s.source == label for s in coverage):
            coverage.append(SourceChecked(source=label, status="not_checked"))

    return ReportJSON(
        run_id=run_id,
        recall_number=recall.recall_number,
        recall_title=recall.title,
        mode=mode,  # type: ignore[arg-type]
        tier_counts=tier_counts,
        listings=rows,
        conflicts=conflicts,
        unresolved=unresolved,
        coverage=coverage,
    )


def _tier_rank(tier: Tier | str) -> int:
    """Lower is 'stronger' / more specific."""
    val = tier.value if hasattr(tier, "value") else str(tier)
    _ORDER = {
        "CONFIRMED": 0,
        "LIKELY": 1,
        "RELATED": 2,
        "CONFLICT": 3,
        "NO_MATCH": 4,
        "UNRESOLVED": 5,
    }
    return _ORDER.get(val, 99)
