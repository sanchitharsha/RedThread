"""
Tests for sponsor integrations: ElevenLabs voice briefing & AWS S3 archival.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import elevenlabs_tts, aws_archive
from contracts.models import (
    ReportJSON,
    RecallRecord,
    ReportListingRow,
    SourceChecked,
    Tier,
    ReasonCode,
)


@pytest.fixture
def sample_report() -> ReportJSON:
    return ReportJSON(
        run_id="test-run-123",
        recall_number="26419",
        recall_title="Test Recalled Product",
        mode="live",
        tier_counts={"CONFIRMED": 1, "LIKELY": 1, "NO_MATCH": 3, "UNRESOLVED": 0, "RELATED": 0, "CONFLICT": 0},
        listings=[
            ReportListingRow(
                listing_id="L01",
                url="http://localhost:8001/l01.html",
                title="Dangerous Item Model AAA",
                best_tier=Tier.CONFIRMED,
                reasons=[ReasonCode.ID_MODEL_EXACT],
                evidence_ids=["ev-1"],
            )
        ],
        conflicts=[],
        unresolved=[],
        coverage=[
            SourceChecked(source="CPSC", status="checked"),
        ],
    )


def test_elevenlabs_script_generation(sample_report):
    script = elevenlabs_tts._build_script(sample_report)
    assert "26419" in script
    assert "Test Recalled Product" in script
    assert "1 confirmed" in script
    assert "Dangerous Item Model AAA" in script


@pytest.mark.asyncio
async def test_elevenlabs_offline_narrate(sample_report):
    script = await elevenlabs_tts.narrate_report_offline(sample_report)
    assert len(script) > 50
    assert "Redthread Exposure Report Briefing" in script


def test_aws_offline_archival():
    manifest = aws_archive.archive_run_offline("demo_run")
    assert manifest["run_id"] == "demo_run"
    assert manifest["file_count"] > 0
    assert any("events.jsonl" in k for k in manifest["keys"])
    assert any("graph.json" in k for k in manifest["keys"])
    assert any("report.json" in k for k in manifest["keys"])


def test_sponsors_status_endpoint():
    client = TestClient(app)
    res = client.get("/api/sponsors/status")
    assert res.status_code == 200
    data = res.json()
    assert "elevenlabs" in data
    assert "aws" in data
    assert "configured" in data["elevenlabs"]
    assert "configured" in data["aws"]


def test_sponsors_narrate_endpoint():
    client = TestClient(app)
    res = client.post("/api/investigations/demo_run/narrate")
    assert res.status_code == 200
    data = res.json()
    assert data.get("fallback") is True
    assert "script" in data
    assert len(data["script"]) > 0


def test_sponsors_archive_endpoint():
    client = TestClient(app)
    res = client.post("/api/investigations/demo_run/archive")
    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == "demo_run"
    assert "keys" in data
    assert data["file_count"] > 0
