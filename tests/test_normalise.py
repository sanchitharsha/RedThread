from datetime import date

import pytest

from matching import normalise as n


def test_canon_model():
    assert n.canon_model("kx - 200") == "KX200"
    assert n.canon_model(" KX-200 ") == n.canon_model("kx200") == "KX200"
    assert n.canon_model("ＫＸ－２００") == "KX200"   # full-width


@pytest.mark.parametrize("g,ok", [
    ("036000291452", True),          # known valid UPC-A
    ("036000291453", False),         # same number, wrong check digit
    ("0 36000 29145 2", True),       # spaces ignored
    ("036-000-291-452", True),
    ("00000000", True),              # GTIN-8 all zeros is arithmetically valid
    ("96385074", True),              # GTIN-8 example (check digit verified by hand)
    ("96385075", False),
    ("4006381333931", True),         # EAN-13 example
    ("4006381333932", False),
    ("12345", False),                # wrong length
    ("", False),
    ("abcdefghijkl", False),
])
def test_gtin_ok(g, ok):
    assert n.gtin_ok(g) is ok


def test_gtin14():
    body = "1003600029145"           # GTIN-14 = indicator 1 + UPC-A body
    d = n.digits(body)
    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(d)))
    gtin14 = body + str((10 - total % 10) % 10)
    assert n.gtin_ok(gtin14)
    assert not n.gtin_ok(gtin14[:-1] + str((int(gtin14[-1]) + 1) % 10))


def test_brand_norm():
    assert n.brand_norm("Acme, Inc.") == n.brand_norm("ACME") == "acme"
    assert n.brand_norm("A.B.C. Co.") == "abc"
    assert n.brand_norm("Foo Bar LLC") == n.brand_norm("foo-bar ltd") == "foo bar"
    assert n.brand_norm(None) == "" == n.brand_norm("")


def test_brand_alias_mechanism(monkeypatch):
    monkeypatch.setitem(n.BRAND_ALIASES, "oldname", "newname")
    assert n.brand_norm("OldName Inc") == "newname"


def test_parse_scope():
    assert n.parse_scope("This recall involves all units sold.") == ("all_units", None, None)
    assert n.parse_scope("manufactured between March 2020 and June 2021") == ("range", "2020-03-01", "2021-06-30")
    assert n.parse_scope("made from 2021-01-01 to 2021-06-30") == ("range", "2021-01-01", "2021-06-30")
    assert n.parse_scope("sold between 03/15/2021 and 12/31/2021") == ("range", "2021-03-15", "2021-12-31")
    assert n.parse_scope("manufactured after January 5, 2022") == ("range", "2022-01-05", None)
    assert n.parse_scope("manufactured before June 2020") == ("range", None, "2020-06-30")
    assert n.parse_scope("lot codes 4411 through 4499") == ("unknown", None, None)
    assert n.parse_scope("") == ("unknown", None, None)
    # a date mention next to "all units" is not an all-units claim
    assert n.parse_scope("all units manufactured before June 2020")[0] == "range"


def test_find_dates_no_double_count():
    spans = n.find_dates("Manufactured 15 March 2021")
    assert spans == [(date(2021, 3, 15), date(2021, 3, 15))]
    assert n.find_dates("not a date 13/2021 or 2021-13-40") == []


def test_similarity_bounds_and_advisory():
    assert n.similarity("Acme Widget", "acme widget") == 1.0
    assert n.similarity("", "x") == 0.0
    assert n.similarity("garden hose reel", "space heater") < 0.5
    assert n.model_similarity("KX-200", "KX201") > 0.7
    assert n.model_similarity("KX-200", "ZZ-9999") < 0.5
