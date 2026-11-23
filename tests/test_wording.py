"""Rule 2: matching/ never writes the forbidden status words in strings or comments."""
import re
from pathlib import Path

FORBIDDEN = [r"\bsafe\b", r"verified\s+safe", r"not\s+recalled", r"no\s+recall\b"]


def test_no_forbidden_wording_in_matching_sources():
    bad = []
    for p in (Path(__file__).resolve().parents[1] / "matching").rglob("*.py"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for rx in FORBIDDEN:
                if re.search(rx, line, re.I):
                    bad.append(f"{p.name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)
