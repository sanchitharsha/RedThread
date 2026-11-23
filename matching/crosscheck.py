"""Compare two OFFICIAL records of the same recall. Used only if a second record exists.

find_conflicts(a, b) -> list of conflict dicts:
  {"code": "CONFLICT_*", "field": ..., "a": side, "b": side}
  side = {"recall_id", "url", "value", "quote", "quote_verified"}
The mini prototype has one official source (CPSC), so callers normally get [].
"""
from __future__ import annotations

from contracts.models import RecallRecord
from matching.normalise import canon, similarity

TEXT_SIM_THRESHOLD = 0.8   # heuristic; a false conflict only makes results MORE cautious


def _rid(r: RecallRecord) -> str:
    return f"{r.authority}:{r.number}"


def _side(r: RecallRecord, value, quote: str | None, default_quote: str) -> dict:
    return {"recall_id": _rid(r), "url": r.url, "value": value,
            "quote": quote or default_quote, "quote_verified": True}


def _model_quote(r: RecallRecord, canons: set[str]) -> str | None:
    qs = [q for k, q in r.quotes.items() if k.startswith("model:") and k[6:] in canons]
    return " | ".join(qs) or None


def find_conflicts(recall_a: RecallRecord, recall_b: RecallRecord) -> list[dict]:
    out: list[dict] = []

    ma = {canon(m) for m in recall_a.models if canon(m)}
    mb = {canon(m) for m in recall_b.models if canon(m)}
    if ma and mb and ma != mb:
        diff = ma ^ mb
        out.append({"code": "CONFLICT_MODELS", "field": "models",
                    "a": _side(recall_a, sorted(recall_a.models), _model_quote(recall_a, diff),
                               "models: " + ", ".join(recall_a.models)),
                    "b": _side(recall_b, sorted(recall_b.models), _model_quote(recall_b, diff),
                               "models: " + ", ".join(recall_b.models))})

    sa = (recall_a.scope_type, recall_a.scope_from, recall_a.scope_to)
    sb = (recall_b.scope_type, recall_b.scope_from, recall_b.scope_to)
    if "unknown" not in (sa[0], sb[0]) and sa != sb:
        out.append({"code": "CONFLICT_SCOPE", "field": "scope",
                    "a": _side(recall_a, sa, recall_a.quotes.get("scope") or recall_a.scope_text, f"scope: {sa}"),
                    "b": _side(recall_b, sb, recall_b.quotes.get("scope") or recall_b.scope_text, f"scope: {sb}")})

    for code, fld in (("CONFLICT_HAZARD", "hazard"), ("CONFLICT_REMEDY", "remedy")):
        va, vb = getattr(recall_a, fld), getattr(recall_b, fld)
        if va and vb and similarity(va, vb) < TEXT_SIM_THRESHOLD:
            out.append({"code": code, "field": fld,
                        "a": _side(recall_a, va, recall_a.quotes.get(fld), va),
                        "b": _side(recall_b, vb, recall_b.quotes.get(fld), vb)})

    # RecallRecord has no `status` field (proposed contract addition); compared only when a
    # verified notice quote under key "status" exists on both records.
    qa, qb = recall_a.quotes.get("status"), recall_b.quotes.get("status")
    if qa and qb and canon(qa) != canon(qb):
        out.append({"code": "CONFLICT_STATUS", "field": "status",
                    "a": _side(recall_a, qa, qa, qa), "b": _side(recall_b, qb, qb, qb)})
    return out
