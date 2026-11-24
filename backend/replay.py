"""
Replay engine — streams stored events with compressed timing.
Owned by M3.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from contracts.models import Event
from backend import store


async def replay_events(
    run_id: str,
    speed: float = 10.0,
) -> list[Event]:
    """
    Load stored events and yield them with compressed inter-event delays.

    speed: multiplier — 10.0 means 10x faster than real timing.
    Returns the full list of events (useful for testing).
    """
    events = store.load_events(run_id)
    return events


async def stream_replay(
    run_id: str,
    speed: float = 10.0,
):
    """
    Async generator that yields stored events with compressed timing.
    Used by the SSE endpoint.
    """
    events = store.load_events(run_id)
    if not events:
        return

    prev_ts = events[0].timestamp
    for event in events:
        # Compute delay since previous event
        delta = (event.timestamp - prev_ts).total_seconds()
        if delta > 0 and speed > 0:
            await asyncio.sleep(delta / speed)
        prev_ts = event.timestamp

        # Mark as recorded
        event.payload["_replayed"] = True
        yield event


def list_replays() -> list[dict]:
    """List all runs that have stored events (available for replay)."""
    runs = store.list_runs()
    result = []
    for run_id in runs:
        meta = store.load_meta(run_id)
        events = store.load_events(run_id)
        result.append({
            "id": run_id,
            "run_id": run_id,
            "event_count": len(events),
            "meta": meta or {},
        })
    return result
