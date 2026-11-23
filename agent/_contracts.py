"""Compatibility layer for shared contracts owned by M3 (`contracts/models.py`).

M1 must not create or modify `contracts/models.py`. When `contracts/models.py`
is present in the repository, this module imports the canonical models and LLM
protocol directly from it. Until M3 commits `contracts/models.py`, local
Pydantic v2 fallbacks matching the team specification are used so M1 code and
offline tests can run immediately.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]

try:
    from contracts.models import (  # type: ignore[import-not-found]
        InvestigationTask,
        LLM,
        PageCapture,
    )

    USING_CONTRACT_STUBS = False
except ImportError:
    USING_CONTRACT_STUBS = True

    @runtime_checkable
    class LLM(Protocol):
        """Protocol for LLM backends provided by M2 (`matching/llm.py`)."""

        async def choose_action(
            self,
            system: str,
            observation: str,
            history: list[dict[str, Any]],
            tools: list[dict[str, Any]],
        ) -> dict[str, Any]:
            """Choose the next browser tool action.

            Returns:
                {"name": <tool>, "args": {...}, "reason": "<one line>"}
            """
            ...

    class PageCapture(BaseModel):
        """Captured content and metadata for a visited web page."""

        url: str
        title: str = ""
        text: str = ""
        spec_text: str = ""
        source_tier: Literal["A", "B", "C"] = "C"
        status: Literal["ok", "blocked", "error"] = "ok"
        block_reason: str | None = None
        http_status: int | None = None
        screenshot_path: str | None = None
        fetched_at: datetime = Field(
            default_factory=lambda: datetime.now(timezone.utc)
        )
        links: list[str] = Field(default_factory=list)

    class InvestigationTask(BaseModel):
        """Task parameters passed into M1's `agent.agent.investigate`."""

        run_id: str = "local"
        playbook: Literal["harvest_notice", "discover_and_inspect"] = (
            "discover_and_inspect"
        )
        start_url: str
        start_urls: list[str] = Field(default_factory=list)
        allow_domains: list[str] = Field(default_factory=list)
        goal: str = ""
        query_terms: list[str] = Field(default_factory=list)
        brand: str | None = None
        models: list[str] = Field(default_factory=list)
        product_name: str | None = None
        source_tier: Literal["A", "B", "C"] | None = None
        max_steps: int = 25
        max_pages: int = 15
        timeout_seconds: int = 180


def build_page_capture(
    *,
    url: str,
    title: str,
    text: str,
    spec_text: str,
    source_tier: str,
    status: str,
    block_reason: str | None,
    http_status: int | None,
    screenshot_path: str | None,
    fetched_at: datetime,
    links: list[str] | None = None,
) -> PageCapture:
    """Construct a `PageCapture` compatible with both stub and M3 schemas.

    Inspects `PageCapture.model_fields` so that if M3's `contracts/models.py`
    omits optional helper fields (such as `spec_text`, `http_status`, or
    `links`) or uses slightly different alias names, construction still
    succeeds without failing validation.
    """
    fields = getattr(PageCapture, "model_fields", {})
    combined_text = text
    if spec_text and spec_text.strip() and spec_text.strip() not in text:
        combined_text = (
            f"{text.rstrip()}\n\n[Specifications / Tables]\n{spec_text.strip()}"
            if text.strip()
            else spec_text.strip()
        )

    candidates: dict[str, Any] = {
        "url": url,
        "title": title,
        "text": combined_text,
        "main_text": text,
        "page_text": combined_text,
        "spec_text": spec_text,
        "specs_text": spec_text,
        "tables_text": spec_text,
        "source_tier": source_tier,
        "status": status,
        "block_reason": block_reason,
        "http_status": http_status,
        "screenshot_path": screenshot_path,
        "screenshot": screenshot_path,
        "fetched_at": fetched_at,
        "links": links or [],
    }

    if not fields:
        return PageCapture(
            url=url,
            title=title,
            text=combined_text,
            spec_text=spec_text,
            source_tier=source_tier,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            block_reason=block_reason,
            http_status=http_status,
            screenshot_path=screenshot_path,
            fetched_at=fetched_at,
            links=links or [],
        )

    kwargs: dict[str, Any] = {}
    for field_name, field_info in fields.items():
        if field_name in candidates:
            value = candidates[field_name]
            if field_name == "fetched_at" and field_info.annotation is str:
                value = fetched_at.isoformat()
            kwargs[field_name] = value

    return PageCapture(**kwargs)
