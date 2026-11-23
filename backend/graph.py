"""
Evidence graph builder.
Owned by M3.

Invariant: a MATCHES edge CANNOT be created without at least one Evidence.
"""
from __future__ import annotations

from contracts.models import (
    EdgeKind,
    Evidence,
    GraphEdge,
    GraphJSON,
    GraphNode,
    MatchResult,
    NodeKind,
    RecallRecord,
    ExtractedListing,
    Tier,
)


def _canon(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace(".", "")


class GraphBuilder:
    """Incrementally builds a GraphJSON, deduplicating nodes by key."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}

    # ---- Node factories ----

    def _node_id(self, kind: str, *keys: str) -> str:
        return f"{kind.lower()}-" + "-".join(_canon(k) for k in keys if k)

    def add_recall(self, recall: RecallRecord) -> str:
        nid = self._node_id("recall", recall.authority, recall.recall_number)
        if nid not in self._nodes:
            self._nodes[nid] = GraphNode(
                id=nid,
                kind=NodeKind.RECALL.value,
                label=f"{recall.authority} {recall.recall_number}",
                properties={
                    "title": recall.title,
                    "brand": recall.brand,
                    "scope": recall.scope.kind,
                },
            )
        return nid

    def add_product_model(self, brand: str, model: str) -> str:
        nid = self._node_id("pm", brand, model)
        if nid not in self._nodes:
            self._nodes[nid] = GraphNode(
                id=nid,
                kind=NodeKind.PRODUCT_MODEL.value,
                label=f"{brand} {model}",
                properties={"brand": brand, "model": model},
            )
        return nid

    def add_identifier(self, id_type: str, value: str) -> str:
        nid = self._node_id("id", id_type, value)
        if nid not in self._nodes:
            self._nodes[nid] = GraphNode(
                id=nid,
                kind=NodeKind.IDENTIFIER.value,
                label=f"{id_type} {value}",
                properties={"type": id_type, "value": value},
            )
        return nid

    def add_listing(self, listing: ExtractedListing) -> str:
        url = listing.source_url or listing.listing_id
        variant = listing.variant_label or ""
        nid = self._node_id("listing", url, variant)
        if nid not in self._nodes:
            title = listing.title.value if listing.title else listing.listing_id
            self._nodes[nid] = GraphNode(
                id=nid,
                kind=NodeKind.LISTING.value,
                label=title,
                properties={
                    "url": listing.source_url,
                    "variant": variant,
                    "listing_id": listing.listing_id,
                },
            )
        return nid

    def add_seller(self, name: str, domain: str = "") -> str:
        nid = self._node_id("seller", name)
        if nid not in self._nodes:
            self._nodes[nid] = GraphNode(
                id=nid,
                kind=NodeKind.SELLER.value,
                label=name,
                properties={"domain": domain},
            )
        return nid

    # ---- Edge factories ----

    def _edge_id(self, source: str, target: str, kind: str) -> str:
        return f"{kind.lower()}-{source}-{target}"

    def _add_edge(
        self,
        source: str,
        target: str,
        kind: EdgeKind,
        evidence_ids: list[str],
        properties: dict | None = None,
    ) -> str:
        eid = self._edge_id(source, target, kind.value)
        if eid not in self._edges:
            # Invariant: MATCHES edges MUST have evidence
            if kind == EdgeKind.MATCHES and not evidence_ids:
                raise ValueError(
                    f"Cannot create MATCHES edge {eid} without evidence"
                )
            self._edges[eid] = GraphEdge(
                id=eid,
                source=source,
                target=target,
                kind=kind.value,
                properties=properties or {},
                evidence_ids=evidence_ids,
            )
        return eid

    def add_covers(self, recall_nid: str, pm_nid: str, evidence_ids: list[str]) -> str:
        return self._add_edge(recall_nid, pm_nid, EdgeKind.COVERS, evidence_ids)

    def add_has_identifier(self, pm_nid: str, id_nid: str, evidence_ids: list[str]) -> str:
        return self._add_edge(pm_nid, id_nid, EdgeKind.HAS_IDENTIFIER, evidence_ids)

    def add_lists(self, listing_nid: str, pm_nid: str, evidence_ids: list[str]) -> str:
        return self._add_edge(listing_nid, pm_nid, EdgeKind.LISTS, evidence_ids)

    def add_sold_by(self, listing_nid: str, seller_nid: str, evidence_ids: list[str]) -> str:
        return self._add_edge(listing_nid, seller_nid, EdgeKind.SOLD_BY, evidence_ids)

    def add_matches(
        self,
        listing_nid: str,
        recall_nid: str,
        tier: Tier | str,
        reasons: list,
        evidence_ids: list[str],
    ) -> str:
        """Add a MATCHES edge. Raises ValueError if evidence_ids is empty."""
        tier_val = tier.value if hasattr(tier, "value") else str(tier)
        return self._add_edge(
            listing_nid,
            recall_nid,
            EdgeKind.MATCHES,
            evidence_ids,
            properties={
                "tier": tier_val,
                "reasons": [r.value if hasattr(r, "value") else str(r) for r in reasons],
            },
        )

    def add_related_to(self, source_nid: str, target_nid: str, evidence_ids: list[str], relationship: str = "") -> str:
        return self._add_edge(
            source_nid,
            target_nid,
            EdgeKind.RELATED_TO,
            evidence_ids,
            properties={"relationship": relationship},
        )

    # ---- Build ----

    def build(self) -> GraphJSON:
        return GraphJSON(
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )

    def get_delta(self, previous: GraphJSON) -> dict:
        """Return nodes/edges added since previous snapshot."""
        prev_node_ids = {n.id for n in previous.nodes}
        prev_edge_ids = {e.id for e in previous.edges}
        return {
            "nodes_added": [
                n.model_dump(mode="json")
                for n in self._nodes.values()
                if n.id not in prev_node_ids
            ],
            "edges_added": [
                e.model_dump(mode="json")
                for e in self._edges.values()
                if e.id not in prev_edge_ids
            ],
        }


def build_graph_from_results(
    recall: RecallRecord,
    listings: list[ExtractedListing],
    results: list[MatchResult],
) -> GraphJSON:
    """
    One-shot graph build from final data.
    Used when we want the complete graph at once (e.g., report generation).
    """
    builder = GraphBuilder()
    recall_nid = builder.add_recall(recall)

    # Recall covers its models
    for model in recall.models:
        pm_nid = builder.add_product_model(recall.brand, model)
        builder.add_covers(recall_nid, pm_nid, [f"ev-recall-covers-{_canon(model)}"])

        # GTINs
        for gtin in recall.gtins:
            id_nid = builder.add_identifier("GTIN", gtin)
            builder.add_has_identifier(pm_nid, id_nid, [f"ev-pm-{_canon(model)}-gtin-{_canon(gtin)}"])

    # Map listing_id -> listing
    listing_map = {lst.listing_id: lst for lst in listings}

    for result in results:
        lst = listing_map.get(result.listing_id)
        if not lst:
            continue

        listing_nid = builder.add_listing(lst)

        # Seller
        if lst.seller and lst.seller.verified:
            seller_nid = builder.add_seller(lst.seller.value)
            builder.add_sold_by(listing_nid, seller_nid, [f"ev-{lst.listing_id}-seller"])

        # Product model from listing
        if lst.model and lst.model.verified and lst.brand and lst.brand.verified:
            pm_nid = builder.add_product_model(lst.brand.value, lst.model.value)
            builder.add_lists(listing_nid, pm_nid, [f"ev-{lst.listing_id}-lists"])

        # MATCHES edge — requires evidence
        evidence_ids = [ev.evidence_id for ev in result.evidence]
        if evidence_ids:
            builder.add_matches(
                listing_nid, recall_nid, result.tier, result.reasons, evidence_ids
            )

    return builder.build()
