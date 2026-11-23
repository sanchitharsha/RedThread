"""Regex stand-in used ONLY by FakeLLM (LLM_PROVIDER=fake) for offline demos.

It is not an LLM and makes no claim to understand pages: it reads "Label: value" lines and
returns verbatim quotes, so the real verify/match code paths run unchanged. Real runs use a
real provider.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from matching.schemas import ListingExtractionOut, NoticeExtractionOut, QuotedOut

_UNTRUSTED = re.compile(r"<<<UNTRUSTED_PAGE_TEXT_BEGIN>>>(.*?)<<<UNTRUSTED_PAGE_TEXT_END>>>", re.S)


def _page(user: str) -> str:
    m = _UNTRUSTED.search(user)
    return m.group(1) if m else user


def _q(line: str, value: str) -> dict:
    return {"value": value.strip(), "evidence_quote": line.strip()}


def _find(text: str, label_rx: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        m = re.match(rf"^\s*(?:{label_rx})\s*[:\-]\s*(.+?)\s*$", line, re.I)
        if m:
            out.append((line, m.group(1)))
    return out


def _split_ids(value: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,]| and ", value) if p.strip()]


def heuristic_output(schema: type[BaseModel], user: str) -> dict:
    text = _page(user)
    if schema is ListingExtractionOut:
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")

        def one(block_text: str, label: Optional[str] = None) -> dict:
            def pick(rx):
                r = _find(block_text, rx)
                return _q(*r[0]) if r else None
            return {
                "variant_label": ({"value": label, "evidence_quote": label} if label else None),
                "brand": pick(r"brand|manufacturer"),
                "product_name": ({"value": first, "evidence_quote": first} if first else None),
                "model_numbers": [_q(l, v) for l, v in _find(block_text, r"model(?: no\.?| number)?")],
                "gtins": [_q(l, v) for l, v in _find(block_text, r"gtin|upc|ean")],
                "lot_or_date_info": [_q(l, v) for l, v in
                                     _find(block_text, r"manufactured|manufacture date|date code|lot(?: code)?")],
                "seller": pick(r"seller|sold by"),
            }
        variant_lines = [l for l in text.splitlines() if re.match(r"^\s*variant\b", l, re.I)]
        if variant_lines:
            shared = one(text)
            listings = []
            for l in variant_lines:
                v = dict(shared)
                m = re.search(r"model(?: no\.?| number)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 \-]*)", l, re.I)
                v["variant_label"] = {"value": l.strip(), "evidence_quote": l.strip()}
                v["model_numbers"] = [_q(l, m.group(1))] if m else []
                listings.append(v)
            return {"listings": listings}
        return {"listings": [one(text)]}
    if schema is NoticeExtractionOut:
        models = [_q(l, p) for l, v in _find(text, r"models?(?: numbers?)?") for p in _split_ids(v)]
        gtins = [_q(l, p) for l, v in _find(text, r"gtin|upc|ean") for p in _split_ids(v)]
        retailers = [_q(l, p) for l, v in _find(text, r"sold at|retailers?") for p in _split_ids(v)]
        brands = [_q(l, v) for l, v in _find(text, r"brand")]
        scope = None
        for line in text.splitlines():
            if re.search(r"\ball\s+(?:\w+\s+){0,3}?units\b", line, re.I):
                scope = {"scope_type": "all_units", "evidence_quote": line.strip()}
                break
        return {"brands": brands, "models": models, "gtins": gtins, "retailers": retailers, "scope": scope}
    raise NotImplementedError(f"fake heuristic has no handler for {schema.__name__}")
