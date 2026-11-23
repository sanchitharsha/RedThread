"""Async Playwright (Chromium) session manager and page capture utilities.

One browser context per investigation run with:
- Honest User-Agent: "Redthread-Hackathon-Bot"
- Viewport: 1280x800
- Sensible navigation/action timeouts
- Cleaned main text + revealed specification/variant table text extraction
- JPEG screenshots saved under runs/<run_id>/shots/
- Transparent bot-check / block detection (no CAPTCHA solving or evasion)
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Response,
    Route,
    async_playwright,
)

from agent._contracts import PageCapture, build_page_capture
from agent.guard import GuardError, check_url

USER_AGENT = "Redthread-Hackathon-Bot"
VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_NAV_TIMEOUT_MS = 20_000
DEFAULT_ACTION_TIMEOUT_MS = 10_000

BLOCK_STATUS_CODES: frozenset[int] = frozenset({403, 429})

_BLOCK_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcaptcha\b", re.IGNORECASE), "CAPTCHA challenge detected"),
    (
        re.compile(r"\bverify\s+you\s+are\s+human\b", re.IGNORECASE),
        "Human verification challenge detected",
    ),
    (
        re.compile(r"\bhuman\s+verification\b", re.IGNORECASE),
        "Human verification challenge detected",
    ),
    (
        re.compile(r"\bunusual\s+traffic\b", re.IGNORECASE),
        "Unusual traffic block detected",
    ),
    (
        re.compile(r"\bbot[\s-]*check\b", re.IGNORECASE),
        "Bot-check interstitial detected",
    ),
    (
        re.compile(r"\bchecking\s+your\s+browser\b", re.IGNORECASE),
        "Browser verification interstitial detected",
    ),
    (
        re.compile(r"\bare\s+you\s+a\s+robot\b|\bi\s+am\s+not\s+a\s+robot\b", re.IGNORECASE),
        "Robot check detected",
    ),
    (
        re.compile(r"\btoo\s+many\s+requests\b", re.IGNORECASE),
        "Rate limit (too many requests) detected",
    ),
)

_SHORT_PAGE_BLOCK_RE = re.compile(
    r"\b(access\s+denied|request\s+blocked|automated\s+access\s+blocked|forbidden)\b",
    re.IGNORECASE,
)


def infer_source_tier(url: str, default_tier: str = "C") -> str:
    """Return source tier 'A' for official cpsc.gov pages, else default_tier."""
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host == "cpsc.gov" or host.endswith(".cpsc.gov"):
        return "A"
    return default_tier


def detect_block(
    http_status: int | None,
    title: str,
    text: str,
) -> tuple[str, str | None]:
    """Inspect HTTP status, page title, and visible text for bot-check/block signals.

    Returns:
        ("blocked", reason) when blocked, otherwise ("ok", None).
    """
    if http_status in BLOCK_STATUS_CODES:
        return "blocked", f"HTTP {http_status} response"

    combined = f"{title}\n{text}"
    for pattern, reason in _BLOCK_PHRASES:
        if pattern.search(combined):
            return "blocked", reason

    # Match generic "Access Denied" / "Forbidden" on short interstitial pages or titles.
    if title and _SHORT_PAGE_BLOCK_RE.search(title):
        return "blocked", f"Blocked page title: {title.strip()[:120]}"
    if len(text.strip()) < 1500 and _SHORT_PAGE_BLOCK_RE.search(text):
        return "blocked", "Access denied / blocked page content"

    return "ok", None


def _clean_text(raw: str) -> str:
    """Normalize line endings and runs of spaces while preserving exact tokens."""
    if not raw:
        return ""
    lines: list[str] = []
    for raw_line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        # Preserve single spaces, hyphens, model identifiers, and GTIN formatting.
        cleaned = re.sub(r"[ \t\u00a0]+", " ", raw_line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _resolve_shots_dir(run_id: str, shots_dir: Path | str | None = None) -> Path:
    if shots_dir is not None:
        target = Path(shots_dir)
    else:
        base_runs = Path(os.environ.get("REDTHREAD_RUNS_DIR", "runs"))
        clean_run_id = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id or "local").strip("_") or "local"
        target = base_runs / clean_run_id / "shots"
    target.mkdir(parents=True, exist_ok=True)
    return target


async def save_step_screenshot(
    page: Page,
    *,
    run_id: str = "local",
    step: int | None = None,
    label: str = "step",
    shots_dir: Path | str | None = None,
) -> str | None:
    """Save a JPEG screenshot under runs/<run_id>/shots/ and return its path."""
    target_dir = _resolve_shots_dir(run_id, shots_dir=shots_dir)
    if step is not None:
        filename = f"{label}_{step:03d}.jpg"
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        filename = f"{label}_{stamp}.jpg"
    out_path = target_dir / filename
    try:
        await page.screenshot(
            path=str(out_path),
            type="jpeg",
            quality=75,
            full_page=False,
            timeout=DEFAULT_ACTION_TIMEOUT_MS,
        )
        return out_path.as_posix()
    except Exception:
        return None


_EXTRACT_TEXT_JS = """
() => {
  const isVisible = (el) => {
    if (!el || el.nodeType !== 1) return false;
    const style = window.getComputedStyle(el);
    if (!style) return false;
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (parseFloat(style.opacity || '1') === 0) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return false;
    return true;
  };

  // Main readable text: prefer <main> or [role="main"] when substantial, else body.
  const mainEl = document.querySelector('main, [role="main"]');
  const rootEl = (mainEl && (mainEl.innerText || '').trim().length >= 40)
    ? mainEl
    : (document.body || document.documentElement);

  const mainText = rootEl ? (rootEl.innerText || '') : '';

  // Spec tables, definition lists, and expanded tabs/accordions/details.
  const specChunks = [];
  const seen = new Set();

  const pushChunk = (s) => {
    const t = (s || '').trim();
    if (t && !seen.has(t)) {
      seen.add(t);
      specChunks.push(t);
    }
  };

  for (const table of document.querySelectorAll('table')) {
    if (!isVisible(table)) continue;
    const rows = [];
    for (const tr of table.querySelectorAll('tr')) {
      if (!isVisible(tr)) continue;
      const cells = Array.from(tr.querySelectorAll('th, td'))
        .filter((c) => isVisible(c))
        .map((c) => (c.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(Boolean);
      if (cells.length === 2) {
        rows.push(`${cells[0]}: ${cells[1]}`);
      } else if (cells.length > 0) {
        rows.push(cells.join(' | '));
      }
    }
    if (rows.length) pushChunk(rows.join('\\n'));
  }

  for (const dl of document.querySelectorAll('dl')) {
    if (!isVisible(dl)) continue;
    const pairs = [];
    let currentKey = '';
    for (const child of dl.children) {
      if (!isVisible(child)) continue;
      const tag = child.tagName.toLowerCase();
      const txt = (child.innerText || '').replace(/\\s+/g, ' ').trim();
      if (!txt) continue;
      if (tag === 'dt') {
        currentKey = txt;
      } else if (tag === 'dd') {
        pairs.push(currentKey ? `${currentKey}: ${txt}` : txt);
      }
    }
    if (pairs.length) pushChunk(pairs.join('\\n'));
  }

  const expandedRegions = document.querySelectorAll(
    '[role="tabpanel"], details[open], [aria-expanded="true"]'
  );
  for (const region of expandedRegions) {
    if (!isVisible(region)) continue;
    const txt = (region.innerText || '').trim();
    if (txt && txt.length >= 10) {
      pushChunk(txt);
    }
  }

  // Visible links resolved to absolute URLs.
  const links = [];
  const linkSeen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    if (!isVisible(a)) continue;
    const href = a.href;
    if (!href || href.startsWith('javascript:') || href.startsWith('mailto:')) continue;
    if (!linkSeen.has(href)) {
      linkSeen.add(href);
      links.push(href);
    }
  }

  return {
    mainText,
    specText: specChunks.join('\\n\\n'),
    links,
  };
}
"""


async def capture_page(
    page: Page,
    source_tier: str = "C",
    *,
    run_id: str = "local",
    step: int | None = None,
    shots_dir: Path | str | None = None,
    http_status: int | None = None,
) -> PageCapture:
    """Capture cleaned text, spec tables, screenshot, and block status from `page`.

    Args:
        page: Active Playwright page.
        source_tier: Evidence source tier ("A", "B", or "C"). `cpsc.gov` URLs
            automatically resolve to tier "A".
        run_id: Run identifier used for `runs/<run_id>/shots/`.
        step: Optional step number for deterministic screenshot naming.
        shots_dir: Optional override directory for screenshots.
        http_status: Last main-frame HTTP status code, if known.

    Returns:
        PageCapture populated with verbatim text, revealed spec-table text,
        title, UTC `fetched_at`, JPEG screenshot path, and block status.
    """
    url = page.url
    fetched_at = datetime.now(timezone.utc)
    resolved_tier = infer_source_tier(url, default_tier=source_tier)

    try:
        title = (await page.title()) or ""
    except Exception:
        title = ""

    try:
        extracted: dict[str, Any] = await page.evaluate(_EXTRACT_TEXT_JS)
    except Exception:
        extracted = {"mainText": "", "specText": "", "links": []}

    main_text = _clean_text(str(extracted.get("mainText") or ""))
    spec_text = _clean_text(str(extracted.get("specText") or ""))
    links = [str(u) for u in (extracted.get("links") or []) if isinstance(u, str)]

    screenshot_path = await save_step_screenshot(
        page,
        run_id=run_id,
        step=step,
        label="capture" if step is None else "step",
        shots_dir=shots_dir,
    )

    combined_for_block = f"{main_text}\n{spec_text}".strip()
    status, block_reason = detect_block(http_status, title, combined_for_block)

    return build_page_capture(
        url=url,
        title=title.strip(),
        text=main_text,
        spec_text=spec_text,
        source_tier=resolved_tier,
        status=status,
        block_reason=block_reason,
        http_status=http_status,
        screenshot_path=screenshot_path,
        fetched_at=fetched_at,
        links=links,
    )


class BrowserSession:
    """Async context manager managing one Playwright Chromium context per run."""

    def __init__(
        self,
        *,
        allow_domains: list[str] | None = None,
        headless: bool | None = None,
        nav_timeout_ms: int = DEFAULT_NAV_TIMEOUT_MS,
        action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS,
    ) -> None:
        if headless is None:
            env_val = os.environ.get("REDTHREAD_HEADLESS", "true").strip().lower()
            headless = env_val not in {"0", "false", "no"}
        self.allow_domains = list(allow_domains or [])
        self.headless = headless
        self.nav_timeout_ms = nav_timeout_ms
        self.action_timeout_ms = action_timeout_ms

        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.last_http_status: int | None = None
        self.blocked_navigations: list[str] = []

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserSession has not been entered.")
        return self._page

    async def __aenter__(self) -> BrowserSession:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            ignore_https_errors=False,
        )
        self._context.set_default_navigation_timeout(self.nav_timeout_ms)
        self._context.set_default_timeout(self.action_timeout_ms)

        if self.allow_domains:
            await self._context.route("**/*", self._route_guard)

        self._page = await self._context.new_page()
        self._page.on("response", self._on_response)
        return self

    async def _route_guard(self, route: Route) -> None:
        """Network-layer allowlist enforcement for top-level document navigations."""
        req = route.request
        if req.is_navigation_request() and req.resource_type == "document":
            try:
                check_url(req.url, self.allow_domains)
            except GuardError:
                self.blocked_navigations.append(req.url)
                await route.abort("blockedbyclient")
                return
        await route.continue_()

    def _on_response(self, response: Response) -> None:
        try:
            if (
                self._page is not None
                and response.frame == self._page.main_frame
                and response.request.is_navigation_request()
            ):
                self.last_http_status = response.status
        except Exception:
            pass

    async def goto(self, url: str) -> Response | None:
        """Navigate to an allowlisted URL and record the main-frame HTTP status."""
        if self.allow_domains:
            check_url(url, self.allow_domains)
        self.last_http_status = None
        response = await self.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.nav_timeout_ms,
        )
        if response is not None:
            self.last_http_status = response.status
        await self.settle()
        return response

    async def settle(self, network_idle_ms: int = 1500) -> None:
        """Wait briefly for client-side rendering / XHR fetches to finish."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=network_idle_ms)
        except Exception:
            pass

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self._page = None
