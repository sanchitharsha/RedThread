"""
Test: no MATCHES edge without evidence.
Enforces the graph invariant from the spec.
"""
import json
import pytest

from contracts.models import GraphJSON, Tier, ReasonCode
from backend.graph import GraphBuilder, build_graph_from_results
from contracts.models import (
    RecallRecord,
    RecallScope,
    ExtractedListing,
    MatchResult,
    Evidence,
    Quoted,
)


class TestGraphEvidenceInvariant:
    """Every MATCHES edge MUST have at least one evidence_id."""

    def test_matches_edge_requires_evidence(self):
        """Creating a MATCHES edge without evidence_ids should raise."""
        builder = GraphBuilder()
        recall_nid = builder.add_recall(RecallRecord(
            recall_number="PLACEHOLDER-000",
            brand="PLACEHOLDER-BRAND",
        ))
        listing_nid = builder.add_listing(ExtractedListing(
            source_url="http://localhost:8001/product/X",
            page_text="test",
        ))

        with pytest.raises(ValueError, match="without evidence"):
            builder.add_matches(
                listing_nid, recall_nid,
                Tier.CONFIRMED, [ReasonCode.ID_MODEL_EXACT],
                evidence_ids=[],  # Empty!
            )

    def test_matches_edge_with_evidence_ok(self):
        """Creating a MATCHES edge with evidence should succeed."""
        builder = GraphBuilder()
        recall_nid = builder.add_recall(RecallRecord(
            recall_number="PLACEHOLDER-000",
            brand="PLACEHOLDER-BRAND",
        ))
        listing_nid = builder.add_listing(ExtractedListing(
            source_url="http://localhost:8001/product/X",
            page_text="test",
        ))

        eid = builder.add_matches(
            listing_nid, recall_nid,
            Tier.CONFIRMED, [ReasonCode.ID_MODEL_EXACT],
            evidence_ids=["ev-test-001"],
        )
        assert eid

    def test_fixture_graph_all_matches_have_evidence(self):
        """The fixture graph must satisfy the invariant."""
        with open("fixtures/graph_fixture.json") as f:
            graph = GraphJSON(**json.load(f))

        for edge in graph.edges:
            if edge.kind == "MATCHES":
                assert len(edge.evidence_ids) >= 1, (
                    f"MATCHES edge {edge.id} has no evidence_ids"
                )

    def test_build_graph_from_results(self):
        """build_graph_from_results should produce valid MATCHES edges."""
        recall = RecallRecord(
            recall_number="PLACEHOLDER-000",
            brand="PLACEHOLDER-BRAND",
            models=["MODEL-AAA"],
            gtins=["0000000000000"],
            scope=RecallScope(kind="all_units"),
        )

        listing = ExtractedListing(
            source_url="http://localhost:8001/product/L01",
            brand=Quoted(value="PLACEHOLDER-BRAND", evidence_quote="Brand: PLACEHOLDER-BRAND", verified=True),
            model=Quoted(value="MODEL-AAA", evidence_quote="Model: MODEL-AAA", verified=True),
            page_text="Brand: PLACEHOLDER-BRAND. Model: MODEL-AAA.",
        )

        evidence = Evidence(
            evidence_id="ev-test-model",
            field="model",
            listing_value="MODEL-AAA",
            recall_value="MODEL-AAA",
            comparison="exact",
        )

        result = MatchResult(
            listing_id=listing.listing_id,
            recall_number="PLACEHOLDER-000",
            tier=Tier.CONFIRMED,
            reasons=[ReasonCode.ID_MODEL_EXACT],
            evidence=[evidence],
        )

        graph = build_graph_from_results(recall, [listing], [result])

        # Check all MATCHES edges have evidence
        matches_edges = [e for e in graph.edges if e.kind == "MATCHES"]
        assert len(matches_edges) >= 1
        for edge in matches_edges:
            assert len(edge.evidence_ids) >= 1
