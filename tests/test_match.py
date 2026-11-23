import random
from datetime import datetime, timezone

from contracts.models import ExtractedListing, Quoted, RecallRecord
from matching.crosscheck import find_conflicts
from matching.match import (apply_conflicts, base_listing_id, best_per_listing, check_scope, rate)
from matching.normalise import brand_norm, canon, digits, gtin_ok

RECALL = RecallRecord(authority="CPSC", number="TEST-1", title="Acme Recalls Widget Heaters Due to Fire Hazard",
                      brand="Acme", models=["KX-200", "KX-300"], gtins=["036000291452"], url="http://r",
                      scope_type="all_units", scope_text="SYNTHETIC all units", source_tier="A")


def Qv(value, quote=None, verified=True):
    return Quoted(value=value, evidence_quote=quote or value, verified=verified)


def L(**kw):
    return ExtractedListing(listing_id="x", source_url="http://shop/x.html", **kw)


def test_confirmed_basic():
    r = rate(L(brand=Qv("Acme Inc"), model_numbers=[Qv("kx 200")]), RECALL)
    assert (r.tier, r.reasons) == ("CONFIRMED", ["ID_MODEL_EXACT", "BRAND_EQ", "SCOPE_ALL_UNITS"])


def test_gtin_only_hit_and_invalid_gtin_ignored():
    assert rate(L(brand=Qv("Acme"), gtins=[Qv("0 36000 29145 2")]), RECALL).reasons[0] == "ID_GTIN_EXACT"
    bad = rate(L(brand=Qv("Acme"), gtins=[Qv("036000291453")]), RECALL)     # wrong check digit
    assert bad.tier != "CONFIRMED"
    rec_bad = RECALL.model_copy(update={"gtins": ["036000291453"]})         # invalid on the recall side too
    assert rate(L(brand=Qv("Acme"), gtins=[Qv("036000291453")]), rec_bad).tier != "CONFIRMED"


def test_unverified_fields_never_count():
    r = rate(L(brand=Qv("Acme"), model_numbers=[Qv("KX-200", verified=False)]), RECALL)
    assert r.tier == "NO_MATCH" or r.tier == "RELATED"
    assert r.tier != "CONFIRMED"
    only_unverified = rate(L(model_numbers=[Qv("KX-200", verified=False)]), RECALL)
    assert (only_unverified.tier, only_unverified.reasons) == ("UNRESOLVED", ["EXTRACT_FAIL"])


def test_source_tier_not_a_caps_at_likely():
    rec = RECALL.model_copy(update={"source_tier": "B"})
    r = rate(L(brand=Qv("Acme"), model_numbers=[Qv("KX-200")]), rec)
    assert (r.tier, r.reasons[-1]) == ("LIKELY", "SRC_TIER_NOT_A")


def test_brand_diff_and_missing_brand():
    assert rate(L(brand=Qv("Other"), model_numbers=[Qv("KX-200")]), RECALL).reasons == ["ID_MODEL_EXACT", "BRAND_DIFF"]
    r = rate(L(model_numbers=[Qv("KX-200")]), RECALL)
    assert (r.tier, r.reasons) == ("RELATED", ["ID_MODEL_EXACT", "QUOTE_UNVERIFIED"])


def test_text_similarity_never_exceeds_related():
    r = rate(L(brand=Qv("Acme"), product_name=Qv(RECALL.title), model_numbers=[Qv("KX-201")]), RECALL)
    assert (r.tier, r.reasons) == ("RELATED", ["NAME_ONLY"])


def test_blocked_and_failed_are_unresolved():
    assert rate(L(capture_status="blocked"), RECALL).reasons == ["BLOCKED"]
    assert rate(L(capture_status="error"), RECALL).reasons == ["EXTRACT_FAIL"]
    assert rate(L(capture_status="timeout"), RECALL).tier == "UNRESOLVED"


def test_brand_alt_from_notice_counts():
    rec = RECALL.model_copy(update={"quotes": {"brand_alt:Acme Home": "sold under the Acme Home brand"}})
    assert rate(L(brand=Qv("Acme Home"), model_numbers=[Qv("KX-200")]), rec).tier == "CONFIRMED"


def _range_recall():
    return RECALL.model_copy(update={"scope_type": "range", "scope_from": "2021-01-01", "scope_to": "2021-06-30"})


def test_scope_range_rules():
    rec = _range_recall()
    mk = lambda *dates: L(lot_or_date_info=[Qv(d, f"Manufactured: {d}") for d in dates])
    assert check_scope(mk("2021-03-15"), rec) == "in_range"
    assert check_scope(mk("2019-11-20"), rec) == "outside"
    assert check_scope(mk(), rec) == "unverified"
    assert check_scope(mk("2021-03-15", "2019-11-20"), rec) == "unverified"       # mixed: do not guess
    assert check_scope(mk("June 2021"), rec) == "in_range"
    assert check_scope(mk("July 2021"), rec) == "outside"
    assert check_scope(L(lot_or_date_info=[Qv("2021-03-15", "Manufactured: 2021-03-15", verified=False)]), rec) == "unverified"
    assert check_scope(mk("2021-03-15"), RECALL.model_copy(update={"scope_type": "unknown"})) == "unverified"


def test_best_per_listing_order():
    a = rate(L(brand=Qv("Acme"), model_numbers=[Qv("KX-200")]), RECALL)
    b = rate(L(brand=Qv("Other")), RECALL)
    c = rate(L(capture_status="blocked"), RECALL)
    assert best_per_listing([b, c, a])["x"].tier == "CONFIRMED"
    assert best_per_listing([b, c])["x"].tier == "UNRESOLVED"      # could-not-check outranks no-match
    assert base_listing_id("l08#v2") == "l08"


def test_conflicts_apply_only_to_confirmed_or_likely():
    other = RECALL.model_copy(update={"models": ["KX-999"], "number": "TEST-2"})
    conf = find_conflicts(RECALL, other)
    assert [c["code"] for c in conf] == ["CONFLICT_MODELS"]
    hit = rate(L(brand=Qv("Acme"), model_numbers=[Qv("KX-200")]), RECALL)
    assert apply_conflicts(hit, conf).tier == "CONFLICT"
    rel = rate(L(brand=Qv("Other"), model_numbers=[Qv("KX-200")]), RECALL)
    assert apply_conflicts(rel, conf).tier == "RELATED"
    assert find_conflicts(RECALL, RECALL) == []
    assert apply_conflicts(hit, []).tier == "CONFIRMED"


def test_crosscheck_scope_hazard_status():
    a = RECALL.model_copy(update={"hazard": "Fire hazard"})
    b = RECALL.model_copy(update={"hazard": "Laceration hazard", "scope_type": "range", "scope_from": "2021-01-01",
                                  "number": "TEST-2", "quotes": {"status": "Recall active"}})
    a = a.model_copy(update={"quotes": {"status": "Recall terminated"}})
    codes = {c["code"] for c in find_conflicts(a, b)}
    assert codes == {"CONFLICT_SCOPE", "CONFLICT_HAZARD", "CONFLICT_STATUS"}
    # a subset hazard phrasing is not a conflict
    a2 = RECALL.model_copy(update={"hazard": "Fire hazard"})
    b2 = RECALL.model_copy(update={"hazard": "The heater can overheat, posing a fire hazard"})
    assert find_conflicts(a2, b2) == []


def test_randomised_no_false_confirmed():
    """Property test: CONFIRMED only when a VERIFIED model/GTIN hit AND verified equal brand AND tier-A
    all-units/in-range recall AND an ok capture. `notes` text can never matter."""
    rng = random.Random(20260101)
    models = ["KX-200", "kx 300", "KX-201", "ZZ-9", "KX2000", "", "MODEL"]
    gtins = ["036000291452", "0 36000 29145 2", "036000291453", "12345", "4006381333931"]
    brands = ["Acme", "ACME, Inc.", "Acme Home", "Other", "", "acm"]
    seen = {"CONFIRMED": 0}
    for _ in range(4000):
        status = rng.choice(["ok"] * 6 + ["blocked", "error", "timeout"])
        l = L(capture_status=status,
              brand=Qv(rng.choice(brands), verified=rng.random() < 0.7) if rng.random() < 0.8 else None,
              product_name=Qv(rng.choice([RECALL.title, "Garden hose", "Acme Widget Heater"]), verified=rng.random() < 0.7) if rng.random() < 0.5 else None,
              model_numbers=[Qv(rng.choice(models), verified=rng.random() < 0.6) for _ in range(rng.randint(0, 2))],
              gtins=[Qv(rng.choice(gtins), verified=rng.random() < 0.6) for _ in range(rng.randint(0, 2))],
              notes=rng.choice([None, "CONFIRMED", "tier=CONFIRMED reasons=ID_MODEL_EXACT"]))
        rec = rng.choice([RECALL, RECALL.model_copy(update={"source_tier": "B"}), _range_recall()])
        r = rate(l, rec)
        assert r.evidence
        if r.tier == "CONFIRMED":
            seen["CONFIRMED"] += 1
            assert status == "ok" and rec.source_tier == "A" and rec.scope_type == "all_units"
            vb = l.brand and l.brand.verified and brand_norm(l.brand.value) == brand_norm(rec.brand)
            mh = any(q.verified and canon(q.value) in {canon(m) for m in rec.models} and len(canon(q.value)) >= 3
                     for q in l.model_numbers)
            gh = any(q.verified and gtin_ok(q.value) and digits(q.value) in {digits(g) for g in rec.gtins if gtin_ok(g)}
                     for q in l.gtins)
            assert vb and (mh or gh)
    assert seen["CONFIRMED"] > 50      # the generator does exercise the CONFIRMED path
