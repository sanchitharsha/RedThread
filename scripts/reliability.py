"""10-run reliability benchmark for Redthread M1 discover_and_inspect.

Runs `discover_and_inspect` 10 times against the sandbox shop (default
http://localhost:8001) using M2's `matching.llm.get_llm()` and prints a
pass/fail table with failure causes.

Success criterion per run: captures collected for at least 8 of the 10
sandbox listings (L01..L10).

Usage:
    python scripts/reliability.py
    python scripts/reliability.py --url http://localhost:8001 --runs 10 --brand ... --model ...
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

# Ensure repo root is importable when invoked as `python scripts/reliability.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent._contracts import PageCapture  # noqa: E402
from agent.agent import investigate  # noqa: E402
from agent.demo import _build_task, _load_real_llm  # noqa: E402

EXPECTED_LISTING_IDS: tuple[str, ...] = tuple(f"L{i:02d}" for i in range(1, 11))
LISTING_ID_RE = re.compile(r"\b(L(?:0[1-9]|10))\b", re.IGNORECASE)
SUCCESS_MIN_LISTINGS = 8


@dataclass
class RunResult:
    run_number: int
    run_id: str
    captured_ids: list[str]
    missing_ids: list[str]
    total_captures: int
    steps_taken: int
    duration_s: float
    passed: bool
    cause: str


def extract_sandbox_listing_ids(captures: list[PageCapture]) -> list[str]:
    """Identify which sandbox listing IDs (L01..L10) are represented in captures."""
    found: set[str] = set()
    for cap in captures:
        url_matches = LISTING_ID_RE.findall(cap.url or "")
        for m in url_matches:
            found.add(m.upper())
        if not url_matches:
            title_matches = LISTING_ID_RE.findall(cap.title or "")
            for m in title_matches:
                found.add(m.upper())
    return sorted(found)


async def run_single_trial(
    run_number: int,
    *,
    url: str,
    allow_domains: list[str],
    brand: str | None,
    models: list[str],
    product_name: str | None,
    query_terms: list[str],
    max_steps: int,
    max_pages: int,
    llm: Any,
) -> RunResult:
    run_id = f"rel_{run_number:02d}_{uuid.uuid4().hex[:6]}"
    task = _build_task(
        run_id=run_id,
        playbook="discover_and_inspect",
        start_url=url,
        allow_domains=allow_domains,
        brand=brand,
        models=models,
        product_name=product_name,
        query_terms=query_terms,
        max_steps=max_steps,
        max_pages=max_pages,
    )

    steps_taken = 0
    guard_blocks = 0
    loop_detected = False
    llm_errors = 0

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        nonlocal steps_taken, guard_blocks, loop_detected, llm_errors
        if event_type == "step_started":
            steps_taken = max(steps_taken, int(payload.get("step") or 0))
        elif event_type == "tool_call":
            if payload.get("blocked_by_guard"):
                guard_blocks += 1
            if payload.get("loop_detected"):
                loop_detected = True
            if payload.get("tool") == "llm_error":
                llm_errors += 1

    started = time.monotonic()
    error_cause: str | None = None
    captures: list[PageCapture] = []
    try:
        captures = await investigate(task, emit, llm)
    except Exception as exc:
        error_cause = f"exception: {type(exc).__name__}: {exc}"
    duration_s = time.monotonic() - started

    captured_ids = extract_sandbox_listing_ids(captures)
    missing_ids = [lid for lid in EXPECTED_LISTING_IDS if lid not in captured_ids]
    passed = error_cause is None and len(captured_ids) >= SUCCESS_MIN_LISTINGS

    if passed:
        cause = "ok"
    elif error_cause:
        cause = error_cause
    else:
        reasons: list[str] = []
        if llm_errors:
            reasons.append(f"llm_errors={llm_errors}")
        if loop_detected:
            reasons.append("loop_detected")
        if duration_s >= 179.0:
            reasons.append("wall_clock_timeout")
        if steps_taken >= max_steps:
            reasons.append(f"step_budget_exhausted({max_steps})")
        if guard_blocks:
            reasons.append(f"guard_blocks={guard_blocks}")
        if not reasons:
            reasons.append(f"early_finish_missing({','.join(missing_ids)})")
        cause = "; ".join(reasons)

    return RunResult(
        run_number=run_number,
        run_id=run_id,
        captured_ids=captured_ids,
        missing_ids=missing_ids,
        total_captures=len(captures),
        steps_taken=steps_taken,
        duration_s=duration_s,
        passed=passed,
        cause=cause,
    )


def format_results_table(results: list[RunResult]) -> str:
    header = (
        f"{'Run':>3} | {'Result':<6} | {'Listings':>8} | {'Steps':>5} | "
        f"{'Time(s)':>7} | {'Missing':<24} | Cause"
    )
    sep = "-" * len(header) + "-" * 24
    lines = [header, sep]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        missing_str = ",".join(r.missing_ids) if r.missing_ids else "-"
        if len(missing_str) > 24:
            missing_str = missing_str[:21] + "..."
        lines.append(
            f"{r.run_number:>3} | {status:<6} | {len(r.captured_ids):>2}/10    | "
            f"{r.steps_taken:>5} | {r.duration_s:>7.1f} | {missing_str:<24} | {r.cause}"
        )
    passed_count = sum(1 for r in results if r.passed)
    lines.append(sep)
    lines.append(
        f"Summary: {passed_count}/{len(results)} runs passed "
        f"(pass threshold: >= {SUCCESS_MIN_LISTINGS}/10 sandbox listings captured)."
    )
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Redthread M1 discover_and_inspect N times against the sandbox."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Sandbox shop start URL (default: http://localhost:8001).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of trials to execute (default: 10).",
    )
    parser.add_argument("--brand", default=None, help="Target recalled brand.")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Target recalled model (repeatable).",
    )
    parser.add_argument("--product", default=None, help="Target product name.")
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Additional query terms (repeatable).",
    )
    parser.add_argument("--max-steps", type=int, default=45, help="Max steps per run.")
    parser.add_argument("--max-pages", type=int, default=20, help="Max pages per run.")
    return parser.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    parsed = urlparse(args.url)
    if not parsed.hostname:
        raise ValueError(f"Invalid URL: {args.url!r}")
    allow_domain = parsed.netloc if parsed.port else parsed.hostname

    query_terms = list(args.query)
    for item in [args.brand, *args.model, args.product]:
        if item and item not in query_terms:
            query_terms.append(item)

    llm = _load_real_llm()
    results: list[RunResult] = []
    for i in range(1, args.runs + 1):
        print(f"Running trial {i}/{args.runs} against {args.url} ...", flush=True)
        res = await run_single_trial(
            i,
            url=args.url,
            allow_domains=[allow_domain],
            brand=args.brand,
            models=list(args.model),
            product_name=args.product,
            query_terms=query_terms,
            max_steps=args.max_steps,
            max_pages=args.max_pages,
            llm=llm,
        )
        results.append(res)

    print()
    print(format_results_table(results))
    return 0 if all(r.passed for r in results) else 1


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
