"""LLM-driven browser investigation loop for Redthread (M1).

Exposes the shared contract entry point:
    async def investigate(task: InvestigationTask, emit: Emit, llm: LLM) -> list[PageCapture]
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from typing import Any
from urllib.parse import urljoin, urldefrag

from playwright.async_api import Locator, Page

from agent._contracts import Emit, InvestigationTask, LLM, PageCapture
from agent.browser import (
    BrowserSession,
    capture_page,
    detect_block,
    infer_source_tier,
    save_step_screenshot,
)
from agent.guard import GuardError, check_url, guard, is_search_box
from agent.observe import PageObservation, build_observation
from agent.playbooks import build_system_prompt, get_tool_schemas

MAX_WALL_CLOCK_SECONDS = 180.0
LOOP_REPEAT_THRESHOLD = 3
MAX_HISTORY_ITEMS = 30

_ELEMENT_META_JS = """
(el) => {
  const tag = (el.tagName || '').toLowerCase();
  const type = (el.getAttribute('type') || '').toLowerCase();
  const role = (el.getAttribute('role') || '').toLowerCase();
  const ariaLabel = el.getAttribute('aria-label') || '';
  const placeholder = el.getAttribute('placeholder') || '';
  const nameAttr = el.getAttribute('name') || '';
  const idAttr = el.getAttribute('id') || '';
  const value = el.getAttribute('value') || '';
  const text = (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 200);
  const href = tag === 'a' ? (el.href || el.getAttribute('href') || '') : '';
  return {
    tag,
    type,
    role,
    aria_label: ariaLabel,
    placeholder,
    name: ariaLabel || text || nameAttr || placeholder || value,
    id: idAttr,
    value,
    text,
    href,
  };
}
"""

_FIND_SEARCH_CANDIDATES_JS = """
() => {
  const isVisible = (el) => {
    const s = window.getComputedStyle(el);
    if (!s || s.display === 'none' || s.visibility === 'hidden') return false;
    if (parseFloat(s.opacity || '1') === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inputs = Array.from(document.querySelectorAll('input, [role="searchbox"]'));
  const results = [];
  let idx = 0;
  for (const el of inputs) {
    if (!isVisible(el)) continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'checkbox', 'radio', 'file', 'image'].includes(type)) {
      continue;
    }
    const marker = `rt-search-cand-${idx++}`;
    el.setAttribute('data-rt-search-cand', marker);
    const ariaLabel = el.getAttribute('aria-label') || '';
    const placeholder = el.getAttribute('placeholder') || '';
    const nameAttr = el.getAttribute('name') || '';
    const idAttr = el.getAttribute('id') || '';
    let labelText = '';
    if (idAttr) {
      const lbl = document.querySelector(`label[for="${CSS.escape(idAttr)}"]`);
      if (lbl) labelText = (lbl.innerText || '').trim();
    }
    const inSearchForm = Boolean(el.closest('form[role="search"], [role="search"]'));
    results.push({
      marker,
      tag,
      type,
      role,
      aria_label: ariaLabel,
      placeholder,
      name: nameAttr,
      id: idAttr,
      label: labelText,
      in_search_form: inSearchForm,
    });
  }
  return results;
}
"""


def _normalize_url(url: str) -> str:
    """Strip fragments and normalize trailing slashes for deduplication."""
    clean, _ = urldefrag((url or "").strip())
    return clean.rstrip("/") or clean


def _one_line(text: Any, fallback: str) -> str:
    """Force tool_call reason into a concise single line."""
    raw = str(text or "").strip()
    if not raw:
        return fallback
    single = " ".join(raw.splitlines()).strip()
    return single[:240] if single else fallback


def _get_start_url(task: InvestigationTask) -> str:
    start_url = getattr(task, "start_url", None)
    if isinstance(start_url, str) and start_url.strip():
        return start_url.strip()
    start_urls = getattr(task, "start_urls", None) or []
    for candidate in start_urls:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ValueError("InvestigationTask must define a non-empty start_url.")


def _get_playbook(task: InvestigationTask) -> str:
    return str(
        getattr(task, "playbook", None)
        or getattr(task, "mode", None)
        or getattr(task, "task_type", None)
        or "discover_and_inspect"
    )


def _resolve_locator(page: Page, ref: str, obs: PageObservation) -> Locator | None:
    meta = obs.refs.get(ref)
    if meta is not None:
        if meta.get("mode") == "aria":
            return page.locator(f"aria-ref={ref}")
        return page.locator(f'[data-rt-ref="{ref}"]')
    if re.fullmatch(r"(?:f\d+)?e\d+", ref):
        return page.locator(f"aria-ref={ref}")
    if re.fullmatch(r"n\d+", ref):
        return page.locator(f'[data-rt-ref="{ref}"]')
    return None


async def _inspect_locator_meta(
    locator: Locator | None,
    fallback_meta: dict[str, Any] | None,
    base_url: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = dict(fallback_meta or {})
    if locator is not None:
        try:
            if await locator.count() > 0:
                live_meta: dict[str, Any] = await locator.first.evaluate(_ELEMENT_META_JS)
                for k, v in live_meta.items():
                    if v:
                        meta[k] = v
                href = meta.get("href")
                if isinstance(href, str) and href and not href.startswith("#"):
                    meta["href"] = urljoin(base_url, href)
        except Exception:
            pass
    return meta


async def _find_search_input(page: Page) -> tuple[Locator | None, dict[str, Any] | None]:
    """Locate the site's visible search box generically using ARIA/HTML semantics."""
    try:
        candidates: list[dict[str, Any]] = await page.evaluate(_FIND_SEARCH_CANDIDATES_JS)
    except Exception:
        return None, None

    if not candidates:
        return None, None

    # Score candidates so explicit search inputs always win over generic text boxes.
    def _score(c: dict[str, Any]) -> int:
        if not is_search_box(c):
            return -1
        score = 0
        if c.get("type") == "search":
            score += 4
        if c.get("role") == "searchbox":
            score += 4
        if c.get("in_search_form"):
            score += 3
        if c.get("placeholder") or c.get("aria_label") or c.get("name"):
            score += 1
        return score

    ranked = sorted(candidates, key=_score, reverse=True)
    best = ranked[0]
    if _score(best) < 0:
        # Return best candidate metadata so guard() produces a clear search-box rejection.
        return None, best

    marker = best["marker"]
    return page.locator(f'[data-rt-search-cand="{marker}"]').first, best


async def _maybe_click_adjacent_search_button(
    page: Page,
    search_input: Locator,
    allow_domains: list[str],
) -> None:
    """If Enter did not trigger navigation/DOM update, click a guarded 'Search' button in the same form."""
    try:
        form_btn = search_input.locator(
            'xpath=ancestor::form[1]//button[not(@disabled)] | following-sibling::button[not(@disabled)]'
        )
        count = await form_btn.count()
        for idx in range(min(count, 3)):
            btn = form_btn.nth(idx)
            meta = await _inspect_locator_meta(btn, None, page.url)
            label = str(meta.get("name") or meta.get("text") or "").strip().lower()
            if label not in {"search", "find", "go"}:
                continue
            # Always validate through guard() before clicking.
            guard(
                {"name": "click", "args": {"ref": label}},
                allow_domains,
                element_meta=meta,
            )
            await btn.click(timeout=5000)
            return
    except Exception:
        return


async def _call_llm(
    llm: LLM,
    system: str,
    observation: str,
    history: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    result = llm.choose_action(system, observation, history, tools)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, dict):
        raise ValueError(f"LLM choose_action must return a dict, got {type(result).__name__}")
    return result


async def _quick_block_check(page: Page, http_status: int | None) -> tuple[str, str | None, str]:
    try:
        title = (await page.title()) or ""
    except Exception:
        title = ""
    try:
        body_text = await page.evaluate(
            "() => (document.body ? (document.body.innerText || '').slice(0, 3000) : '')"
        )
    except Exception:
        body_text = ""
    status, reason = detect_block(http_status, title, str(body_text or ""))
    return status, reason, title.strip()


async def investigate(
    task: InvestigationTask,
    emit: Emit,
    llm: LLM,
) -> list[PageCapture]:
    """Run an LLM-driven, guardrailed browser investigation and return PageCaptures.

    Tools exposed to the LLM:
        open_url(url), search_site(query), click(ref), read_page(),
        find_links(pattern), back(), scroll(), finish(findings).

    Enforces:
        - task.max_steps, task.max_pages, and a hard 3-minute wall-clock budget
        - Loop detection (same URL + same tool 3 times)
        - Allowlist, forbidden-click, and search-box-only typing guardrails
        - Untrusted content delimiters on all web observations
    """
    run_id = str(getattr(task, "run_id", "local") or "local")
    playbook = _get_playbook(task)
    allow_domains = list(getattr(task, "allow_domains", None) or [])
    start_url = _get_start_url(task)
    default_tier = str(
        getattr(task, "source_tier", None)
        or ("A" if playbook == "harvest_notice" else "C")
    )
    max_steps = max(1, int(getattr(task, "max_steps", 25)))
    max_pages = max(1, int(getattr(task, "max_pages", 15)))
    timeout_seconds = min(
        float(getattr(task, "timeout_seconds", MAX_WALL_CLOCK_SECONDS)),
        MAX_WALL_CLOCK_SECONDS,
    )

    # Validate initial URL(s) up front before launching a browser.
    check_url(start_url, allow_domains)
    for extra_url in list(getattr(task, "start_urls", None) or []):
        if extra_url:
            check_url(extra_url, allow_domains)

    system_prompt = build_system_prompt(task)
    tools = get_tool_schemas()

    captures_by_url: dict[str, PageCapture] = {}
    visited_urls: set[str] = set()
    history: list[dict[str, Any]] = []

    prev_url_tool: tuple[str, str] | None = None
    prev_args_key: str | None = None
    consecutive_same = 0
    consecutive_clicks_same_url = 0
    exact_action_counts: dict[tuple[str, str, str], int] = {}

    started_at = time.monotonic()

    def _record_capture(cap: PageCapture) -> None:
        key = _normalize_url(cap.url)
        existing = captures_by_url.get(key)
        if existing is None:
            captures_by_url[key] = cap
            return
        # Always keep blocked status or richer/updated text when re-reading after tab clicks.
        if cap.status == "blocked" or len(cap.text) >= len(existing.text):
            captures_by_url[key] = cap

    def _append_history(entry: dict[str, Any]) -> None:
        history.append(entry)
        if len(history) > MAX_HISTORY_ITEMS:
            del history[:-MAX_HISTORY_ITEMS]

    async with BrowserSession(allow_domains=allow_domains) as session:
        page = session.page
        await session.goto(start_url)
        visited_urls.add(_normalize_url(page.url))

        # Check immediately if the landing page itself is blocked.
        init_status, init_block_reason, init_title = await _quick_block_check(
            page, session.last_http_status
        )
        if init_status == "blocked":
            await emit(
                "step_started",
                {
                    "run_id": run_id,
                    "step": 1,
                    "url": page.url,
                    "max_steps": max_steps,
                },
            )
            blocked_cap = await capture_page(
                page,
                default_tier,
                run_id=run_id,
                step=1,
                http_status=session.last_http_status,
            )
            _record_capture(blocked_cap)
            await emit(
                "page_visited",
                {
                    "run_id": run_id,
                    "step": 1,
                    "url": blocked_cap.url,
                    "title": blocked_cap.title or init_title,
                    "screenshot_path": blocked_cap.screenshot_path,
                    "status": blocked_cap.status,
                    "block_reason": blocked_cap.block_reason or init_block_reason,
                    "source_tier": blocked_cap.source_tier,
                },
            )
            return list(captures_by_url.values())

        for step in range(1, max_steps + 1):
            if (time.monotonic() - started_at) >= timeout_seconds:
                _append_history(
                    {
                        "step": step,
                        "event": "budget_reached",
                        "detail": f"Wall-clock timeout ({timeout_seconds:.0f}s) reached.",
                    }
                )
                break

            current_url = page.url
            norm_url = _normalize_url(current_url)

            await emit(
                "step_started",
                {
                    "run_id": run_id,
                    "step": step,
                    "url": current_url,
                    "max_steps": max_steps,
                },
            )

            obs = await build_observation(
                page,
                captured_urls=set(captures_by_url.keys()),
            )

            try:
                action = await _call_llm(llm, system_prompt, obs.text, history, tools)
            except Exception as exc:
                await emit(
                    "tool_call",
                    {
                        "run_id": run_id,
                        "step": step,
                        "tool": "llm_error",
                        "args": {},
                        "reason": _one_line(exc, "LLM failed to produce an action"),
                        "allowed": False,
                        "error": str(exc),
                    },
                )
                shot = await save_step_screenshot(page, run_id=run_id, step=step)
                await emit(
                    "page_visited",
                    {
                        "run_id": run_id,
                        "step": step,
                        "url": page.url,
                        "title": obs.title,
                        "screenshot_path": shot,
                        "status": "error",
                        "block_reason": None,
                        "source_tier": infer_source_tier(page.url, default_tier),
                    },
                )
                break

            tool_name = str(action.get("name") or "").strip()
            tool_args = action.get("args") if isinstance(action.get("args"), dict) else {}
            reason = _one_line(
                action.get("reason"),
                f"Execute {tool_name or 'unknown'} on {current_url}",
            )
            args_key = json.dumps(tool_args, sort_keys=True, default=str)

            # Loop detection: same URL + same tool 3 times.
            url_tool = (norm_url, tool_name)
            if url_tool == prev_url_tool:
                if tool_name != "click" or args_key == prev_args_key:
                    consecutive_same += 1
                else:
                    consecutive_same = 1
                if tool_name == "click":
                    consecutive_clicks_same_url += 1
                else:
                    consecutive_clicks_same_url = 0
            else:
                consecutive_same = 1
                consecutive_clicks_same_url = 1 if tool_name == "click" else 0
            prev_url_tool = url_tool
            prev_args_key = args_key

            exact_key = (norm_url, tool_name, args_key)
            exact_action_counts[exact_key] = exact_action_counts.get(exact_key, 0) + 1

            if (
                consecutive_same >= LOOP_REPEAT_THRESHOLD
                or exact_action_counts[exact_key] >= LOOP_REPEAT_THRESHOLD
                or consecutive_clicks_same_url >= 6
            ):
                loop_msg = (
                    f"Loop detected: repeated ({tool_name}) on {current_url} "
                    f"{LOOP_REPEAT_THRESHOLD} times."
                )
                await emit(
                    "tool_call",
                    {
                        "run_id": run_id,
                        "step": step,
                        "tool": tool_name,
                        "args": tool_args,
                        "reason": reason,
                        "allowed": False,
                        "loop_detected": True,
                        "error": loop_msg,
                    },
                )
                shot = await save_step_screenshot(page, run_id=run_id, step=step)
                await emit(
                    "page_visited",
                    {
                        "run_id": run_id,
                        "step": step,
                        "url": page.url,
                        "title": obs.title,
                        "screenshot_path": shot,
                        "status": "ok",
                        "block_reason": None,
                        "source_tier": infer_source_tier(page.url, default_tier),
                    },
                )
                break

            # Prepare resolved DOM/ARIA metadata for guard().
            element_meta: dict[str, Any] | None = None
            click_locator: Locator | None = None
            search_locator: Locator | None = None

            if tool_name == "click":
                ref = str(tool_args.get("ref") or "").strip()
                click_locator = _resolve_locator(page, ref, obs) if ref else None
                element_meta = await _inspect_locator_meta(
                    click_locator,
                    obs.refs.get(ref),
                    current_url,
                )
            elif tool_name == "search_site":
                search_locator, element_meta = await _find_search_input(page)

            # Enforce policy guardrails before executing any tool.
            try:
                guard(action, allow_domains, element_meta=element_meta)
            except GuardError as exc:
                await emit(
                    "tool_call",
                    {
                        "run_id": run_id,
                        "step": step,
                        "tool": tool_name,
                        "args": tool_args,
                        "reason": reason,
                        "allowed": False,
                        "blocked_by_guard": True,
                        "error": str(exc),
                    },
                )
                _append_history(
                    {
                        "step": step,
                        "url": current_url,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": f"BLOCKED_BY_GUARD: {exc}",
                    }
                )
                shot = await save_step_screenshot(page, run_id=run_id, step=step)
                await emit(
                    "page_visited",
                    {
                        "run_id": run_id,
                        "step": step,
                        "url": page.url,
                        "title": obs.title,
                        "screenshot_path": shot,
                        "status": "ok",
                        "block_reason": None,
                        "source_tier": infer_source_tier(page.url, default_tier),
                    },
                )
                continue

            # Enforce max_pages budget before navigating to a brand-new URL.
            target_new_url: str | None = None
            if tool_name == "open_url":
                target_new_url = str(tool_args.get("url") or "").strip()
            elif tool_name == "click" and element_meta:
                href = str(element_meta.get("href") or "").strip()
                if href and not href.startswith("#"):
                    target_new_url = href

            if (
                target_new_url
                and _normalize_url(target_new_url) not in visited_urls
                and len(visited_urls) >= max_pages
            ):
                budget_msg = (
                    f"Page budget reached (max_pages={max_pages}). "
                    "Call read_page on current page if needed, then call finish."
                )
                await emit(
                    "tool_call",
                    {
                        "run_id": run_id,
                        "step": step,
                        "tool": tool_name,
                        "args": tool_args,
                        "reason": reason,
                        "allowed": False,
                        "error": budget_msg,
                    },
                )
                _append_history(
                    {
                        "step": step,
                        "url": current_url,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": f"BUDGET_LIMIT: {budget_msg}",
                    }
                )
                shot = await save_step_screenshot(page, run_id=run_id, step=step)
                await emit(
                    "page_visited",
                    {
                        "run_id": run_id,
                        "step": step,
                        "url": page.url,
                        "title": obs.title,
                        "screenshot_path": shot,
                        "status": "ok",
                        "block_reason": None,
                        "source_tier": infer_source_tier(page.url, default_tier),
                    },
                )
                continue

            # Action approved by guardrails — emit tool_call and execute.
            await emit(
                "tool_call",
                {
                    "run_id": run_id,
                    "step": step,
                    "tool": tool_name,
                    "args": tool_args,
                    "reason": reason,
                    "allowed": True,
                },
            )

            step_screenshot_path: str | None = None
            step_status = "ok"
            step_block_reason: str | None = None
            step_title = obs.title
            tool_outcome = "ok"
            should_finish = False
            navigated_or_changed = False

            try:
                if tool_name == "open_url":
                    target_url = str(tool_args["url"]).strip()
                    await session.goto(target_url)
                    visited_urls.add(_normalize_url(page.url))
                    navigated_or_changed = True
                    tool_outcome = f"Opened {page.url} (HTTP {session.last_http_status})"

                elif tool_name == "search_site":
                    query = str(tool_args["query"]).strip()
                    if search_locator is None:
                        tool_outcome = "No visible search input found on this page."
                    else:
                        before_url = page.url
                        before_len = len(obs.aria_snapshot)
                        await search_locator.click(timeout=5000)
                        await search_locator.fill(query, timeout=5000)
                        await search_locator.press("Enter", timeout=5000)
                        await session.settle()
                        await asyncio.sleep(0.35)
                        # If neither URL nor visible DOM changed, try an adjacent "Search" button.
                        if page.url == before_url:
                            after_obs = await build_observation(page)
                            if abs(len(after_obs.aria_snapshot) - before_len) < 10:
                                await _maybe_click_adjacent_search_button(
                                    page, search_locator, allow_domains
                                )
                                await session.settle()
                                await asyncio.sleep(0.35)
                        visited_urls.add(_normalize_url(page.url))
                        navigated_or_changed = True
                        tool_outcome = f"Searched site for {query!r}; now at {page.url}"

                elif tool_name == "click":
                    ref = str(tool_args.get("ref") or "").strip()
                    if click_locator is None or await click_locator.count() == 0:
                        tool_outcome = f"Element ref {ref!r} was not found on the current page."
                    else:
                        before_blocked = len(session.blocked_navigations)
                        await click_locator.first.click(timeout=8000)
                        await session.settle()
                        await asyncio.sleep(0.25)
                        if len(session.blocked_navigations) > before_blocked:
                            blocked_target = session.blocked_navigations[-1]
                            tool_outcome = (
                                f"Navigation to off-allowlist URL {blocked_target!r} was blocked."
                            )
                        else:
                            visited_urls.add(_normalize_url(page.url))
                            navigated_or_changed = True
                            tool_outcome = f"Clicked {ref!r}; now at {page.url}"

                elif tool_name == "read_page":
                    cap = await capture_page(
                        page,
                        default_tier,
                        run_id=run_id,
                        step=step,
                        http_status=session.last_http_status,
                    )
                    _record_capture(cap)
                    step_screenshot_path = cap.screenshot_path
                    step_status = cap.status
                    step_block_reason = cap.block_reason
                    step_title = cap.title
                    tool_outcome = (
                        f"Captured {cap.url} (status={cap.status}, "
                        f"tier={cap.source_tier}, text_chars={len(cap.text)})"
                    )
                    if cap.block_reason:
                        tool_outcome += f" [block_reason={cap.block_reason}]"

                elif tool_name == "find_links":
                    pattern = str(tool_args.get("pattern") or "")
                    try:
                        regex = re.compile(pattern, re.IGNORECASE)
                        matches = [
                            lnk
                            for lnk in obs.links
                            if regex.search(lnk.get("text", ""))
                            or regex.search(lnk.get("href", ""))
                        ]
                    except re.error:
                        needle = pattern.lower()
                        matches = [
                            lnk
                            for lnk in obs.links
                            if needle in lnk.get("text", "").lower()
                            or needle in lnk.get("href", "").lower()
                        ]
                    preview = [
                        f"{m.get('ref', '-')}: {m.get('text', '')} -> {m.get('href', '')}"
                        for m in matches[:25]
                    ]
                    tool_outcome = (
                        f"Found {len(matches)} links matching {pattern!r}: "
                        + ("; ".join(preview) if preview else "(none)")
                    )

                elif tool_name == "back":
                    resp = await page.go_back(
                        wait_until="domcontentloaded",
                        timeout=session.nav_timeout_ms,
                    )
                    if resp is not None:
                        session.last_http_status = resp.status
                    await session.settle()
                    navigated_or_changed = True
                    tool_outcome = f"Navigated back to {page.url}"

                elif tool_name == "scroll":
                    direction = str(tool_args.get("direction") or "down").lower()
                    delta = 650 if direction == "down" else -650
                    await page.evaluate("(dy) => window.scrollBy(0, dy)", delta)
                    await asyncio.sleep(0.2)
                    tool_outcome = f"Scrolled {direction} on {page.url}"

                elif tool_name == "finish":
                    findings = str(tool_args.get("findings") or "").strip()
                    tool_outcome = f"Finished: {findings or 'done'}"
                    should_finish = True

            except Exception as exc:
                tool_outcome = f"Tool error ({tool_name}): {exc}"

            # Auto-record blocked/bot-check pages immediately upon navigation so
            # downstream receives status="blocked" even if the LLM steps back right away.
            if navigated_or_changed and tool_name != "read_page":
                blk_status, blk_reason, blk_title = await _quick_block_check(
                    page, session.last_http_status
                )
                step_title = blk_title or step_title
                if blk_status == "blocked":
                    blocked_cap = await capture_page(
                        page,
                        default_tier,
                        run_id=run_id,
                        step=step,
                        http_status=session.last_http_status,
                    )
                    _record_capture(blocked_cap)
                    step_screenshot_path = blocked_cap.screenshot_path
                    step_status = blocked_cap.status
                    step_block_reason = blocked_cap.block_reason or blk_reason
                    step_title = blocked_cap.title or step_title
                    tool_outcome += (
                        f" | BLOCKED page auto-captured ({step_block_reason}); "
                        "do not attempt to bypass."
                    )

            if step_screenshot_path is None:
                step_screenshot_path = await save_step_screenshot(
                    page, run_id=run_id, step=step
                )
                try:
                    step_title = (await page.title()) or step_title
                except Exception:
                    pass

            await emit(
                "page_visited",
                {
                    "run_id": run_id,
                    "step": step,
                    "url": page.url,
                    "title": step_title,
                    "screenshot_path": step_screenshot_path,
                    "status": step_status,
                    "block_reason": step_block_reason,
                    "source_tier": infer_source_tier(page.url, default_tier),
                },
            )

            _append_history(
                {
                    "step": step,
                    "url": page.url,
                    "tool": tool_name,
                    "args": tool_args,
                    "reason": reason,
                    "result": tool_outcome[:600],
                }
            )

            if should_finish:
                break

    return list(captures_by_url.values())
