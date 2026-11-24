"""
FastAPI backend for Redthread.
Owned by M3.

Endpoints:
  POST /api/investigations           — start a new investigation
  GET  /api/investigations/{id}/events — SSE stream of events
  GET  /api/investigations/{id}/graph  — current GraphJSON
  GET  /api/investigations/{id}/report — ReportJSON
  GET  /api/evidence/{evidence_id}     — single Evidence object
  GET  /api/investigations/{id}/export.json — full export
  GET  /api/replays                    — list recorded runs
  GET  /api/health                     — health check
  /shots/...                           — static screenshots
"""
from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from contracts.models import Event, EventType
from backend import store
from backend import elevenlabs_tts, aws_archive
from backend.orchestrator import run_investigation
from backend.replay import stream_replay, list_replays


# ---- Active runs: run_id -> asyncio.Queue for live SSE ----
_live_queues: dict[str, list[asyncio.Queue]] = {}
_running_tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    # Ensure runs directory exists
    store.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Cancel any running investigations
    for task in _running_tasks.values():
        task.cancel()


app = FastAPI(
    title="Redthread API",
    description="Product safety recall investigation engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve screenshots
shots_dir = Path(os.environ.get("RUNS_DIR", "runs"))
if shots_dir.exists():
    app.mount("/shots", StaticFiles(directory=str(shots_dir)), name="shots")


# ---- Request/Response models ----

class InvestigationRequest(BaseModel):
    recall_ref: str
    shop_url: str | None = None
    replay_id: str | None = None


class InvestigationResponse(BaseModel):
    run_id: str


# ---- Endpoints ----

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/investigations", response_model=InvestigationResponse)
async def create_investigation(req: InvestigationRequest):
    """Start a new investigation or replay a recorded one."""

    if req.replay_id:
        # Replay mode — just return the existing run_id
        if not store.run_exists(req.replay_id):
            raise HTTPException(404, f"Replay run '{req.replay_id}' not found")
        return InvestigationResponse(run_id=req.replay_id)

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    shop_url = req.shop_url or os.environ.get("SHOP_URL", "http://localhost:8001")

    # Create SSE queue list for this run
    _live_queues[run_id] = []

    async def emit(event_type: str, payload: dict) -> None:
        """Broadcast events to all SSE subscribers."""
        event = Event(
            run_id=run_id,
            seq=0,  # store.append_event sets real seq
            type=event_type,
            payload=payload,
        )
        for q in _live_queues.get(run_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop if consumer is too slow

    # Launch investigation in background
    task = asyncio.create_task(
        run_investigation(run_id, req.recall_ref, shop_url, emit)
    )
    _running_tasks[run_id] = task

    # Clean up when done
    def _cleanup(t: asyncio.Task):
        _running_tasks.pop(run_id, None)
        # Don't remove queues immediately — SSE clients may still be reading

    task.add_done_callback(_cleanup)

    return InvestigationResponse(run_id=run_id)


@app.get("/api/investigations/{run_id}/events")
async def investigation_events(run_id: str, request: Request, speed: float = 10.0):
    """
    SSE stream of investigation events.
    - For live runs: replays stored events then streams new ones.
    - For recorded runs (replay): streams with compressed timing.
    """

    async def event_generator():
        # Check if this is a replay of a completed run
        meta = store.load_meta(run_id)
        is_finished = meta and meta.get("status") in ("finished", "error")

        if is_finished and run_id not in _live_queues:
            # Pure replay mode
            async for event in stream_replay(run_id, speed=speed):
                if await request.is_disconnected():
                    return
                yield {
                    "event": "message",
                    "data": event.model_dump_json(),
                }
            return

        # Live mode (or mixed: replay stored + stream new)
        # First, replay any stored events
        stored = store.load_events(run_id)
        has_finished_event = False
        for event in stored:
            if await request.is_disconnected():
                return
            yield {
                "event": "message",
                "data": event.model_dump_json(),
            }
            if event.type in (EventType.RUN_FINISHED.value, EventType.RUN_ERROR.value):
                has_finished_event = True

        if has_finished_event or is_finished:
            return

        # Then stream new events via queue
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        queues = _live_queues.setdefault(run_id, [])
        queues.append(q)

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {
                        "event": "message",
                        "data": event.model_dump_json(),
                    }
                    # Stop after run_finished or run_error
                    if event.type in (EventType.RUN_FINISHED.value, EventType.RUN_ERROR.value):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            if q in queues:
                queues.remove(q)

    return EventSourceResponse(event_generator())


@app.get("/api/investigations/{run_id}/graph")
async def investigation_graph(run_id: str):
    graph = store.load_graph(run_id)
    if graph is None:
        raise HTTPException(404, "Graph not found (run may still be in progress)")
    return graph.model_dump(mode="json")


@app.get("/api/investigations/{run_id}/report")
async def investigation_report(run_id: str):
    report = store.load_report(run_id)
    if report is None:
        raise HTTPException(404, "Report not found (run may still be in progress)")
    return report.model_dump(mode="json")


@app.get("/api/evidence/{evidence_id}")
async def get_evidence(evidence_id: str):
    """Find evidence by id across all runs."""
    for run_id in store.list_runs():
        ev = store.load_evidence(run_id, evidence_id)
        if ev:
            return ev.model_dump(mode="json")
    raise HTTPException(404, f"Evidence '{evidence_id}' not found")


@app.get("/api/investigations/{run_id}/export.json")
async def export_investigation(run_id: str):
    """Full export of a run."""
    if not store.run_exists(run_id):
        raise HTTPException(404, "Run not found")

    events = store.load_events(run_id)
    graph = store.load_graph(run_id)
    report = store.load_report(run_id)
    meta = store.load_meta(run_id)

    return {
        "run_id": run_id,
        "meta": meta,
        "events": [e.model_dump(mode="json") for e in events],
        "graph": graph.model_dump(mode="json") if graph else None,
        "report": report.model_dump(mode="json") if report else None,
    }


@app.get("/api/replays")
async def replays():
    return list_replays()


# ---- Sponsor Prize Integrations: ElevenLabs & AWS ----

@app.get("/api/sponsors/status")
async def sponsors_status():
    """Return status of ElevenLabs and AWS sponsor integrations."""
    return {
        "elevenlabs": {
            "configured": elevenlabs_tts.is_configured(),
            "description": "ElevenLabs voice narration briefing for exposure reports",
        },
        "aws": {
            "configured": aws_archive.is_configured(),
            "description": "AWS S3 evidence archival for investigation artifacts",
        },
    }


@app.post("/api/investigations/{run_id}/narrate")
async def narrate_investigation(run_id: str):
    """
    Generate voice narration of the report using ElevenLabs.
    Returns MP3 audio if configured, or JSON fallback script if offline/unconfigured.
    """
    report = store.load_report(run_id)
    if report is None:
        raise HTTPException(404, "Report not found (investigation may still be running)")

    if elevenlabs_tts.is_configured():
        try:
            audio_bytes = await elevenlabs_tts.narrate_report(report)
            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={"Content-Disposition": f'attachment; filename="redthread-{run_id}-briefing.mp3"'},
            )
        except Exception as exc:
            script = await elevenlabs_tts.narrate_report_offline(report)
            return JSONResponse(
                {
                    "fallback": True,
                    "configured": True,
                    "error": str(exc),
                    "script": script,
                },
                status_code=200,
            )
    else:
        script = await elevenlabs_tts.narrate_report_offline(report)
        return JSONResponse(
            {
                "fallback": True,
                "configured": False,
                "message": "ELEVENLABS_API_KEY not configured. Previewing briefing script.",
                "script": script,
            },
            status_code=200,
        )


@app.post("/api/investigations/{run_id}/archive")
async def archive_investigation(run_id: str):
    """
    Archive investigation artifacts (events, graph, report, evidence) to AWS S3.
    Returns the archive manifest.
    """
    if not store.run_exists(run_id):
        raise HTTPException(404, "Run not found")

    if aws_archive.is_configured():
        try:
            manifest = aws_archive.archive_run(run_id)
            return JSONResponse(manifest)
        except Exception as exc:
            manifest = aws_archive.archive_run_offline(run_id)
            manifest["error"] = str(exc)
            return JSONResponse(manifest, status_code=200)
    else:
        manifest = aws_archive.archive_run_offline(run_id)
        manifest["message"] = "AWS credentials not configured. Generated offline archival manifest."
        return JSONResponse(manifest, status_code=200)

