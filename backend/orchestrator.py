"""
Pipeline orchestrator.
Owned by M3.

Runs the investigation: fetch recall → harvest notice → enrich →
discover & inspect → extract → rate → graph → report.

async def run_investigation(run_id, recall_ref, shop_url, emit) -> None
"""
from __future__ import annotations

import asyncio
import logging
import os
import traceback
from datetime import datetime

from contracts.models import (
    Emit,
    Event,
    EventType,
    ExtractedListing,
    InvestigationTask,
    MatchResult,
    PageCapture,
    ReasonCode,
    RecallRecord,
    TaskKind,
    Tier,
)
from backend import store
from backend.graph import GraphBuilder, GraphJSON
from backend.report import build_report

logger = logging.getLogger(__name__)


def _use_stubs() -> bool:
    return os.environ.get("USE_STUBS", "0") == "1"


def _get_modules():
    """Import agent/matching modules, using stubs when USE_STUBS=1."""
    if _use_stubs():
        from agent import agent as agent_mod
        from matching.connectors import cpsc as cpsc_mod
        from matching import extract as extract_mod
        from matching import match as match_mod
        from matching.llm import get_llm
    else:
        # In production, these would be the real modules from M1/M2
        # They share the same package paths; M1/M2 just replace the files
        from agent import agent as agent_mod
        from matching.connectors import cpsc as cpsc_mod
        from matching import extract as extract_mod
        from matching import match as match_mod
        from matching.llm import get_llm
    return agent_mod, cpsc_mod, extract_mod, match_mod, get_llm


async def run_investigation(
    run_id: str,
    recall_ref: str,
    shop_url: str,
    emit: Emit,
) -> None:
    """
    Main pipeline entry point.

    Steps:
    a) Fetch recall from CPSC → emit official_record
    b) Harvest notice page → enrich recall → emit official_record (enriched)
    c) Discover & inspect shop → collect PageCaptures
    d) For each capture: extract listings → rate each → emit results
    e) Build graph → emit graph_delta
    f) Build report → emit run_finished
    """
    agent_mod, cpsc_mod, extract_mod, match_mod, get_llm = _get_modules()
    llm = get_llm()
    seq = 0

    async def _emit(event_type: str, payload: dict) -> None:
        nonlocal seq
        seq += 1
        event = Event(
            run_id=run_id,
            seq=seq,
            type=event_type,
            timestamp=datetime.utcnow(),
            payload=payload,
        )
        store.append_event(run_id, event)
        await emit(event_type, payload)

    allow_domains = [
        d.strip()
        for d in os.environ.get("ALLOW_DOMAINS", "localhost").split(",")
        if d.strip()
    ]

    all_listings: list[ExtractedListing] = []
    all_results: list[MatchResult] = []
    all_captures: list[PageCapture] = []

    try:
        # ---- (a) Fetch recall ----
        await _emit(EventType.RUN_STARTED.value, {
            "recall_ref": recall_ref,
            "shop_url": shop_url,
            "mode": "live",
        })

        await _emit(EventType.STEP_STARTED.value, {
            "step": "fetch_recall",
            "recall_ref": recall_ref,
        })

        recall = cpsc_mod.fetch_recall(recall_ref)

        await _emit(EventType.OFFICIAL_RECORD.value, {
            "recall_number": recall.recall_number,
            "authority": recall.authority,
            "brand": recall.brand,
            "models": recall.models,
            "title": recall.title,
            "scope": recall.scope.model_dump(mode="json"),
        })

        store.save_meta(run_id, {
            "recall_ref": recall_ref,
            "shop_url": shop_url,
            "recall_number": recall.recall_number,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        })

        # ---- (b) Harvest notice page → enrich ----
        if recall.url:
            await _emit(EventType.STEP_STARTED.value, {
                "step": "harvest_notice",
                "url": recall.url,
            })

            harvest_task = InvestigationTask(
                kind=TaskKind.HARVEST_NOTICE,
                target_url=recall.url,
                recall=recall,
                allow_domains=allow_domains + ["www.cpsc.gov", "cpsc.gov"],
                max_pages=3,
            )

            notice_captures = await agent_mod.investigate(harvest_task, _emit, llm)

            if notice_captures:
                recall = await extract_mod.enrich_recall(
                    recall, notice_captures[0], llm
                )
                await _emit(EventType.OFFICIAL_RECORD.value, {
                    "recall_number": recall.recall_number,
                    "authority": recall.authority,
                    "brand": recall.brand,
                    "models": recall.models,
                    "title": recall.title,
                    "hazard": recall.hazard,
                    "remedy": recall.remedy,
                    "scope": recall.scope.model_dump(mode="json"),
                    "enriched": True,
                })
                all_captures.extend(notice_captures)

        # ---- (c) Discover & inspect shop ----
        await _emit(EventType.STEP_STARTED.value, {
            "step": "discover_and_inspect",
            "url": shop_url,
        })

        search_terms = []
        if recall.brand:
            search_terms.append(recall.brand)
        search_terms.extend(recall.models)
        if recall.product_name:
            search_terms.append(recall.product_name)

        shop_task = InvestigationTask(
            kind=TaskKind.DISCOVER_AND_INSPECT,
            target_url=shop_url,
            recall=recall,
            search_terms=search_terms,
            allow_domains=allow_domains,
            max_pages=20,
        )

        shop_captures = await agent_mod.investigate(shop_task, _emit, llm)
        all_captures.extend(shop_captures)

        # ---- (d) Extract & rate ----
        graph_builder = GraphBuilder()
        recall_nid = graph_builder.add_recall(recall)

        # Add recall's product models to graph
        for model in recall.models:
            pm_nid = graph_builder.add_product_model(recall.brand, model)
            graph_builder.add_covers(
                recall_nid, pm_nid,
                [f"ev-recall-covers-{model.lower().replace(' ', '')}"],
            )

        prev_graph = graph_builder.build()

        for capture in shop_captures:
            if capture.blocked:
                # Blocked capture → UNRESOLVED
                unresolved_result = MatchResult(
                    listing_id=f"blocked-{capture.url}",
                    recall_number=recall.recall_number,
                    tier=Tier.UNRESOLVED,
                    reasons=[ReasonCode.BLOCKED],
                    evidence=[],
                    explanation=f"Page blocked: {capture.error or 'bot check'}",
                )
                all_results.append(unresolved_result)
                await _emit(EventType.MATCH_RESULT.value, {
                    "listing_id": unresolved_result.listing_id,
                    "recall_number": recall.recall_number,
                    "tier": Tier.UNRESOLVED.value,
                    "reasons": [ReasonCode.BLOCKED.value],
                })
                continue

            try:
                listings = await extract_mod.extract_listings(capture, llm)
            except Exception as exc:
                logger.error("Extract failed for %s: %s", capture.url, exc)
                fail_result = MatchResult(
                    listing_id=f"extract-fail-{capture.url}",
                    recall_number=recall.recall_number,
                    tier=Tier.UNRESOLVED,
                    reasons=[ReasonCode.EXTRACT_FAIL],
                    evidence=[],
                    explanation=f"Extraction failed: {exc}",
                )
                all_results.append(fail_result)
                await _emit(EventType.RUN_ERROR.value, {
                    "error": f"Extract failed for {capture.url}: {exc}",
                    "listing_id": fail_result.listing_id,
                })
                continue

            for listing in listings:
                all_listings.append(listing)

                await _emit(EventType.EXTRACTION.value, {
                    "listing_id": listing.listing_id,
                    "source_url": listing.source_url,
                    "brand": listing.brand.value if listing.brand else None,
                    "model": listing.model.value if listing.model else None,
                    "gtin": listing.gtin.value if listing.gtin else None,
                })

                try:
                    result = match_mod.rate(listing, recall)
                except Exception as exc:
                    logger.error("Rate failed for %s: %s", listing.listing_id, exc)
                    result = MatchResult(
                        listing_id=listing.listing_id,
                        recall_number=recall.recall_number,
                        tier=Tier.UNRESOLVED,
                        reasons=[ReasonCode.EXTRACT_FAIL],
                        evidence=[],
                        explanation=f"Rating failed: {exc}",
                    )

                all_results.append(result)

                # Save evidence
                for ev in result.evidence:
                    store.save_evidence(run_id, ev)

                tier_val = result.tier.value if hasattr(result.tier, "value") else str(result.tier)
                reasons_val = [r.value if hasattr(r, "value") else str(r) for r in result.reasons]
                await _emit(EventType.MATCH_RESULT.value, {
                    "listing_id": result.listing_id,
                    "recall_number": result.recall_number or getattr(result, "recall_id", ""),
                    "tier": tier_val,
                    "reasons": reasons_val,
                })

                # Update graph
                listing_nid = graph_builder.add_listing(listing)
                evidence_ids = [ev.id or ev.evidence_id for ev in result.evidence]
                if evidence_ids:
                    graph_builder.add_matches(
                        listing_nid, recall_nid, result.tier, result.reasons, evidence_ids
                    )

                # Emit graph delta
                current_graph = graph_builder.build()
                delta = graph_builder.get_delta(prev_graph)
                if delta["nodes_added"] or delta["edges_added"]:
                    await _emit(EventType.GRAPH_DELTA.value, delta)
                prev_graph = current_graph

        # ---- (e) Save final artefacts ----
        final_graph = graph_builder.build()
        store.save_graph(run_id, final_graph)
        store.save_captures(run_id, all_captures)
        store.save_results(run_id, all_results)

        # ---- (f) Build report ----
        report = build_report(
            run_id, recall, all_listings, all_results, mode="live"
        )
        store.save_report(run_id, report)

        # ---- Done ----
        await _emit(EventType.RUN_FINISHED.value, {
            "run_id": run_id,
            "total_listings": len(all_listings),
            "tier_counts": report.tier_counts,
            "duration_s": 0,  # TODO: compute from timestamps
        })

        store.save_meta(run_id, {
            "recall_ref": recall_ref,
            "shop_url": shop_url,
            "recall_number": recall.recall_number,
            "status": "finished",
            "started_at": datetime.utcnow().isoformat(),
        })

    except Exception as exc:
        logger.exception("Run %s failed: %s", run_id, exc)
        try:
            await _emit(EventType.RUN_ERROR.value, {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
        except Exception:
            pass
        store.save_meta(run_id, {
            "recall_ref": recall_ref,
            "shop_url": shop_url,
            "status": "error",
            "error": str(exc),
        })
        raise
