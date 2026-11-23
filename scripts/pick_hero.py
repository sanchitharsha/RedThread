"""List recent CPSC recalls that have several model numbers AND UPCs: hero-recall candidates.

    python scripts/pick_hero.py [--days 365] [--min-models 2] [--min-upcs 1] [--limit 20]

Needs network. Prints number, date, title, counts and URL; pick one, then run
    python -m matching.connectors.cpsc <number> --fields --save-sample
and agree the hero with the other three leads.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matching.connectors import cpsc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--min-models", type=int, default=2)
    ap.add_argument("--min-upcs", type=int, default=1)
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()
    end, start = date.today(), date.today() - timedelta(days=a.days)
    data, last = None, None
    for params in ({"RecallDateStart": start.isoformat(), "RecallDateEnd": end.isoformat()},
                   {"LastPublishDateStart": start.isoformat(), "LastPublishDateEnd": end.isoformat()}):
        try:
            data = cpsc.http_get_json(params)
            if data:
                print(f"query params that worked: {list(params)}")
                break
        except Exception as exc:  # noqa: BLE001
            last = exc
    if not data:
        print(f"No data (network blocked or parameter names wrong): {last}", file=sys.stderr)
        return 1
    rows = []
    for rec in data:
        r = cpsc.map_record(rec)
        from matching.normalise import gtin_ok
        valid = [g for g in r.gtins if gtin_ok(g)]
        if len(r.models) >= a.min_models and len(valid) >= a.min_upcs:
            rows.append((len(r.models) + len(valid), r, len(valid)))
    rows.sort(key=lambda t: -t[0])
    print(f"{len(data)} recalls scanned, {len(rows)} candidates\n")
    for _, r, nv in rows[:a.limit]:
        print(f"{r.number}  {r.date}  models={len(r.models)} valid_upcs={nv} scope={r.scope_type}\n   {r.title}\n   {r.url}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
