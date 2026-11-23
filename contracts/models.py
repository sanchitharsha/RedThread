"""
Redthread shared contracts.
All team members import from here. M3 owns this file.
Supports both initial skeleton schemas and M1/M2/M4 implementations.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, Optional, Protocol, Union

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Tier(str, Enum):
    """Verdict tiers — there is NO 'safe' tier."""
    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    RELATED = "RELATED"
    CONFLICT = "CONFLICT"
    NO_MATCH = "NO_MATCH"
    UNRESOLVED = "UNRESOLVED"


class ReasonCode(str, Enum):
    """Reason codes attached to every verdict."""
    ID_MODEL_EXACT = "ID_MODEL_EXACT"
    ID_GTIN_EXACT = "ID_GTIN_EXACT"
    BRAND_EQ = "BRAND_EQ"
    BRAND_DIFF = "BRAND_DIFF"
    SCOPE_ALL_UNITS = "SCOPE_ALL_UNITS"
    SCOPE_IN_RANGE = "SCOPE_IN_RANGE"
    SCOPE_UNVERIFIED = "SCOPE_UNVERIFIED"
    SCOPE_OUTSIDE = "SCOPE_OUTSIDE"
    NAME_ONLY = "NAME_ONLY"
    SRC_TIER_NOT_A = "SRC_TIER_NOT_A"
    QUOTE_UNVERIFIED = "QUOTE_UNVERIFIED"
    CONFLICT_MODELS = "CONFLICT_MODELS"
    CONFLICT_SCOPE = "CONFLICT_SCOPE"
    CONFLICT_HAZARD = "CONFLICT_HAZARD"
    CONFLICT_REMEDY = "CONFLICT_REMEDY"
    CONFLICT_STATUS = "CONFLICT_STATUS"
    BLOCKED = "BLOCKED"
    EXTRACT_FAIL = "EXTRACT_FAIL"


class EventType(str, Enum):
    """Every event emitted by the pipeline."""
    RUN_STARTED = "run_started"
    STEP_STARTED = "step_started"
    TOOL_CALL = "tool_call"
    PAGE_VISITED = "page_visited"
    OFFICIAL_RECORD = "official_record"
    EXTRACTION = "extraction"
    MATCH_RESULT = "match_result"
    CONFLICT = "conflict"
    GRAPH_DELTA = "graph_delta"
    RUN_FINISHED = "run_finished"
    RUN_ERROR = "run_error"


class TaskKind(str, Enum):
    """The kind of investigation sub-task."""
    HARVEST_NOTICE = "harvest_notice"
    DISCOVER_AND_INSPECT = "discover_and_inspect"


class SourceTier(str, Enum):
    """Trustworthiness of a data source."""
    A = "A"   # Official authority (CPSC, etc.)
    B = "B"   # Manufacturer / brand
    C = "C"   # Retailer / marketplace
    D = "D"   # News / blog


class IdentifierType(str, Enum):
    """Types of product identifiers."""
    MODEL = "MODEL"
    GTIN = "GTIN"
    UPC = "UPC"
    LOT = "LOT"
    SERIAL = "SERIAL"


class NodeKind(str, Enum):
    """Node types in the evidence graph."""
    RECALL = "Recall"
    PRODUCT_MODEL = "ProductModel"
    IDENTIFIER = "Identifier"
    LISTING = "Listing"
    SELLER = "Seller"


class EdgeKind(str, Enum):
    """Edge types in the evidence graph."""
    COVERS = "COVERS"
    HAS_IDENTIFIER = "HAS_IDENTIFIER"
    LISTS = "LISTS"
    SOLD_BY = "SOLD_BY"
    MATCHES = "MATCHES"
    RELATED_TO = "RELATED_TO"


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

Emit = Callable[[str, dict], Awaitable[None]]
"""emit(event_type, payload) — called by pipeline steps to push events."""


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class Quoted(BaseModel):
    """A value with a verbatim evidence quote from the page."""
    value: str
    evidence_quote: str
    verified: bool = False  # True after code confirms quote appears in page text
    evidence_id: Optional[str] = None


class RecallScope(BaseModel):
    """Describes the scope of a recall (all units, date range, lot range, etc.)."""
    kind: Literal["all_units", "date_range", "lot_range", "serial_range", "unknown", "range"] = "unknown"
    date_start: date | None = None
    date_end: date | None = None
    lot_codes: list[str] = Field(default_factory=list)
    description: Optional[str] = ""


class RecallRecord(BaseModel):
    """An official recall record from an authority (e.g., CPSC)."""
    authority: str = "CPSC"
    number: str = ""
    recall_number: str = ""
    title: str = ""
    description: Optional[str] = None
    url: str = ""

    brand: Optional[str] = ""
    product_name: Optional[str] = ""
    models: list[str] = Field(default_factory=list)
    gtins: list[str] = Field(default_factory=list)
    hazard: Optional[str] = ""
    remedy: Optional[str] = ""
    units_affected: Optional[str] = ""
    scope: RecallScope = Field(default_factory=RecallScope)

    # Extended CPSC API fields used by M2
    date: Optional[str] = None
    source_updated: Optional[str] = None
    retailers: list[str] = Field(default_factory=list)
    scope_type: str = "unknown"  # "all_units" | "range" | "unknown"
    scope_from: Optional[str] = None
    scope_to: Optional[str] = None
    scope_text: Optional[str] = ""
    raw_ref: str = ""
    quotes: dict[str, str] = Field(default_factory=dict)
    status: Optional[str] = None
    fetched_at: Optional[datetime] = None

    manufacture_dates: str = ""
    sold_at: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)

    source_tier: Union[SourceTier, str] = SourceTier.A
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            num = data.get("number") or data.get("recall_number") or ""
            data.setdefault("number", num)
            data.setdefault("recall_number", num)
            # Sync scope
            stype = data.get("scope_type")
            if stype and not data.get("scope"):
                data["scope"] = RecallScope(
                    kind="all_units" if stype == "all_units" else ("date_range" if stype == "range" else "unknown"),
                    description=data.get("scope_text") or ""
                )
            elif data.get("scope") and isinstance(data["scope"], RecallScope) and not data.get("scope_type"):
                data["scope_type"] = "all_units" if data["scope"].kind == "all_units" else ("range" if "range" in data["scope"].kind else "unknown")
        return data


class PageCapture(BaseModel):
    """A captured web page: URL, text content, screenshot path, etc."""
    url: str
    final_url: str = ""
    title: str = ""
    text: str = ""
    spec_text: str = ""
    html_snippet: str = ""
    screenshot_path: Optional[str] = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_tier: Union[SourceTier, str] = "C"
    blocked: bool = False
    status: Literal["ok", "blocked", "error"] = "ok"
    block_reason: Optional[str] = None
    http_status: Optional[int] = None
    links: list[str] = Field(default_factory=list)
    error: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sync_capture(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "status" in data and "blocked" not in data:
                data["blocked"] = (data["status"] == "blocked")
            elif "blocked" in data and "status" not in data:
                data["status"] = "blocked" if data["blocked"] else "ok"
            if "fetched_at" in data and "captured_at" not in data:
                data["captured_at"] = data["fetched_at"]
            elif "captured_at" in data and "fetched_at" not in data:
                data["fetched_at"] = data["captured_at"]
        return data


class InvestigationTask(BaseModel):
    """A task for the browser agent."""
    run_id: str = "local"
    kind: Union[TaskKind, str] = TaskKind.DISCOVER_AND_INSPECT
    playbook: Literal["harvest_notice", "discover_and_inspect"] = "discover_and_inspect"
    target_url: str = ""
    start_url: str = ""
    start_urls: list[str] = Field(default_factory=list)
    recall: RecallRecord | None = None
    goal: str = ""
    search_terms: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    brand: Optional[str] = None
    models: list[str] = Field(default_factory=list)
    product_name: Optional[str] = None
    allow_domains: list[str] = Field(default_factory=list)
    source_tier: Optional[str] = None
    max_steps: int = 25
    max_pages: int = 20
    timeout_seconds: int = 180

    @model_validator(mode="before")
    @classmethod
    def _sync_task(cls, data: Any) -> Any:
        if isinstance(data, dict):
            url = data.get("start_url") or data.get("target_url") or ""
            data.setdefault("start_url", url)
            data.setdefault("target_url", url)

            kind = data.get("kind") or data.get("playbook") or "discover_and_inspect"
            if hasattr(kind, "value"):
                kind = kind.value
            data["kind"] = kind
            data["playbook"] = kind

            terms = data.get("query_terms") or data.get("search_terms") or []
            data.setdefault("query_terms", terms)
            data.setdefault("search_terms", terms)
        return data


class ExtractedListing(BaseModel):
    """A product listing extracted from a page by the LLM."""
    listing_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_url: str = ""
    variant_label: str = ""
    capture_status: str = "ok"
    notes: Optional[str] = ""

    title: Quoted | None = None
    product_name: Quoted | None = None
    brand: Quoted | None = None
    model: Quoted | None = None
    gtin: Quoted | None = None
    lot_code: Quoted | None = None
    manufacture_date: Quoted | None = None
    price: Quoted | None = None
    seller: Quoted | None = None
    description: Quoted | None = None

    model_numbers: list[Quoted] = Field(default_factory=list)
    gtins: list[Quoted] = Field(default_factory=list)
    lot_or_date_info: list[Quoted] = Field(default_factory=list)
    variants: list[Quoted] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)

    identifiers: dict[str, Quoted] = Field(default_factory=dict)
    page_text: str = ""  # full page text for quote verification

    @model_validator(mode="before")
    @classmethod
    def _sync_listing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync title and product_name
            t = data.get("title") or data.get("product_name")
            if t:
                data.setdefault("title", t)
                data.setdefault("product_name", t)
            # Sync model and model_numbers
            if data.get("model") and not data.get("model_numbers"):
                data["model_numbers"] = [data["model"]]
            elif data.get("model_numbers") and not data.get("model"):
                data["model"] = data["model_numbers"][0]
            # Sync gtin and gtins
            if data.get("gtin") and not data.get("gtins"):
                data["gtins"] = [data["gtin"]]
            elif data.get("gtins") and not data.get("gtin"):
                data["gtin"] = data["gtins"][0]
        return data


class Evidence(BaseModel):
    """A piece of evidence supporting a match edge."""
    id: str = ""
    evidence_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    field: str = ""  # which field matched (e.g., "model", "gtin", "brand")
    listing_value: str = ""
    recall_value: str = ""
    comparison: str = ""  # how they were compared (e.g., "exact", "canonical", "fuzzy")
    evidence_quote: str = ""
    quote: str = ""
    quote_verified: bool = True
    page_url: str = ""
    source_url: str = ""
    source_tier: Union[SourceTier, str] = "C"
    screenshot_path: Optional[str] = None
    method: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sync_evidence(cls, data: Any) -> Any:
        if isinstance(data, dict):
            eid = data.get("id") or data.get("evidence_id") or uuid.uuid4().hex[:12]
            data.setdefault("id", eid)
            data.setdefault("evidence_id", eid)

            q = data.get("quote") or data.get("evidence_quote") or ""
            data.setdefault("quote", q)
            data.setdefault("evidence_quote", q)

            u = data.get("source_url") or data.get("page_url") or ""
            data.setdefault("source_url", u)
            data.setdefault("page_url", u)
        return data


class MatchResult(BaseModel):
    """The verdict for one listing vs. one recall."""
    listing_id: str
    recall_id: str = ""
    recall_number: str = ""
    tier: Union[Tier, str]
    reasons: list[Union[ReasonCode, str]] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sync_match_result(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rid = data.get("recall_id") or data.get("recall_number") or ""
            data.setdefault("recall_id", rid)
            data.setdefault("recall_number", rid)
        return data


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """An event emitted by the pipeline, consumed by the SSE stream and UI."""
    run_id: str
    seq: int = 0
    type: str  # one of EventType values
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    id: str
    kind: str  # NodeKind value
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str  # EdgeKind value
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    # Invariant: len(evidence_ids) >= 1 for MATCHES edges


class GraphJSON(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class ReportListingRow(BaseModel):
    listing_id: str
    url: str = ""
    title: str = ""
    brand: str = ""
    model: str = ""
    best_tier: Union[Tier, str]
    reasons: list[Union[ReasonCode, str]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class SourceChecked(BaseModel):
    source: str
    url: str = ""
    checked_at: datetime | None = None
    status: str = "checked"  # "checked" or "not_checked"


class ReportJSON(BaseModel):
    run_id: str
    recall_number: str = ""
    recall_title: str = ""
    mode: Literal["live", "recorded"] = "live"
    tier_counts: dict[str, int] = Field(default_factory=dict)
    listings: list[ReportListingRow] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    unresolved: list[dict[str, Any]] = Field(default_factory=list)
    coverage: list[SourceChecked] = Field(default_factory=list)
    disclaimer: str = (
        "Redthread reports what was matched in the sources it checked. "
        "'No match found in checked sources' is not a statement about product safety. "
        "Always follow the official notice and remedy."
    )


# ---------------------------------------------------------------------------
# LLM protocol
# ---------------------------------------------------------------------------

class LLM(Protocol):
    """Protocol for LLM provider implemented by M2 in matching/llm.py."""
    async def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        ...

    async def choose_action(
        self,
        system: str,
        observation: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ...

    async def generate(self, prompt: str, *, system: str = "", json_mode: bool = False) -> str:
        ...
