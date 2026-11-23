"""Fail if forbidden wording appears in UI source. Run via `make test`.

Forbidden: "safe", "verified safe", "not recalled", "no recall" (whole words, any case).
Scans frontend/src, sandbox/templates and sandbox/build.py. A line is exempt only if it
contains the marker  wording-allow  (used for the planted injection text on L09).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(r"\b(verified\s+safe|not\s+recalled|no\s+recall|safe)\b", re.IGNORECASE)
TARGETS = [ROOT / "frontend" / "src", ROOT / "sandbox" / "templates", ROOT / "sandbox" / "build.py"]
EXTS = {".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".py", ".json", ".md"}


def files():
    for t in TARGETS:
        if t.is_file():
            yield t
        elif t.is_dir():
            yield from (p for p in t.rglob("*") if p.suffix in EXTS and "node_modules" not in p.parts)


def main() -> int:
    bad = []
    for f in files():
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "wording-allow" in line:
                continue
            m = FORBIDDEN.search(line)
            if m:
                bad.append(f"{f.relative_to(ROOT)}:{n}: forbidden word {m.group(0)!r}: {line.strip()[:90]}")
    if bad:
        print("\n".join(bad))
        print(f"\ncheck_wording: FAILED ({len(bad)} problem(s))")
        return 1
    print("check_wording: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
