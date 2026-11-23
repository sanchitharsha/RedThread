"""LLM-facing output schemas (NOT contracts). They contain NO verdict/tier field on purpose:
the model only extracts fields with quotes; code verifies them and code decides verdicts.

No defaults anywhere: provider structured-output modes (OpenAI strict, Gemini) want every
field present, so "absent" is expressed as null / [].
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")   # unexpected keys (e.g. a injected "tier") are discarded


class QuotedOut(_Out):
    value: str            # copied exactly as written on the page
    evidence_quote: str   # contiguous verbatim text from the page that contains `value`


class VariantOut(_Out):
    variant_label: Optional[QuotedOut]
    brand: Optional[QuotedOut]
    product_name: Optional[QuotedOut]
    model_numbers: list[QuotedOut]
    gtins: list[QuotedOut]
    lot_or_date_info: list[QuotedOut]
    seller: Optional[QuotedOut]


class ListingExtractionOut(_Out):
    listings: list[VariantOut]   # one per purchasable variant; one entry if the page has none


class ScopeOut(_Out):
    scope_type: Literal["all_units", "range", "unknown"]
    evidence_quote: str


class NoticeExtractionOut(_Out):
    brands: list[QuotedOut]
    models: list[QuotedOut]
    gtins: list[QuotedOut]
    retailers: list[QuotedOut]
    scope: Optional[ScopeOut]
