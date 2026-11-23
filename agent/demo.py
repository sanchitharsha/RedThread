"""CLI demo for M1's Redthread browser agent.

Usage:
    python -m agent.demo http://localhost:8001
    python -m agent.demo http://localhost:8001 --brand BRAND-PLACEHOLDER --model MODEL-AAA
    python -m agent.demo http://localhost:8001 --fake
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from agent._contracts import InvestigationTask, PageCapture
from agent.agent import investigate
from agent.fake_llm import FakeLLM


def _build_task(
    *,
    run_id: str,
    playbook: str,
    start_url: str,
    allow_domains: list[str],
    brand: str | None,
    models: list[str],
    product_name: str | None,
    query_terms: list[str],
    max_steps: int,
    max_pages: int,
) -> InvestigationTask:
    """Construct an InvestigationTask compatible with both stub and M3 schemas."""
    fields = getattr(InvestigationTask, "model_fields", {})
    goal_parts = []
    if brand:
        goal_parts.append(f"brand={brand}")
    if models:
        goal_parts.append(f"models={', '.join(models)}")
    if product_name:
        goal_parts.append(f"product={product_name}")
    goal = (
        f"Investigate listings on {start_url}"
        + (f" ({'; '.join(goal_parts)})" if goal_parts else "")
    )
    candidates: dict[str, Any] = {
        "run_id": run_id,
        "playbook": playbook,
        "mode": playbook,
        "task_type": playbook,
        "start_url": start_url,
        "start_urls": [start_url],
        "allow_domains": allow_domains,
        "goal": goal,
        "query_terms": query_terms,
        "brand": brand,
        "models": models,
        "product_name": product_name,
        "max_steps": max_steps,
        "max_pages": max_pages,
        "timeout_seconds": 180,
    }
    if not fields:
        return InvestigationTask(
            run_id=run_id,
            playbook=playbook,  # type: ignore[arg-type]
            start_url=start_url,
            allow_domains=allow_domains,
            goal=goal,
            query_terms=query_terms,
            brand=brand,
            models=models,
            product_name=product_name,
            max_steps=max_steps,
            max_pages=max_pages,
        )
    kwargs = {k: v for k, v in candidates.items() if k in fields}
    return InvestigationTask(**kwargs)


def _load_real_llm() -> Any:
    try:
        from matching.llm import get_llm  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "matching/llm.py (owned by M2) is not in this workspace yet. "
            "Add matching/llm.py with get_llm(), or pass --fake for an offline smoke run."
        ) from exc
    return get_llm()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agent.demo",
        description="Run Redthread M1 browser agent against a shop or recall URL.",
    )
    parser.add_argument(
        "url",
        help="Start URL to investigate (e.g. http://localhost:8001).",
    )
    parser.add_argument(
        "--playbook",
        choices=["discover_and_inspect", "harvest_notice"],
        default="discover_and_inspect",
        help="Agent playbook to execute (default: discover_and_inspect).",
    )
    parser.add_argument("--brand", default=None, help="Target recalled brand name.")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Target recalled model number (repeatable).",
    )
    parser.add_argument("--product", default=None, help="Target product name.")
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Additional search query term (repeatable).",
    )
    parser.add_argument("--max-steps", type=int, default=30, help="Max agent steps.")
    parser.add_argument("--max-pages", type=int, default=15, help="Max unique pages.")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier for runs/<run_id>/shots/ (default: generated).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch Chromium visibly instead of headless mode.",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use offline FakeLLM (reads start page and finishes) instead of matching.llm.get_llm().",
    )
    return parser.parse_args(argv)


async def _run_demo(args: argparse.Namespace) -> list[PageCapture]:
    if args.headed:
        os.environ["REDTHREAD_HEADLESS"] = "false"

    parsed = urlparse(args.url)
    if not parsed.hostname:
        raise ValueError(f"Invalid URL: {args.url!r}")
    allow_domain = parsed.netloc if parsed.port else parsed.hostname
    run_id = args.run_id or f"demo_{uuid.uuid4().hex[:8]}"

    query_terms = list(args.query)
    for item in [args.brand, *args.model, args.product]:
        if item and item not in query_terms:
            query_terms.append(item)

    task = _build_task(
        run_id=run_id,
        playbook=args.playbook,
        start_url=args.url,
        allow_domains=[allow_domain],
        brand=args.brand,
        models=list(args.model),
        product_name=args.product,
        query_terms=query_terms,
        max_steps=args.max_steps,
        max_pages=args.max_pages,
    )

    if args.fake:
        llm: Any = FakeLLM(
            actions=[
                {
                    "name": "read_page",
                    "args": {},
                    "reason": "Capture initial page content in offline FakeLLM mode.",
                },
                {
                    "name": "finish",
                    "args": {"findings": f"Offline smoke capture of {args.url}."},
                    "reason": "Completed offline FakeLLM demo sequence.",
                },
            ]
        )
    else:
        llm = _load_real_llm()

    print(f"=== Redthread M1 Browser Agent Demo (run_id={run_id}) ===")
    print(f"Start URL     : {args.url}")
    print(f"Allowlist     : {[allow_domain]}")
    print(f"Playbook      : {args.playbook}")
    print(f"Budgets       : max_steps={args.max_steps}, max_pages={args.max_pages}")
    print()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        step = payload.get("step", "-")
        if event_type == "step_started":
            print(f"[step {step}] START  url={payload.get('url')}")
        elif event_type == "tool_call":
            allowed = payload.get("allowed", True)
            status_tag = "EXEC" if allowed else "DENY"
            print(
                f"[step {step}] {status_tag}   tool={payload.get('tool')} "
                f"args={payload.get('args')} | reason={payload.get('reason')}"
            )
            if payload.get("error"):
                print(f"           note: {payload.get('error')}")
        elif event_type == "page_visited":
            blk = (
                f" block_reason={payload.get('block_reason')}"
                if payload.get("block_reason")
                else ""
            )
            print(
                f"[step {step}] VISIT  url={payload.get('url')} "
                f"status={payload.get('status')}{blk} shot={payload.get('screenshot_path')}"
            )
        else:
            print(f"[step {step}] {event_type.upper()} {payload}")

    captures = await investigate(task, emit, llm)

    print()
    print(f"=== Collected PageCaptures ({len(captures)}) ===")
    for idx, cap in enumerate(captures, start=1):
        print(
            f"{idx:2d}. [{cap.status.upper()} | tier={cap.source_tier}] {cap.url}\n"
            f"    title      : {cap.title}\n"
            f"    text_chars : {len(cap.text)}\n"
            f"    screenshot : {cap.screenshot_path}\n"
            f"    fetched_at : {cap.fetched_at}"
        )
        if cap.block_reason:
            print(f"    block      : {cap.block_reason}")
    return captures


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse_args(argv)
    try:
        asyncio.run(_run_demo(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
