"""CPSC Recall REST API connector.

Root: https://www.saferproducts.gov/RestWebServices/Recall  (format=json, no API key)

!! FIELD / PARAMETER NAMES BELOW COME FROM THE PUBLIC DOCS AS REMEMBERED, NOT FROM A LIVE
!! RESPONSE (the build sandbox could not reach the API). `python -m matching.connectors.cpsc
!! <ref> --fields` prints the real names from a live call: verify them, then adjust FIELD_MAP.
All lookups are case-insensitive and tolerant of missing fields, and several parameter
spellings are tried in turn (the docs disagree: RecallNumber / RecallID / RecallTitle / Title).
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from contracts.models import RecallRecord
from matching import capture_index as ci
from matching.normalise import canon, digits, parse_scope

log = logging.getLogger("redthread.cpsc")

API_ROOT = "https://www.saferproducts.gov/RestWebServices/Recall"
UA = "Redthread-Hackathon-Bot"
TIMEOUT = 20.0

# Field names as (assumed) in the API response. Verify with --fields.
FIELD_MAP = {
    "number": ("RecallNumber",), "id": ("RecallID",), "title": ("Title", "RecallTitle"),
    "date": ("RecallDate",), "updated": ("LastPublishDate",), "description": ("Description",),
    "url": ("URL",), "products": ("Products",), "product_model": ("Model",),
    "upcs": ("ProductUPCs",), "upc": ("UPC",), "hazards": ("Hazards",), "remedies": ("Remedies",),
    "remedy_options": ("RemedyOptions",), "retailers": ("Retailers",), "manufacturers": ("Manufacturers",),
    "name": ("Name",),
}


def fixtures_dir() -> Path:
    return Path(os.getenv("FIXTURES_DIR", "fixtures"))


# ------------------------------------------------------------------ helpers

def _g(d: Any, key: str, default: Any = None) -> Any:
    """Case-insensitive lookup of any of FIELD_MAP[key]'s spellings."""
    if not isinstance(d, dict):
        return default
    lowered = {str(k).lower(): v for k, v in d.items()}
    for name in FIELD_MAP[key]:
        if name.lower() in lowered and lowered[name.lower()] not in (None, ""):
            return lowered[name.lower()]
    return default


def _names(items: Any, key: str = "name") -> list[str]:
    out = []
    for it in items or []:
        v = _g(it, key) if isinstance(it, dict) else it
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _split_models(raw: str) -> list[str]:
    out = []
    for part in re.split(r"[;,\n/]| and ", raw or ""):
        # strip only an explicit label ("Model No.", "Model:", "Models #"); never part of an identifier
        p = re.sub(r"^\s*models?\s*(?:(?:no\.?|number)s?\s*[:#.]?|[:#])\s*", "", part, flags=re.I).strip(" .")
        if len(canon(p)) >= 3:
            out.append(p)
    return out


def _gtin_strings(items: Any) -> list[str]:
    out = []
    for it in items or []:
        v = _g(it, "upc") if isinstance(it, dict) else it
        if not isinstance(v, str):
            continue
        d = digits(v)
        out.append(d if len(d) in (8, 12, 13, 14) else v.strip())   # keep odd values for audit; matcher ignores invalid
    return out


_MANUF = re.compile(r"manufactur|produced|made\b|date code|lot\b|serial", re.I)


def _scope_from_description(desc: str) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Conservative: a date range counts only in a sentence about manufacture, not sale dates."""
    found_all = None
    for sent in re.split(r"(?<=[.!?])\s+", desc):
        t, f, to = parse_scope(sent)
        if t == "range" and _MANUF.search(sent):
            return "range", f, to, sent
        if t == "all_units" and found_all is None:
            found_all = sent
    if found_all:
        return "all_units", None, None, found_all
    return "unknown", None, None, None


def map_record(rec: dict, raw_ref: str = "") -> RecallRecord:
    number = str(_g(rec, "number", "") or _g(rec, "id", "") or "UNKNOWN")
    desc = _clean_text(_g(rec, "description", "") or "")
    models: list[str] = []
    seen = set()
    for p in _g(rec, "products", []) or []:
        for m in _split_models(_g(p, "product_model", "") or ""):
            if canon(m) not in seen:
                seen.add(canon(m))
                models.append(m)
    hazards = _names(_g(rec, "hazards", []))
    remedies = _names(_g(rec, "remedies", [])) or _names(_g(rec, "remedy_options", []), "name")
    manuf = _names(_g(rec, "manufacturers", []))
    stype, sfrom, sto, stext = _scope_from_description(desc)
    quotes = {"scope": stext} if stext else {}
    url = _g(rec, "url") or f"{API_ROOT}?format=json&RecallNumber={number}"
    return RecallRecord(
        authority="CPSC", number=number, title=_clean_text(_g(rec, "title", "") or number),
        date=(str(_g(rec, "date", "") or "")[:10] or None),
        source_updated=(str(_g(rec, "updated", "") or "")[:10] or None),
        brand=manuf[0] if manuf else None,
        hazard="; ".join(hazards) or None, remedy="; ".join(remedies) or None,
        models=models, gtins=_gtin_strings(_g(rec, "upcs", [])), retailers=_names(_g(rec, "retailers", [])),
        scope_type=stype, scope_from=sfrom, scope_to=sto, scope_text=stext,
        url=url, source_tier="A", raw_ref=raw_ref, quotes=quotes)


# ---------------------------------------------------------------------- HTTP

def http_get_json(params: dict) -> Any:
    import httpx
    r = httpx.get(API_ROOT, params={"format": "json", **params}, headers={"User-Agent": UA},
                  timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def _param_attempts(ref: str) -> list[tuple[str, str]]:
    out = []
    for value in dict.fromkeys([ref, ref.replace("-", "")]):
        out.append(("RecallNumber", value))
    if ref.isdigit():
        out.append(("RecallID", ref))
    out += [("RecallTitle", ref), ("Title", ref)]
    return out


def _pick(records: Any, ref: str) -> Optional[dict]:
    recs = records if isinstance(records, list) else ([records] if isinstance(records, dict) else [])
    recs = [r for r in recs if isinstance(r, dict)]
    for r in recs:                       # exact number match first
        if canon(str(_g(r, "number", ""))) == canon(ref) or str(_g(r, "id", "")) == ref:
            return r
    return recs[0] if recs else None


def _norm_ref(ref: str) -> str:
    return re.sub(r"^\s*cpsc\s*:\s*", "", ref, flags=re.I).strip()


def _fixture_candidates(ref: str) -> list[Path]:
    d = fixtures_dir()
    return [d / f"cpsc_raw_{ref}.json", d / "cpsc_sample.json", d / "cpsc_sample.PLACEHOLDER.json"]


def _load_fixture(ref: str) -> tuple[RecallRecord, datetime]:
    for p in _fixture_candidates(ref):
        if p.exists():
            rec = _pick(json.loads(p.read_text()), ref)
            if rec is None:
                continue
            if p.name == "cpsc_sample.json" and ref not in ("hero", "26419", ""):
                if canon(str(_g(rec, "number", ""))) != canon(ref) and str(_g(rec, "id", "")) != ref:
                    continue
            if "PLACEHOLDER" in p.name:
                log.warning("=" * 70 + "\nUSING PLACEHOLDER RECALL DATA (%s). NOT A REAL RECALL.\n" + "=" * 70, p)
            elif canon(str(_g(rec, "number", ""))) != canon(ref):
                log.warning("offline fixture %s holds recall %s, not the requested %s", p.name,
                            _g(rec, "number"), ref)
            when = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            return map_record(rec, raw_ref=str(p)), when
    raise FileNotFoundError(f"No offline fixture for {ref!r} under {fixtures_dir()}/ "
                            "(run `python -m matching.connectors.cpsc <ref> --save-sample` online first)")


def fetch_recall(ref: str) -> RecallRecord:
    """ref: 'CPSC:<number>', '<number>', a RecallID, or a title. OFFLINE=1 or any failure -> fixtures/."""
    ref = _norm_ref(ref)
    if os.getenv("OFFLINE") != "1":
        last_err: Optional[Exception] = None
        for name, value in _param_attempts(ref):
            try:
                data = http_get_json({name: value})
            except Exception as exc:  # noqa: BLE001  network or HTTP failure
                last_err = exc
                log.info("CPSC %s=%s failed: %s", name, value, exc)
                import httpx
                if isinstance(exc, (httpx.HTTPStatusError, ValueError)):
                    continue         # this spelling was rejected / not JSON: try the next one
                break                # network down: do not hammer; fall back to fixtures
            rec = _pick(data, ref)
            if rec is None:
                continue
            number = str(_g(rec, "number", "") or ref)
            fixtures_dir().mkdir(parents=True, exist_ok=True)
            raw_path = fixtures_dir() / f"cpsc_raw_{re.sub(r'[^A-Za-z0-9_-]', '', number)}.json"
            raw_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("CPSC lookup worked with %s=%s", name, value)
            ci.register_recall_fetch(f"CPSC:{number}", datetime.now(timezone.utc))
            return map_record(rec, raw_ref=str(raw_path))
        log.warning("CPSC API unavailable or no match (%s); falling back to fixtures/", last_err)
    rec, when = _load_fixture(ref)
    ci.register_recall_fetch(f"CPSC:{rec.number}", when)
    return rec


# ----------------------------------------------------------------------- CLI

def _field_names(rec: dict, prefix: str = "") -> list[str]:
    names = []
    for k, v in rec.items():
        names.append(prefix + k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            names += _field_names(v[0], prefix + k + "[].")
    return names


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Fetch one CPSC recall; optionally save it as the hero fixture.")
    ap.add_argument("ref")
    ap.add_argument("--fields", action="store_true", help="print the real field names of the raw record")
    ap.add_argument("--save-sample", action="store_true", help="write fixtures/cpsc_sample.json (list of one record)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    r = fetch_recall(a.ref)
    print(r.model_dump_json(indent=2))
    if r.raw_ref and "PLACEHOLDER" not in r.raw_ref:
        raw = json.loads(Path(r.raw_ref).read_text())
        rec = _pick(raw, _norm_ref(a.ref)) or {}
        if a.fields:
            print("\nREAL FIELD NAMES:\n  " + "\n  ".join(_field_names(rec)))
        if a.save_sample:
            p = fixtures_dir() / "cpsc_sample.json"
            p.write_text(json.dumps([rec], indent=2, ensure_ascii=False))
            print(f"\nsaved hero fixture -> {p}")
    elif a.fields or a.save_sample:
        print("\nPLACEHOLDER/offline data in use: nothing real to save. Run online.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
