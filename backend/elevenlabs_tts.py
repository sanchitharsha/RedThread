"""
ElevenLabs TTS integration — voice narration of investigation reports.
Sponsor prize qualification: ElevenLabs.

Generates a concise audio briefing from the exposure report using
ElevenLabs Text-to-Speech API v1.

Usage:
  audio_bytes = await narrate_report(report: ReportJSON)
  → returns MP3 bytes

Requires env vars:
  ELEVENLABS_API_KEY   — API key from elevenlabs.io
  ELEVENLABS_VOICE_ID  — (optional) voice ID; defaults to "Rachel"
  ELEVENLABS_MODEL     — (optional) model; defaults to "eleven_multilingual_v2"
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from contracts.models import ReportJSON

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
DEFAULT_MODEL = "eleven_multilingual_v2"


def _get_config() -> dict:
    """Read ElevenLabs config from env."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)
    return {"api_key": api_key, "voice_id": voice_id, "model_id": model_id}


def is_configured() -> bool:
    """Check if ElevenLabs API key is set."""
    return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())


def _build_script(report: ReportJSON) -> str:
    """Build a natural-language briefing script from the report."""
    lines = []
    lines.append(f"Redthread Exposure Report Briefing.")
    lines.append("")

    # Recall info
    lines.append(
        f"This investigation concerns recall number {report.recall_number}, "
        f"titled: {report.recall_title}."
    )
    lines.append("")

    # Tier summary
    total = sum(report.tier_counts.values())
    confirmed = report.tier_counts.get("CONFIRMED", 0)
    likely = report.tier_counts.get("LIKELY", 0)
    related = report.tier_counts.get("RELATED", 0)
    no_match = report.tier_counts.get("NO_MATCH", 0)
    unresolved = report.tier_counts.get("UNRESOLVED", 0)
    conflict = report.tier_counts.get("CONFLICT", 0)

    lines.append(
        f"We analyzed {total} listings. "
        f"{confirmed} confirmed matches, {likely} likely matches, "
        f"{related} related, {no_match} with no match found, "
        f"{unresolved} unresolved, and {conflict} conflicts."
    )
    lines.append("")

    # Top findings
    if report.listings:
        def _tier_str(t):
            return t.value if hasattr(t, "value") else str(t)

        high = [l for l in report.listings if _tier_str(l.best_tier) in ("CONFIRMED", "LIKELY")]
        if high:
            lines.append("Key findings:")
            for l in high[:5]:
                tier_label = _tier_str(l.best_tier).lower().replace("_", " ")
                title = l.title or l.listing_id
                lines.append(f"  {title}: {tier_label}.")
            lines.append("")

    # Disclaimer
    lines.append(
        "Remember: 'No match found' is not a statement about product safety. "
        "Always follow the official notice and remedy."
    )

    return "\n".join(lines)


async def narrate_report(report: ReportJSON) -> bytes:
    """
    Generate MP3 audio narration of a report using ElevenLabs TTS.

    Returns raw MP3 bytes.
    Raises RuntimeError if the API call fails.
    """
    config = _get_config()
    if not config["api_key"]:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set. "
            "Set it in .env to enable voice narration."
        )

    script = _build_script(report)
    logger.info("Narrating report %s (%d chars)", report.run_id, len(script))

    url = f"{ELEVENLABS_API_URL}/text-to-speech/{config['voice_id']}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={
                "xi-api-key": config["api_key"],
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": script,
                "model_id": config["model_id"],
                "voice_settings": {
                    "stability": 0.6,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                },
            },
        )

        if resp.status_code != 200:
            detail = resp.text[:500]
            logger.error("ElevenLabs API error %d: %s", resp.status_code, detail)
            raise RuntimeError(
                f"ElevenLabs API returned {resp.status_code}: {detail}"
            )

        return resp.content


async def narrate_report_offline(report: ReportJSON) -> str:
    """
    Offline fallback: returns the text script that would be narrated.
    Used when ELEVENLABS_API_KEY is not set (demo mode).
    """
    return _build_script(report)
