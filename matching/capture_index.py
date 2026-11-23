"""Process-local side-channel for provenance the contracts have no field for.

ExtractedListing / RecallRecord carry no retrieved_at, screenshot or dropped-field list,
but Evidence needs retrieved_at and the UI wants screenshots. extract.py / cpsc.py record
them here; match.py reads them. Everything here is advisory metadata: it NEVER influences
a tier. (Proposed contract fields that would remove the need for this: see M2 notes.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from contracts.models import PageCapture

_captures: dict[str, PageCapture] = {}           # source_url -> latest capture
_recall_fetched: dict[str, datetime] = {}        # "AUTH:number" -> fetch time
_dropped: dict[str, list[str]] = {}              # listing_id -> dropped-field descriptions


def now() -> datetime:
    return datetime.now(timezone.utc)


def register_capture(cap: PageCapture) -> None:
    _captures[cap.url] = cap


def get_capture(url: str) -> Optional[PageCapture]:
    return _captures.get(url)


def register_recall_fetch(recall_id: str, when: datetime) -> None:
    _recall_fetched[recall_id] = when


def recall_fetched_at(recall_id: str) -> datetime:
    return _recall_fetched.get(recall_id) or now()


def set_dropped(listing_id: str, items: list[str]) -> None:
    _dropped[listing_id] = list(items)


def get_dropped(listing_id: str) -> list[str]:
    return list(_dropped.get(listing_id, []))


def clear() -> None:
    _captures.clear()
    _recall_fetched.clear()
    _dropped.clear()
