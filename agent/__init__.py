"""Redthread M1 Browser Agent & Web Tooling package."""

from agent.agent import investigate
from agent.browser import BrowserSession, capture_page, detect_block, infer_source_tier
from agent.fake_llm import FakeLLM
from agent.guard import GuardError, check_url, guard, wrap_untrusted
from agent.observe import MAX_OBSERVATION_CHARS, PageObservation, build_observation
from agent.playbooks import build_system_prompt, get_tool_schemas

__all__ = [
    "BrowserSession",
    "FakeLLM",
    "GuardError",
    "MAX_OBSERVATION_CHARS",
    "PageObservation",
    "build_observation",
    "build_system_prompt",
    "capture_page",
    "check_url",
    "detect_block",
    "get_tool_schemas",
    "guard",
    "infer_source_tier",
    "investigate",
    "wrap_untrusted",
]
