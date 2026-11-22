"""
Redthread shared contracts.
All team members import from here. M3 owns this file.
Do NOT modify without team agreement.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, Protocol

from pydantic import BaseModel, Field


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


class RecallScope(BaseModel):
    """Describes the scope of a recall (all units, date range, lot range, etc.)."""
    kind: Literal["all_units", "date_range", "lot_range", "serial_range", "unknown"] = "unknown"
    date_start: date | None = None
    date_end: date | None = None
    lot_codes: list[str] = Field(default_factory=list)
    description: str = ""


class RecallRecord(BaseModel):
    """An official recall record from an authority (e.g., CPSC)."""
    authority: str = "CPSC"
    recall_number: str
    title: str = ""
    description: str = ""
    url: str = ""

    brand: str = ""
    product_name: str = ""
    models: list[str] = Field(default_factory=list)
    gtins: list[str] = Field(default_factory=list)
    hazard: str = ""
    remedy: str = ""
    units_affected: str = ""
    scope: RecallScope = Field(default_factory=RecallScope)

    manufacture_dates: str = ""
    sold_at: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)

    source_tier: SourceTier = SourceTier.A
    raw: dict[str, Any] = Field(default_factory=dict)


class PageCapture(BaseModel):
    """A captured web page: URL, text content, screenshot path, etc."""
    url: str
    final_url: str = ""
    title: str = ""
    text: str = ""
    html_snippet: str = ""
    screenshot_path: str = ""
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    source_tier: SourceTier = SourceTier.C
    blocked: bool = False
    error: str = ""


class InvestigationTask(BaseModel):
    """A task for the browser agent."""
    kind: TaskKind
    target_url: str
    recall: RecallRecord | None = None
    search_terms: list[str] = Field(default_factory=list)
    allow_domains: list[str] = Field(default_factory=list)
    max_pages: int = 20


class ExtractedListing(BaseModel):
    """A product listing extracted from a page by the LLM."""
    listing_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_url: str = ""
    variant_label: str = ""

    title: Quoted | None = None
    brand: Quoted | None = None
    model: Quoted | None = None
    gtin: Quoted | None = None
    lot_code: Quoted | None = None
    manufacture_date: Quoted | None = None
    price: Quoted | None = None
    seller: Quoted | None = None
    description: Quoted | None = None

    identifiers: dict[str, Quoted] = Field(default_factory=dict)
    page_text: str = ""  # full page text for quote verification


class Evidence(BaseModel):
    """A piece of evidence supporting a match edge."""
    evidence_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    field: str  # which field matched (e.g., "model", "gtin", "brand")
    listing_value: str
    recall_value: str
    comparison: str  # how they were compared (e.g., "exact", "canonical", "fuzzy")
    evidence_quote: str = ""
    page_url: str = ""
    screenshot_path: str = ""


class MatchResult(BaseModel):
    """The verdict for one listing vs. one recall."""
    listing_id: str
    recall_number: str
    tier: Tier
    reasons: list[ReasonCode] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str = ""


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """An event emitted by the pipeline, consumed by the SSE stream and UI."""
    run_id: str
    seq: int = 0
    type: str  # one of EventType values
    timestamp: datetime = Field(default_factory=datetime.utcnow)
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
    best_tier: Tier
    reasons: list[ReasonCode] = Field(default_factory=list)
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
    """Minimal protocol for an LLM provider.
    M2 implements this in matching/llm.py with get_llm().
    """
    async def generate(self, prompt: str, *, system: str = "", json_mode: bool = False) -> str:
        """Send a prompt and return the text response."""
        ...
