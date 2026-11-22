"""
Stub extract / enrich — returns fixture data when USE_STUBS=1.
M2 replaces this file.
Signatures MUST stay:
  async def extract_listings(capture, llm) -> list[ExtractedListing]
  async def enrich_recall(recall, notice, llm) -> RecallRecord
"""
from __future__ import annotations

from contracts.models import (
    ExtractedListing,
    PageCapture,
    RecallRecord,
    Quoted,
    LLM,
)


async def extract_listings(
    capture: PageCapture, llm: LLM
) -> list[ExtractedListing]:
    """
    Stub: extracts a single fake listing from each capture.
    Real implementation sends page text to the LLM for extraction.
    """
    # Build a Quoted value only if the quote can be found in the page text
    def _quoted(value: str, quote: str) -> Quoted:
        verified = quote in capture.text
        return Quoted(value=value, evidence_quote=quote, verified=verified)

    listing = ExtractedListing(
        source_url=capture.url,
        title=_quoted(
            capture.title or "PLACEHOLDER Product",
            capture.title or "PLACEHOLDER Product",
        ),
        brand=_quoted("PLACEHOLDER-BRAND", "Brand: PLACEHOLDER-BRAND"),
        model=_quoted("MODEL-AAA", "Model: MODEL-AAA"),
        gtin=_quoted("0000000000000", "GTIN: 0000000000000"),
        page_text=capture.text,
    )
    return [listing]


async def enrich_recall(
    recall: RecallRecord, notice: PageCapture, llm: LLM
) -> RecallRecord:
    """
    Stub: returns the recall as-is (real impl uses LLM to extract
    additional fields from the notice page).
    """
    return recall
