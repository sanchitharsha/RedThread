import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["OFFLINE"] = "1"
os.environ.setdefault("FIXTURES_DIR", str(ROOT / "fixtures"))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from matching import capture_index
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "llm_cache"))
    monkeypatch.setenv("OFFLINE", "1")
    capture_index.clear()
    yield
    capture_index.clear()
