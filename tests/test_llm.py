import asyncio

import pytest
from pydantic import BaseModel

from matching import llm as L
from matching.schemas import ListingExtractionOut


class Out(BaseModel):
    answer: str


class Counting(L._Base):
    provider = "counting"

    def __init__(self, fail_times=0, exc=None):
        super().__init__("m1")
        self.n = 0
        self.fail_times, self.exc = fail_times, exc

    async def _raw_json(self, system, user, schema):
        self.n += 1
        if self.n <= self.fail_times:
            raise self.exc
        return Out(answer=f"a{self.n}").model_dump_json()


class RateLimit(Exception):
    status_code = 429


def run(c):
    return asyncio.run(c)


def test_cache_hit_and_key_sensitivity():
    m = Counting()
    a = run(m.complete_json("s", "u", Out))
    b = run(m.complete_json("s", "u", Out))
    assert a == b and m.n == 1
    run(m.complete_json("s", "u2", Out))
    run(m.complete_json("s2", "u", Out))
    assert m.n == 3
    other = Counting(); other.model = "m2"
    run(other.complete_json("s", "u", Out))
    assert other.n == 1                                   # different model -> different key


def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "0")
    m = Counting()
    run(m.complete_json("s", "u", Out)); run(m.complete_json("s", "u", Out))
    assert m.n == 2


def test_retry_with_backoff_on_rate_limit(monkeypatch):
    delays = []

    async def fake_sleep(d):
        delays.append(d)
    monkeypatch.setattr(L, "_sleep", fake_sleep)
    m = Counting(fail_times=3, exc=RateLimit("slow down"))
    assert run(m.complete_json("s", "u", Out)).answer == "a4"
    assert len(delays) == 3 and delays[0] < delays[1] < delays[2]      # exponential


def test_non_retryable_error_raises_immediately(monkeypatch):
    monkeypatch.setattr(L, "_sleep", lambda d: asyncio.sleep(0))
    m = Counting(fail_times=5, exc=ValueError("bad request"))
    with pytest.raises(ValueError):
        run(m.complete_json("s", "u", Out))
    assert m.n == 1


def test_retries_exhausted(monkeypatch):
    monkeypatch.setattr(L, "_sleep", lambda d: asyncio.sleep(0))
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    m = Counting(fail_times=99, exc=RateLimit("x"))
    with pytest.raises(RateLimit):
        run(m.complete_json("s", "u", Out))
    assert m.n == 3


def test_invalid_json_is_validated():
    class Bad(Counting):
        async def _raw_json(self, *a):
            return '{"wrong": 1}'
    with pytest.raises(Exception):
        run(Bad().complete_json("s", "u", Out))


def test_normalise_tools_accepts_both_shapes_and_adds_reason():
    flat = {"name": "open_url", "description": "d", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}
    oa = {"type": "function", "function": {"name": "back", "description": "b"}}
    out = L.normalise_tools([flat, oa])
    assert [t["name"] for t in out] == ["open_url", "back"]
    assert all("reason" in t["parameters"]["properties"] for t in out)
    assert "reason" not in flat["parameters"]["properties"]            # input not mutated


def test_fake_llm_validates_and_records():
    f = L.FakeLLM(script={Out: {"answer": "x", "junk": 1}})
    assert run(f.complete_json("s", "u", Out)).answer == "x" and f.calls[0][0] == "Out"
    act = L.FakeLLM(actions=[{"name": "read_page", "args": {}, "reason": "r"}])
    assert run(act.choose_action("s", "o", [], [{"name": "read_page"}]))["name"] == "read_page"
    assert run(act.choose_action("s", "o", [], []))["name"] == "finish"


def test_get_llm_selection_and_errors(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.chdir("/tmp")                                  # no .env here
    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        L.get_llm()
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    assert isinstance(L.get_llm(), L.FakeLLM)
    monkeypatch.setenv("LLM_PROVIDER", "openai"); monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        L.get_llm()
    monkeypatch.setenv("LLM_MODEL", "some-model"); monkeypatch.setenv("OPENAI_API_KEY", "x")
    o = L.get_llm()
    assert isinstance(o, L.OpenAILLM) and o.model == "some-model"
    monkeypatch.setenv("LLM_PROVIDER", "gemini"); monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert isinstance(L.get_llm(), L.GeminiLLM)


def test_provider_request_shapes_build_offline():
    """No network: just prove the SDK objects we hand to the providers construct."""
    from google.genai import types
    tools = L.normalise_tools([{"name": "open_url", "description": "d",
                                "parameters": {"type": "object", "properties": {"url": {"type": "string"}}}}])
    types.FunctionDeclaration(name=tools[0]["name"], description=tools[0]["description"],
                              parameters_json_schema=tools[0]["parameters"])
    types.GenerateContentConfig(temperature=0, response_mime_type="application/json", response_schema=ListingExtractionOut)
    types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
    types.AutomaticFunctionCallingConfig(disable=True)
