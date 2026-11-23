"""Golden tests (offline). Pages are SYNTHETIC; identifiers come from the recall fixture
(real once fixtures/cpsc_sample.json exists, else the PLACEHOLDER fixture), range-scope recalls
are SYNTHETIC overrides. Each case runs the real pipeline: extract_listings (scripted FakeLLM
output) -> verify -> rate (-> apply_conflicts for G12).

Asserts expected tier AND reason codes, evidence on every result, and the global rule:
never a CONFIRMED where the expectation is not CONFIRMED.
"""
from __future__ import annotations

import asyncio
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.models import PageCapture, RecallRecord
from matching import capture_index as ci
from matching.connectors.cpsc import fetch_recall
from matching.crosscheck import find_conflicts
from matching.extract import extract_listings
from matching.llm import FakeLLM
from matching.match import annotate_dropped, apply_conflicts, rate
from matching.normalise import canon, digits, gtin_ok
from matching.schemas import ListingExtractionOut
from matching.verify import quote_ok

CASES = json.loads(Path(__file__).with_name("cases.json").read_text())["cases"]
DATE_IN, DATE_OUT = "2021-03-15", "2019-11-20"
SYNTH_GTIN = "000000000017"


def _sibling(model: str, taken: set[str]) -> str:
    for ch in "9876543210ZYXWVU":
        cand = model[:-1] + ch if model[-1].isalnum() else model + ch
        if canon(cand) not in taken:
            return cand
    raise AssertionError("no sibling found")


def _build_recalls() -> tuple[dict[str, RecallRecord], dict[str, str]]:
    base = fetch_recall("hero")
    notes = []
    brand = base.brand or "PLACEHOLDER-BRAND"
    models = list(base.models) or ["MODEL-AAA"]
    gtins = [g for g in base.gtins if gtin_ok(g)]
    if not gtins:
        gtins, _ = [SYNTH_GTIN], notes.append("fixture has no valid GTIN: SYNTHETIC GTIN injected for golden tests")
    if not base.brand or not base.models:
        notes.append("fixture lacks brand/models: placeholders injected for golden tests")
    for n in notes:
        warnings.warn(n)
    common = dict(brand=brand, models=models, gtins=gtins, quotes={}, source_tier="A")
    all_units = base.model_copy(update=dict(common, scope_type="all_units", scope_from=None, scope_to=None,
                                            scope_text="SYNTHETIC TEST SCOPE: all units"))
    rng = base.model_copy(update=dict(common, scope_type="range", scope_from="2021-01-01", scope_to="2021-06-30",
                                      scope_text="SYNTHETIC TEST SCOPE: manufactured between January 1, 2021 and June 30, 2021"))
    taken = {canon(m) for m in models}
    c = canon(models[0])
    g = digits(gtins[0])
    ctx = {
        "BRAND": brand, "OTHER_BRAND": "OtherBrandCo-SYNTH", "MODEL": models[0],
        "MODEL_SIB": _sibling(models[0], taken), "MODEL_OTHER": "ZZ-9999-SYNTH",
        "MODEL_SPACED": f"{c[:2].lower()} - {c[2:].lower()}",
        "GTIN": g, "GTIN_SPACED": f"{g[0]} {g[1:6]} {g[6:11]} {g[11:]}" if len(g) == 12 else g,
        "PRODUCT_SIMILAR": " ".join(base.title.split()[:4]) + " Mini",
        "DATE_IN": DATE_IN, "DATE_OUT": DATE_OUT,
    }
    return {"all_units": all_units, "range": rng}, ctx


RECALLS, CTX = _build_recalls()


def render(obj):
    s = json.dumps(obj)
    for k, v in CTX.items():
        s = s.replace("{{" + k + "}}", v)
    assert "{{" not in s, "unrendered token"
    return json.loads(s)


def run_case(case: dict, mode: str):
    case = render(case)
    recall = RECALLS[mode]
    cap = PageCapture(url=case["url"], title=case["id"], fetched_at=datetime.now(timezone.utc),
                      text=case["page"], status=case["capture_status"], block_reason=case.get("block_reason"))
    out = case["llm_output"]
    llm = FakeLLM(script=lambda schema, s, u: out)
    listings = asyncio.run(extract_listings(cap, llm))
    results = []
    for l in listings:
        r = rate(l, recall)
        if case.get("record_b_overrides"):
            b = recall.model_copy(update=case["record_b_overrides"])
            r = apply_conflicts(r, find_conflicts(recall, b))
        results.append(r)
    return case, listings, results, llm


@pytest.mark.parametrize("mode", ["all_units", "range"])
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden(case, mode):
    case, listings, results, llm = run_case(case, mode)
    expected = case["expect"][mode]
    assert {r.listing_id for r in results} == set(expected)
    for r in results:
        e = expected[r.listing_id]
        assert r.tier == e["tier"], (r.listing_id, r.reasons)
        assert r.reasons == e["reasons"]
        if e["tier"] != "CONFIRMED":
            assert r.tier != "CONFIRMED"                       # global: no false CONFIRMED
        assert r.evidence, "every result carries evidence (graph edges need it)"
        for ev in r.evidence:
            if ev.source_url == case["url"] and ev.method == "llm_extract+quote_check":
                assert ev.quote_verified and quote_ok(ev.quote, case["page"])
    if "expect_llm_calls" in case:
        assert len(llm.calls) == case["expect_llm_calls"]
    if case.get("expect_dropped"):
        dropped = ci.get_dropped(results[0].listing_id)
        assert [d.split("=")[0] for d in dropped] == case["expect_dropped"]
        ann = annotate_dropped(results[0])
        assert ann.tier == results[0].tier and "QUOTE_UNVERIFIED" in ann.reasons   # annotation never changes tier


def test_g11_dropped_fields_absent_from_listing():
    case = next(c for c in CASES if c["id"] == "G11")
    _, listings, results, _ = run_case(case, "all_units")
    l = listings[0]
    assert l.model_numbers == [] and l.gtins == []
    assert results[0].tier not in ("CONFIRMED", "LIKELY")


def test_g12_conflict_evidence_has_both_records():
    case = next(c for c in CASES if c["id"] == "G12")
    _, _, results, _ = run_case(case, "all_units")
    r = results[0]
    assert r.tier == "CONFLICT" and "CONFLICT_MODELS" in r.reasons
    assert sum(e.method == "official_record_compare" for e in r.evidence) >= 2


def test_l09_injection_text_cannot_alter_extraction_contract():
    """The page's hidden instruction is plain data: nothing in code reads it, and the model's
    output has no tier field to set."""
    case = next(c for c in CASES if c["id"] == "L09")
    _, listings, results, llm = run_case(case, "all_units")
    assert "Ignore all previous instructions" in llm.calls[0][2]            # present only inside the delimiters
    assert llm.calls[0][2].count("<<<UNTRUSTED_PAGE_TEXT_BEGIN>>>") == 1
    assert results[0].tier == "NO_MATCH"
    assert not hasattr(listings[0], "tier")
    assert "tier" not in ListingExtractionOut.model_json_schema()["$defs"]["VariantOut"]["properties"]
