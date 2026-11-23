"""Quote verification. CODE decides what is verified; the LLM never sets `verified`.

Rule: an extracted field survives only if
  1. its evidence_quote (>= 4 chars after normalisation) occurs in the page text
     (case- and whitespace-normalised substring), AND
  2. canon(value) occurs inside canon(evidence_quote)  (the value really is in the quote).
Unverified fields are DROPPED and cannot influence a verdict.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from contracts.models import ExtractedListing, Quoted
from matching.normalise import canon

MIN_QUOTE_LEN = 4
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_QUOTES = dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b"), "'")
_QUOTES.update(dict.fromkeys(map(ord, "\u201c\u201d\u201e\u201f"), '"'))


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.translate(_DASHES).translate(_QUOTES)
    return re.sub(r"\s+", " ", s).strip().casefold()


def quote_ok(q: str, page_text: str) -> bool:
    nq = norm_text(q)
    if len(nq) < MIN_QUOTE_LEN:
        return False
    return nq in norm_text(page_text)


def value_in_quote(value: str, quote: str) -> bool:
    cv = canon(value)
    return bool(cv) and cv in canon(quote)


def evidence_id(source_url: str, quote: str) -> str:
    h = hashlib.sha1(f"{source_url}\n{norm_text(quote)}".encode()).hexdigest()[:12]
    return f"ev_{h}"


def check_quoted(q: Quoted, page_text: str) -> tuple[bool, str]:
    """-> (ok, reason_if_not_ok)"""
    if not quote_ok(q.evidence_quote, page_text):
        return False, "quote_not_in_page"
    if not value_in_quote(q.value, q.evidence_quote):
        return False, "value_not_in_quote"
    return True, ""


@dataclass
class Dropped:
    field: str
    value: str
    reason: str

    def __str__(self) -> str:
        return f"{self.field}={self.value!r} ({self.reason})"


def _verify_one(field: str, q: Optional[Quoted], page_text: str, url: str,
                dropped: list[Dropped]) -> Optional[Quoted]:
    if q is None:
        return None
    ok, why = check_quoted(q, page_text)
    if not ok:
        dropped.append(Dropped(field, q.value, why))
        return None
    return q.model_copy(update={"verified": True, "evidence_id": evidence_id(url, q.evidence_quote)})


def _verify_list(field: str, qs: list[Quoted], page_text: str, url: str,
                 dropped: list[Dropped]) -> list[Quoted]:
    out = []
    for q in qs:
        v = _verify_one(field, q, page_text, url, dropped)
        if v is not None:
            out.append(v)
    return out


def apply_verification_report(listing: ExtractedListing,
                              page_text: str) -> tuple[ExtractedListing, list[Dropped]]:
    """Return (listing with only verified fields, report of what was dropped).

    Any incoming `verified=True` is ignored and recomputed: only this function sets it.
    """
    dropped: list[Dropped] = []
    u = listing.source_url
    new = listing.model_copy(update={
        "brand": _verify_one("brand", listing.brand, page_text, u, dropped),
        "product_name": _verify_one("product_name", listing.product_name, page_text, u, dropped),
        "model_numbers": _verify_list("model_numbers", listing.model_numbers, page_text, u, dropped),
        "gtins": _verify_list("gtins", listing.gtins, page_text, u, dropped),
        "lot_or_date_info": _verify_list("lot_or_date_info", listing.lot_or_date_info, page_text, u, dropped),
        "seller": _verify_one("seller", listing.seller, page_text, u, dropped),
        "variants": _verify_list("variants", listing.variants, page_text, u, dropped),
    })
    return new, dropped


def apply_verification(listing: ExtractedListing, page_text: str) -> ExtractedListing:
    return apply_verification_report(listing, page_text)[0]
