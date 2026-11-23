"""
Simple persistence layer using JSON files under runs/<run_id>/.
Owned by M3.

Storage layout:
  runs/<run_id>/events.jsonl   — one Event JSON per line
  runs/<run_id>/meta.json      — run metadata (recall_ref, shop_url, status)
  runs/<run_id>/results.json   — list of MatchResult dicts
  runs/<run_id>/captures.json  — list of PageCapture dicts
  runs/<run_id>/graph.json     — GraphJSON
  runs/<run_id>/report.json    — ReportJSON
  runs/<run_id>/evidence/      — Evidence objects keyed by evidence_id
  runs/<run_id>/shots/         — screenshots
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from contracts.models import (
    Event,
    Evidence,
    GraphJSON,
    MatchResult,
    PageCapture,
    ReportJSON,
)

RUNS_DIR = Path(os.environ.get("RUNS_DIR", "runs"))


def _run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- Metadata ----

def save_meta(run_id: str, meta: dict[str, Any]) -> None:
    p = _run_dir(run_id) / "meta.json"
    p.write_text(json.dumps(meta, default=str, indent=2))


def load_meta(run_id: str) -> dict[str, Any] | None:
    p = _run_dir(run_id) / "meta.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


# ---- Events ----

def append_event(run_id: str, event: Event) -> None:
    """Append a single event to the JSONL file."""
    p = _run_dir(run_id) / "events.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")


def load_events(run_id: str) -> list[Event]:
    """Load all events for a run."""
    p = _run_dir(run_id) / "events.jsonl"
    if not p.exists():
        return []
    events = []
    for line in p.read_text(encoding="utf-8").strip().splitlines():
        if line.strip():
            events.append(Event.model_validate_json(line))
    return events


# ---- Evidence ----

def save_evidence(run_id: str, ev: Evidence) -> None:
    d = _run_dir(run_id) / "evidence"
    d.mkdir(exist_ok=True)
    eid = ev.id or ev.evidence_id
    p = d / f"{eid}.json"
    p.write_text(ev.model_dump_json(indent=2))


def load_evidence(run_id: str, evidence_id: str) -> Evidence | None:
    p = _run_dir(run_id) / "evidence" / f"{evidence_id}.json"
    if p.exists():
        return Evidence.model_validate_json(p.read_text())
    return None


def load_all_evidence(run_id: str) -> dict[str, Evidence]:
    """Load all evidence for a run, keyed by evidence_id."""
    d = _run_dir(run_id) / "evidence"
    if not d.exists():
        return {}
    result = {}
    for p in d.glob("*.json"):
        ev = Evidence.model_validate_json(p.read_text())
        result[ev.evidence_id] = ev
    return result


# ---- MatchResults ----

def save_results(run_id: str, results: list[MatchResult]) -> None:
    p = _run_dir(run_id) / "results.json"
    p.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2, default=str))


def load_results(run_id: str) -> list[MatchResult]:
    p = _run_dir(run_id) / "results.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    return [MatchResult.model_validate(r) for r in raw]


# ---- PageCaptures ----

def save_captures(run_id: str, captures: list[PageCapture]) -> None:
    p = _run_dir(run_id) / "captures.json"
    p.write_text(json.dumps([c.model_dump(mode="json") for c in captures], indent=2, default=str))


def load_captures(run_id: str) -> list[PageCapture]:
    p = _run_dir(run_id) / "captures.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    return [PageCapture.model_validate(c) for c in raw]


# ---- Graph ----

def save_graph(run_id: str, graph: GraphJSON) -> None:
    p = _run_dir(run_id) / "graph.json"
    p.write_text(graph.model_dump_json(indent=2))


def load_graph(run_id: str) -> GraphJSON | None:
    p = _run_dir(run_id) / "graph.json"
    if p.exists():
        return GraphJSON.model_validate_json(p.read_text())
    return None


# ---- Report ----

def save_report(run_id: str, report: ReportJSON) -> None:
    p = _run_dir(run_id) / "report.json"
    p.write_text(report.model_dump_json(indent=2))


def load_report(run_id: str) -> ReportJSON | None:
    p = _run_dir(run_id) / "report.json"
    if p.exists():
        return ReportJSON.model_validate_json(p.read_text())
    return None


# ---- Run listing ----

def list_runs() -> list[str]:
    """List all run_ids that have an events.jsonl file."""
    if not RUNS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in RUNS_DIR.iterdir()
        if d.is_dir() and (d / "events.jsonl").exists()
    )


def run_exists(run_id: str) -> bool:
    return (_run_dir(run_id) / "events.jsonl").exists() or (_run_dir(run_id) / "meta.json").exists()
