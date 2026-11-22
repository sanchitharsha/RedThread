"""
Stub browser agent — returns fixture data when USE_STUBS=1.
M1 replaces this file with the real browser agent.
Signature MUST stay: async def investigate(task, emit, llm) -> list[PageCapture]
"""
from __future__ import annotations

import os
from datetime import datetime

from contracts.models import (
    InvestigationTask,
    PageCapture,
    Emit,
    LLM,
    EventType,
    TaskKind,
)


async def investigate(
    task: InvestigationTask, emit: Emit, llm: LLM
) -> list[PageCapture]:
    """
    Stub: returns synthetic PageCapture objects.
    When USE_STUBS != 1, this file should not be called (M1 provides the real one).
    """
    await emit(EventType.STEP_STARTED.value, {
        "step": "investigate",
        "kind": task.kind.value,
        "target_url": task.target_url,
    })

    if task.kind == TaskKind.HARVEST_NOTICE:
        # Return a single capture of the recall notice page
        captures = [
            PageCapture(
                url=task.target_url,
                final_url=task.target_url,
                title="PLACEHOLDER Recall Notice Page",
                text=(
                    "PLACEHOLDER RECALL NOTICE. Brand: PLACEHOLDER-BRAND. "
                    "Model: MODEL-AAA. GTIN: 0000000000000. "
                    "Hazard: PLACEHOLDER hazard description. "
                    "Remedy: PLACEHOLDER remedy description. "
                    "Units: PLACEHOLDER units affected."
                ),
                captured_at=datetime.utcnow(),
                source_tier="A",
            ),
        ]
    else:
        # discover_and_inspect: return fake listing captures
        captures = []
        for i, suffix in enumerate(["L01", "L02", "L03"], start=1):
            cap = PageCapture(
                url=f"{task.target_url}/product/{suffix}",
                final_url=f"{task.target_url}/product/{suffix}",
                title=f"PLACEHOLDER Product {suffix}",
                text=(
                    f"PLACEHOLDER listing {suffix}. "
                    f"Brand: PLACEHOLDER-BRAND. Model: MODEL-AAA. "
                    f"GTIN: 0000000000000. Price: $PLACEHOLDER."
                ),
                captured_at=datetime.utcnow(),
                source_tier="C",
            )
            captures.append(cap)

            await emit(EventType.PAGE_VISITED.value, {
                "url": cap.url,
                "title": cap.title,
                "seq": i,
            })

    return captures
