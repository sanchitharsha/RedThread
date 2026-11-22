#!/usr/bin/env python3
"""
Smoke test for Redthread.

USE_STUBS=1 must be set. Starts a run via the backend API, reads the SSE
stream to completion, and asserts:
  - run_finished event received
  - graph is non-empty
  - every MATCHES edge has evidence
  - report has all tier keys
  - at least one match_result event

Exit non-zero on any failure.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import httpx

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")
RECALL_REF = "PLACEHOLDER-RECALL-000"


async def main() -> int:
    errors: list[str] = []

    async with httpx.AsyncClient(base_url=BACKEND, timeout=60.0) as client:
        # 1. Health check
        r = await client.get("/api/health")
        if r.status_code != 200:
            print(f"FAIL: /api/health returned {r.status_code}")
            return 1
        print("✓ Health OK")

        # 2. Start investigation
        r = await client.post("/api/investigations", json={
            "recall_ref": RECALL_REF,
        })
        if r.status_code != 200:
            print(f"FAIL: POST /api/investigations returned {r.status_code}: {r.text}")
            return 1

        run_id = r.json()["run_id"]
        print(f"✓ Investigation started: {run_id}")

        # 3. Read SSE stream to completion
        events: list[dict] = []
        event_types_seen: set[str] = set()
        got_finished = False

        async with client.stream("GET", f"/api/investigations/{run_id}/events") as stream:
            buffer = ""
            async for chunk in stream.aiter_text():
                buffer += chunk.replace("\r\n", "\n")
                while "\n\n" in buffer:
                    msg, buffer = buffer.split("\n\n", 1)
                    for line in msg.strip().splitlines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str:
                                continue
                            try:
                                event = json.loads(data_str)
                                events.append(event)
                                event_types_seen.add(event.get("type", ""))
                                print(f"  event #{event.get('seq', '?')}: {event.get('type', '?')}", flush=True)
                                if event.get("type") == "run_finished":
                                    got_finished = True
                            except json.JSONDecodeError:
                                pass
                    if got_finished:
                        break
                if got_finished:
                    break

        print(f"✓ Received {len(events)} events")
        print(f"  Types seen: {sorted(event_types_seen)}")

        if not got_finished:
            errors.append("run_finished event not received")

        if "match_result" not in event_types_seen:
            errors.append("No match_result events received")

        # 4. Wait a moment for files to be written
        await asyncio.sleep(1)

        # 5. Check graph
        r = await client.get(f"/api/investigations/{run_id}/graph")
        if r.status_code != 200:
            errors.append(f"Graph endpoint returned {r.status_code}")
        else:
            graph = r.json()
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            if not nodes:
                errors.append("Graph has no nodes")
            if not edges:
                errors.append("Graph has no edges")

            # Check MATCHES edges have evidence
            for edge in edges:
                if edge.get("kind") == "MATCHES":
                    if not edge.get("evidence_ids"):
                        errors.append(f"MATCHES edge {edge.get('id')} has no evidence")
            print(f"✓ Graph: {len(nodes)} nodes, {len(edges)} edges")

        # 6. Check report
        r = await client.get(f"/api/investigations/{run_id}/report")
        if r.status_code != 200:
            errors.append(f"Report endpoint returned {r.status_code}")
        else:
            report = r.json()
            tier_counts = report.get("tier_counts", {})
            expected_tiers = {"CONFIRMED", "LIKELY", "RELATED", "CONFLICT", "NO_MATCH", "UNRESOLVED"}
            missing_tiers = expected_tiers - set(tier_counts.keys())
            if missing_tiers:
                errors.append(f"Report missing tier keys: {missing_tiers}")
            if report.get("disclaimer", "") == "":
                errors.append("Report missing disclaimer")
            print(f"✓ Report: tiers={tier_counts}")

        # 7. Check export
        r = await client.get(f"/api/investigations/{run_id}/export.json")
        if r.status_code != 200:
            errors.append(f"Export endpoint returned {r.status_code}")
        else:
            print("✓ Export OK")

    # Summary
    if errors:
        print(f"\n✗ SMOKE TEST FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("\n✓ SMOKE TEST PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
