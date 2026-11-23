import json
import shutil
from pathlib import Path

import httpx
import pytest

from matching.connectors import cpsc

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_offline_uses_placeholder_loudly(caplog):
    r = cpsc.fetch_recall("whatever")
    assert "PLACEHOLDER" in r.raw_ref and r.authority == "CPSC" and r.source_tier == "A"
    assert r.models == ["MODEL-AAA", "MODEL-BBB"] and r.gtins == ["000000000017"]
    assert r.scope_type == "all_units" and r.quotes["scope"].startswith("This recall involves all units")
    assert "NOT A REAL RECALL" in caplog.text


def test_offline_never_touches_network(monkeypatch):
    monkeypatch.setattr(cpsc, "http_get_json", lambda p: (_ for _ in ()).throw(AssertionError("network used")))
    cpsc.fetch_recall("x")


def test_network_failure_falls_back(monkeypatch):
    monkeypatch.setenv("OFFLINE", "0")
    monkeypatch.setattr(cpsc, "http_get_json", lambda p: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert "PLACEHOLDER" in cpsc.fetch_recall("CPSC:24-123").raw_ref


def test_online_tries_spellings_and_saves_raw(monkeypatch, tmp_path):
    shutil.copy(FIX / "cpsc_sample.PLACEHOLDER.json", tmp_path / "src.json")
    data = json.loads((tmp_path / "src.json").read_text())
    data[0]["RecallNumber"] = "24-123"
    monkeypatch.setenv("OFFLINE", "0")
    monkeypatch.setenv("FIXTURES_DIR", str(tmp_path))
    tried = []

    def fake_get(params):
        tried.append(params)
        if "RecallNumber" in params and params["RecallNumber"] == "24123":     # only this spelling "works"
            return data
        raise httpx.HTTPStatusError("400", request=None, response=None)
    monkeypatch.setattr(cpsc, "http_get_json", fake_get)
    r = cpsc.fetch_recall("CPSC:24-123")
    assert r.number == "24-123" and r.raw_ref == str(tmp_path / "cpsc_raw_24-123.json")
    assert (tmp_path / "cpsc_raw_24-123.json").exists()
    assert tried[0] == {"RecallNumber": "24-123"} and {"RecallNumber": "24123"} in tried


def test_map_record_is_tolerant_and_case_insensitive():
    r = cpsc.map_record({"recallnumber": "9", "TITLE": "T", "products": [{"model": "Model No. AB-12; CD-34 and EF"}],
                         "ProductUPCs": [{"UPC": "0 36000 29145 2"}, {"UPC": "see label"}]})
    assert r.number == "9" and r.models == ["AB-12", "CD-34"]            # 'EF' too short to be an identifier
    assert r.gtins == ["036000291452", "see label"] and r.brand is None
    assert r.url.startswith("https://www.saferproducts.gov/") and r.scope_type == "unknown"


def test_scope_ignores_sale_dates_but_accepts_manufacture_dates():
    sold = "Sold at Big Store from January 2021 through March 2022. Units are recalled."
    assert cpsc._scope_from_description(sold)[0] == "unknown"
    made = "Units manufactured between March 2020 and June 2021 are affected. Sold from 2019 to 2022."
    t, f, to, text = cpsc._scope_from_description(made)
    assert (t, f, to) == ("range", "2020-03-01", "2021-06-30") and text.startswith("Units manufactured")
    assert cpsc._scope_from_description("All units are recalled.")[0] == "all_units"


def test_split_models_never_mangles_identifiers():
    assert cpsc._split_models("MODEL-AAA, MODEL-BBB") == ["MODEL-AAA", "MODEL-BBB"]
    assert cpsc._split_models("Model: KX-200; Models # KX-300") == ["KX-200", "KX-300"]
    assert cpsc._split_models("Model AB-12") == ["Model AB-12"]          # unlabelled form kept whole (conservative)
