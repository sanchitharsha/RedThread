"""LLM observation builder for the Redthread browser agent.

Builds a strictly size-capped (~6000 character) observation containing:
- Current URL
- Page title
- Trimmed accessibility snapshot (using Playwright's native `page.aria_snapshot(mode="ai")`
  verified on playwright==1.65.2, with an automatic numeric-id DOM fallback if
  an older Playwright runtime lacks `aria_snapshot`)
- Deduplicated link list
All page-derived content is wrapped in untrusted-content delimiters via `wrap_untrusted`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Page

from agent.guard import UNTRUSTED_END, wrap_untrusted

MAX_OBSERVATION_CHARS = 6000

_ARIA_REF_LINE_RE = re.compile(
    r'^(?P<indent>\s*)-\s+(?P<role>[a-zA-Z0-9_-]+)'
    r'(?:\s+"(?P<name>(?:\\.|[^"\\])*)")?'
    r'(?P<rest>.*?)\[ref=(?P<ref>[A-Za-z0-9_-]+)\]'
)
_ARIA_URL_LINE_RE = re.compile(r"^\s*-\s+/url:\s+(?P<href>.+?)\s*$")

_EXTRACT_LINKS_JS = """
() => {
  const isVisible = (el) => {
    const s = window.getComputedStyle(el);
    if (!s || s.display === 'none' || s.visibility === 'hidden') return false;
    if (parseFloat(s.opacity || '1') === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  };
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    if (!isVisible(a)) continue;
    const href = a.href || '';
    if (!href || href.startsWith('javascript:') || href.startsWith('mailto:')) continue;
    const text = (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '')
      .replace(/\\s+/g, ' ')
      .trim()
      .slice(0, 120);
    const key = `${href}::${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ text: text || href, href });
    if (out.length >= 80) break;
  }
  return out;
}
"""

_FALLBACK_DOM_SNAPSHOT_JS = """
() => {
  const isVisible = (el) => {
    const s = window.getComputedStyle(el);
    if (!s || s.display === 'none' || s.visibility === 'hidden') return false;
    if (parseFloat(s.opacity || '1') === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  };
  const selector = [
    'a[href]',
    'button',
    'input',
    'select',
    'textarea',
    'summary',
    '[role="button"]',
    '[role="tab"]',
    '[role="link"]',
    '[role="searchbox"]',
    '[role="textbox"]',
  ].join(',');

  const items = [];
  let idx = 1;
  for (const el of document.querySelectorAll(selector)) {
    if (!isVisible(el)) continue;
    const ref = `n${idx++}`;
    el.setAttribute('data-rt-ref', ref);
    const tag = el.tagName.toLowerCase();
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    const role = el.getAttribute('role')
      || (tag === 'a' ? 'link'
        : tag === 'button' ? 'button'
        : (tag === 'input' && inputType === 'search') ? 'searchbox'
        : (tag === 'input' || tag === 'textarea') ? 'textbox'
        : tag);
    const name = (
      el.getAttribute('aria-label')
      || el.innerText
      || el.getAttribute('placeholder')
      || el.getAttribute('name')
      || el.getAttribute('value')
      || ''
    ).replace(/\\s+/g, ' ').trim().slice(0, 120);
    const href = tag === 'a' ? (el.href || '') : '';
    items.push({ ref, role, name, href, tag, type: inputType });
    if (items.length >= 120) break;
  }
  const snippet = (document.body ? (document.body.innerText || '') : '')
    .replace(/\\s+/g, ' ')
    .trim()
    .slice(0, 1500);
  return { items, snippet };
}
"""


@dataclass
class PageObservation:
    """Structured observation plus hard-capped prompt string for the LLM."""

    url: str
    title: str
    text: str
    aria_snapshot: str
    links: list[dict[str, str]] = field(default_factory=list)
    refs: dict[str, dict[str, Any]] = field(default_factory=dict)
    used_aria_snapshot: bool = True


def _unescape_aria_name(raw: str) -> str:
    return raw.replace('\\"', '"').replace("\\\\", "\\")


def _parse_aria_refs(snapshot: str, base_url: str) -> dict[str, dict[str, Any]]:
    """Extract element ref metadata (`role`, `name`, `href`) from Playwright's AI ARIA snapshot."""
    refs: dict[str, dict[str, Any]] = {}
    last_ref: str | None = None
    last_indent = -1

    for line in snapshot.splitlines():
        url_match = _ARIA_URL_LINE_RE.match(line)
        if url_match and last_ref is not None:
            indent = len(line) - len(line.lstrip(" "))
            if indent > last_indent:
                raw_href = url_match.group("href").strip().strip('"').strip("'")
                if raw_href and not raw_href.startswith("javascript:"):
                    refs[last_ref]["href"] = urljoin(base_url, raw_href)
                continue

        m = _ARIA_REF_LINE_RE.match(line)
        if m:
            ref = m.group("ref")
            role = m.group("role")
            raw_name = m.group("name") or ""
            name = _unescape_aria_name(raw_name)
            refs[ref] = {
                "ref": ref,
                "role": role,
                "name": name,
                "href": None,
                "mode": "aria",
            }
            last_ref = ref
            last_indent = len(m.group("indent"))
        elif line.strip():
            indent = len(line) - len(line.lstrip(" "))
            if indent <= last_indent:
                last_ref = None
                last_indent = -1

    return refs


def _trim_lines(text: str, max_chars: int, marker: str = "... [truncated]") -> str:
    """Trim multi-line text on line boundaries to fit within `max_chars`."""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker) + 2:
        return text[:max_chars]
    budget = max_chars - len(marker) - 1
    out: list[str] = []
    used = 0
    for line in text.splitlines():
        add_len = len(line) + (1 if out else 0)
        if used + add_len > budget:
            break
        out.append(line)
        used += add_len
    if not out:
        return text[:budget] + "\n" + marker
    return "\n".join(out) + "\n" + marker


def _clamp_observation(formatted: str, max_chars: int) -> str:
    """Guarantee `len(formatted) <= max_chars` while keeping closing untrusted delimiter."""
    if len(formatted) <= max_chars:
        return formatted
    suffix = f"\n... [observation truncated]\n{UNTRUSTED_END}"
    keep = max(0, max_chars - len(suffix))
    return formatted[:keep].rstrip() + suffix


async def build_observation(
    page: Page,
    *,
    max_chars: int = MAX_OBSERVATION_CHARS,
    captured_urls: set[str] | None = None,
) -> PageObservation:
    """Build a trimmed, delimiter-wrapped observation for the LLM.

    Uses Playwright's native `page.aria_snapshot(mode="ai")` when available
    (confirmed on playwright==1.65.2), and falls back to DOM ref assignment
    if `aria_snapshot` is unavailable.
    """
    url = page.url
    try:
        title = (await page.title()) or ""
    except Exception:
        title = ""

    aria_snapshot = ""
    refs: dict[str, dict[str, Any]] = {}
    used_aria = False

    if hasattr(page, "aria_snapshot"):
        try:
            aria_snapshot = await page.aria_snapshot(mode="ai", timeout=5000)
            if aria_snapshot and aria_snapshot.strip():
                refs = _parse_aria_refs(aria_snapshot, url)
                used_aria = True
        except Exception:
            used_aria = False

    if not used_aria:
        try:
            fallback = await page.evaluate(_FALLBACK_DOM_SNAPSHOT_JS)
        except Exception:
            fallback = {"items": [], "snippet": ""}
        lines: list[str] = []
        for item in fallback.get("items") or []:
            ref = str(item.get("ref") or "")
            role = str(item.get("role") or "element")
            name = str(item.get("name") or "")
            href = str(item.get("href") or "")
            refs[ref] = {
                "ref": ref,
                "role": role,
                "name": name,
                "href": href or None,
                "tag": item.get("tag") or "",
                "type": item.get("type") or "",
                "mode": "dom",
            }
            desc = f'- {role} "{name}" [ref={ref}]'
            if href:
                desc += f" -> {href}"
            lines.append(desc)
        snippet = str(fallback.get("snippet") or "")
        if snippet:
            lines.append("")
            lines.append(f"Visible text excerpt: {snippet}")
        aria_snapshot = "\n".join(lines)

    try:
        links: list[dict[str, str]] = await page.evaluate(_EXTRACT_LINKS_JS)
    except Exception:
        links = []

    # Attach link refs when an ARIA/DOM ref shares the same absolute href.
    href_to_ref: dict[str, str] = {}
    for ref_id, meta in refs.items():
        href = meta.get("href")
        if href and href not in href_to_ref:
            href_to_ref[str(href)] = ref_id

    link_lines: list[str] = []
    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")
        ref_id = href_to_ref.get(href)
        if ref_id:
            link["ref"] = ref_id
            link_lines.append(f"- [{ref_id}] {text} -> {href}")
        else:
            link_lines.append(f"- {text} -> {href}")

    # Budget allocation inside max_chars:
    # ~350 chars header + delimiters, ~3600 chars ARIA snapshot, ~1600 chars links.
    snap_budget = max(800, int(max_chars * 0.60))
    links_budget = max(400, int(max_chars * 0.25))

    trimmed_snap = _trim_lines(aria_snapshot.strip(), snap_budget)
    trimmed_links = _trim_lines("\n".join(link_lines), links_budget) if link_lines else "(no visible links)"

    captured_note = ""
    if captured_urls:
        captured_preview = ", ".join(sorted(captured_urls)[:15])
        captured_note = f"Already captured ({len(captured_urls)}): {captured_preview}\n"

    untrusted_body = (
        f"Title: {title.strip()}\n\n"
        f"Accessibility Snapshot:\n{trimmed_snap}\n\n"
        f"Links:\n{trimmed_links}"
    )

    formatted = (
        f"Current URL: {url}\n"
        f"{captured_note}"
        f"{wrap_untrusted(untrusted_body)}"
    )
    formatted = _clamp_observation(formatted, max_chars=max_chars)

    return PageObservation(
        url=url,
        title=title.strip(),
        text=formatted,
        aria_snapshot=trimmed_snap,
        links=links,
        refs=refs,
        used_aria_snapshot=used_aria,
    )
