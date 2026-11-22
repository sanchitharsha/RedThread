"""
LLM provider factory.
M2 owns the real implementation; this stub satisfies the contract.
Signature MUST stay: def get_llm() -> LLM
"""
from __future__ import annotations

import os
from contracts.models import LLM


class _StubLLM:
    """A no-op LLM for USE_STUBS=1 mode. Satisfies the LLM protocol."""

    async def generate(
        self, prompt: str, *, system: str = "", json_mode: bool = False
    ) -> str:
        return '{"_stub": true, "note": "PLACEHOLDER LLM response"}'


class _GeminiLLM:
    """Thin wrapper around google.genai. Real impl by M2."""

    def __init__(self) -> None:
        try:
            from google import genai  # type: ignore
            api_key = os.environ.get("GEMINI_API_KEY", "")
            self._client = genai.Client(api_key=api_key)
            self._model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
        except ImportError as exc:
            raise ImportError("google-genai is required for Gemini provider") from exc

    async def generate(
        self, prompt: str, *, system: str = "", json_mode: bool = False
    ) -> str:
        # Synchronous call wrapped for the protocol
        config: dict = {}
        if system:
            config["system_instruction"] = system
        if json_mode:
            config["response_mime_type"] = "application/json"
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config if config else None,
        )
        return response.text or ""


class _OpenAILLM:
    """Thin wrapper around openai. Real impl by M2."""

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI  # type: ignore
            self._client = AsyncOpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", "")
            )
            self._model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        except ImportError as exc:
            raise ImportError("openai is required for OpenAI provider") from exc

    async def generate(
        self, prompt: str, *, system: str = "", json_mode: bool = False
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict = {"model": self._model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


def get_llm() -> LLM:
    """Return an LLM instance based on LLM_PROVIDER env var."""
    provider = os.environ.get("LLM_PROVIDER", "stub").lower()
    if provider == "gemini":
        return _GeminiLLM()  # type: ignore[return-value]
    elif provider == "openai":
        return _OpenAILLM()  # type: ignore[return-value]
    else:
        return _StubLLM()  # type: ignore[return-value]
