"""Deterministic offline LLM double for unit and integration tests.

Implements the shared `LLM` protocol (`choose_action`) without requiring any
network call or API key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Responder = Callable[
    [str, str, list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]
]


class FakeLLM:
    """Offline LLM stub returning a scripted action sequence (or responder output)."""

    def __init__(
        self,
        actions: list[dict[str, Any]] | None = None,
        *,
        responder: Responder | None = None,
    ) -> None:
        self._actions: list[dict[str, Any]] = list(actions or [])
        self._responder = responder
        self._index = 0
        self.calls: list[dict[str, Any]] = []

    async def choose_action(
        self,
        system: str,
        observation: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system": system,
                "observation": observation,
                "history": list(history),
                "tools": list(tools),
            }
        )
        if self._responder is not None:
            return self._responder(system, observation, history, tools)
        if self._index < len(self._actions):
            action = self._actions[self._index]
            self._index += 1
            return action
        return {
            "name": "finish",
            "args": {"findings": "FakeLLM action sequence completed."},
            "reason": "Scripted offline action sequence exhausted.",
        }
