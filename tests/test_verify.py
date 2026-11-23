from contracts.models import ExtractedListing, Quoted
from matching import verify as v

PAGE = "Acme Widget Pro\nBrand:  Acme\nModel No: KX - 200 \nGTIN: 0 36000 29145 2\nSold by Shop \u201cOne\u201d"


def test_quote_ok_normalisation():
    assert v.quote_ok("model no: kx - 200", PAGE)             # case-insensitive
    assert v.quote_ok("Brand: Acme", PAGE)                   # whitespace collapsed (double space on page)
    assert v.quote_ok('Sold by Shop "One"', PAGE)            # curly vs straight quotes
    assert not v.quote_ok("Model No: KX-200", PAGE)          # spacing differs inside the quote: not verbatim
    assert not v.quote_ok("Model: ZZ-1", PAGE)


def test_quote_min_length():
    assert not v.quote_ok("Acm", PAGE)
    assert v.quote_ok("Acme", PAGE)
    assert not v.quote_ok("    ", PAGE)


def test_value_must_be_inside_quote():
    assert v.check_quoted(Quoted(value="KX - 200", evidence_quote="Model No: KX - 200"), PAGE)[0]
    assert v.check_quoted(Quoted(value="kx200", evidence_quote="Model No: KX - 200"), PAGE)[0]   # canon match
    ok, why = v.check_quoted(Quoted(value="ZZ999", evidence_quote="Model No: KX - 200"), PAGE)
    assert not ok and why == "value_not_in_quote"
    ok, why = v.check_quoted(Quoted(value="ZZ999", evidence_quote="Model No: ZZ999"), PAGE)
    assert not ok and why == "quote_not_in_page"
    assert not v.check_quoted(Quoted(value="", evidence_quote="Brand: Acme"), PAGE)[0]


def _listing(**kw):
    return ExtractedListing(listing_id="l01", source_url="http://x/l01.html", **kw)


def test_apply_verification_drops_and_flags():
    l = _listing(
        brand=Quoted(value="Acme", evidence_quote="Brand: Acme"),
        model_numbers=[Quoted(value="KX - 200", evidence_quote="Model No: KX - 200"),
                       Quoted(value="MADE-UP", evidence_quote="Model: MADE-UP")],
        gtins=[Quoted(value="0 36000 29145 2", evidence_quote="GTIN: 0 36000 29145 2")])
    out, dropped = v.apply_verification_report(l, PAGE)
    assert out.brand.verified and out.brand.evidence_id
    assert [m.value for m in out.model_numbers] == ["KX - 200"]
    assert out.gtins[0].verified
    assert [(d.field, d.value) for d in dropped] == [("model_numbers", "MADE-UP")]
    assert v.apply_verification(l, PAGE) == out


def test_incoming_verified_flag_is_ignored():
    l = _listing(model_numbers=[Quoted(value="MADE-UP", evidence_quote="Model: MADE-UP", verified=True)])
    assert v.apply_verification(l, PAGE).model_numbers == []


def test_evidence_id_stable_and_url_scoped():
    a = v.evidence_id("http://x", "Brand:  Acme")
    assert a == v.evidence_id("http://x", "brand: acme")
    assert a != v.evidence_id("http://y", "brand: acme")
