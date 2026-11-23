"""Pure normalisation helpers. No network, no LLM.

`similarity` is advisory: it may only ever suggest RELATED (see match.py).
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date
from typing import Optional

from rapidfuzz import fuzz

# ---------------------------------------------------------------- identifiers


def canon(s: str) -> str:
    """Uppercase, strip everything that is not A-Z / 0-9 (after Unicode NFKC)."""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def canon_model(s: str) -> str:
    return canon(s)


def digits(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\D", "", s)


def gtin_ok(s: str) -> bool:
    """GS1 check-digit validation for GTIN-8/12/13/14 (spaces/hyphens ignored)."""
    d = digits(s)
    if len(d) not in (8, 12, 13, 14):
        return False
    body, check = d[:-1], int(d[-1])
    total = 0
    for i, ch in enumerate(reversed(body)):  # rightmost body digit has weight 3
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10 == check


# ---------------------------------------------------------------------- brand

# Deliberately empty: aliases are factual claims about real companies, so they are added
# only when verified. Format: {"normalised alias": "normalised canonical"}.
BRAND_ALIASES: dict[str, str] = {}

_SUFFIXES = {"inc", "llc", "ltd", "co", "corp", "corporation", "company", "limited", "plc", "gmbh"}


def brand_norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[.'’`]", "", s)           # "a.b.c." -> "abc", "o'neil" -> "oneil"
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = [t for t in s.split() if t]
    while toks and toks[-1] in _SUFFIXES:   # strip trailing Inc / LLC / Ltd / Co ...
        toks.pop()
    out = " ".join(toks)
    return BRAND_ALIASES.get(out, out)


# ----------------------------------------------------------------- similarity


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def similarity(a: str, b: str) -> float:
    """0..1 fuzzy token similarity. ADVISORY ONLY: may suggest RELATED, nothing more."""
    a, b = _plain(a), _plain(b)
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0


def model_similarity(a: str, b: str) -> float:
    a, b = canon(a), canon(b)
    if not a or not b:
        return 0.0
    return fuzz.ratio(a, b) / 100.0


# ---------------------------------------------------------------------- dates

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MONTHS["sept"] = 9
_MON = "|".join(sorted(_MONTHS, key=len, reverse=True))

# (regex, builder) ; builder returns (start_date, end_date) for the matched text
_DATE_PATTERNS = [
    # 2021-03-15 / 2021/03/15
    (re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"),
     lambda m: _day(int(m[1]), int(m[2]), int(m[3]))),
    # 15 March 2021 / 15 Mar. 2021
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\.?,?\s+(\d{{4}})\b", re.I),
     lambda m: _day(int(m[3]), _MONTHS[m[2].lower()], int(m[1]))),
    # March 15, 2021
    (re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),
     lambda m: _day(int(m[3]), _MONTHS[m[1].lower()], int(m[2]))),
    # March 2021
    (re.compile(rf"\b({_MON})\.?,?\s+(\d{{4}})\b", re.I),
     lambda m: _month(int(m[2]), _MONTHS[m[1].lower()])),
    # 03/15/2021 (US month/day/year; only when day > 12 or unambiguous M/D)
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),
     lambda m: _day(int(m[3]), int(m[1]), int(m[2]))),
    # 03/2021
    (re.compile(r"\b(\d{1,2})/(\d{4})\b"),
     lambda m: _month(int(m[2]), int(m[1]))),
]


def _day(y: int, mo: int, d: int):
    try:
        x = date(y, mo, d)
    except ValueError:
        return None
    return x, x


def _month(y: int, mo: int):
    if not 1 <= mo <= 12:
        return None
    return date(y, mo, 1), date(y, mo, calendar.monthrange(y, mo)[1])


def find_dates(text: str) -> list[tuple[date, date]]:
    """All dates found in text as (start, end) spans (month-only dates span the month)."""
    spans: list[tuple[int, int, tuple[date, date]]] = []
    for rx, build in _DATE_PATTERNS:
        for m in rx.finditer(text or ""):
            if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in spans):
                continue  # already covered by a more specific pattern
            built = build(m)
            if built:
                spans.append((m.start(), m.end(), built))
    spans.sort(key=lambda t: t[0])
    return [x[2] for x in spans]


# ---------------------------------------------------------------------- scope

_ALL_UNITS = re.compile(
    r"\b(?:all|every)\s+(?:\w+\s+){0,3}?(?:units?|models?|products?|sizes?|colou?rs?|lots?|"
    r"batches|serial numbers?|date codes?)\b", re.I)
_RANGE_WORDS = re.compile(r"\b(?:between|from|manufactured|made|produced|sold|dated?)\b", re.I)


def parse_scope(text: str) -> tuple[str, Optional[str], Optional[str]]:
    """-> (type, from_iso, to_iso). type is 'all_units' | 'range' | 'unknown'.

    A range needs two dates, or one date with 'before/after/until/through'. Anything
    else (lot codes, vague wording) is 'unknown' so the matcher stays conservative.
    """
    t = text or ""
    dates = find_dates(t)
    if len(dates) >= 2 and _RANGE_WORDS.search(t):
        start = min(d[0] for d in dates)
        end = max(d[1] for d in dates)
        return "range", start.isoformat(), end.isoformat()
    if len(dates) == 1:
        if re.search(r"\b(?:after|since|from|beginning)\b", t, re.I):
            return "range", dates[0][0].isoformat(), None
        if re.search(r"\b(?:before|until|through|prior to)\b", t, re.I):
            return "range", None, dates[0][1].isoformat()
    if _ALL_UNITS.search(t) and not dates:
        return "all_units", None, None
    return "unknown", None, None
