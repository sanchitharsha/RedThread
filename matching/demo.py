"""python -m matching.demo [--ref REF] [--captures DIR] [--shop-url URL] [--notice FILE]

Fetch the hero recall (live, or fixtures when OFFLINE=1 / no network), read saved sandbox page
texts from fixtures/captures/*.txt, extract with the configured LLM, rate, print tiers + reasons.
LLM_PROVIDER=fake runs the regex stand-in (no key needed; NOT a model). Blocked-looking pages
(bot check) are marked blocked here only because there is no browser; M1's capture does this for real.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from contracts.models import PageCapture
from matching.connectors.cpsc import fetch_recall
from matching.extract import enrich_recall, extract_listings
from matching.llm import get_llm
from matching.match import annotate_dropped, rate
from matching import capture_index as ci

BLOCK_RX = re.compile(r"verify you are human|captcha|unusual traffic|are you a robot", re.I)


def load_captures(d: Path, shop_url: str) -> list[PageCapture]:
    caps = []
    for p in sorted(d.glob("*.txt")):
        if p.name.startswith("_"):
            continue
        text = p.read_text(errors="replace")
        blocked = bool(BLOCK_RX.search(text))
        caps.append(PageCapture(url=f"{shop_url.rstrip('/')}/listings/{p.stem}.html", title=p.stem,
                                fetched_at=datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc),
                                text=text, status="blocked" if blocked else "ok",
                                block_reason="bot-check wording on page" if blocked else None))
    return caps


async def main_async(a) -> int:
    logging.basicConfig(level=logging.WARNING)
    recall = fetch_recall(a.ref)
    print(f"RECALL  {recall.authority}:{recall.number}  tier={recall.source_tier}\n  {recall.title}\n"
          f"  brand={recall.brand!r} models={recall.models} gtins={recall.gtins}\n"
          f"  scope={recall.scope_type} {recall.scope_from or ''}..{recall.scope_to or ''}\n  raw_ref={recall.raw_ref}")
    if "PLACEHOLDER" in recall.raw_ref:
        print("\n  *** PLACEHOLDER RECALL DATA: NOT A REAL RECALL. Save the real one first. ***")
    llm = get_llm()
    if a.notice:
        n = PageCapture(url=recall.url, fetched_at=datetime.now(timezone.utc), text=Path(a.notice).read_text(),
                        source_tier="A")
        recall = await enrich_recall(recall, n, llm)
        print(f"\nENRICHED from notice: models={recall.models} gtins={recall.gtins} scope={recall.scope_type}")
    d = Path(a.captures)
    caps = load_captures(d, a.shop_url) if d.exists() else []
    if not caps:
        print(f"\nNo page texts in {d}/ (M4 saves fixtures/captures/<id>.txt). Save one by hand and rerun.",
              file=sys.stderr)
        return 1
    print(f"\n{'LISTING':<12}{'TIER':<11}REASONS")
    counts: dict[str, int] = {}
    for cap in caps:
        for l in await extract_listings(cap, llm):
            r = annotate_dropped(rate(l, recall))
            counts[r.tier] = counts.get(r.tier, 0) + 1
            print(f"{r.listing_id:<12}{r.tier:<11}{', '.join(r.reasons) or '-'}")
            for e in r.evidence[:3]:
                print(f"{'':<23}evidence[{e.source_tier}] {'ok ' if e.quote_verified else 'UNVERIFIED '}{e.quote[:70]!r}")
    print("\nCOUNTS", counts, "\nNo match found in checked sources is not a statement about product safety.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=os.getenv("RECALL_REF", "hero"))
    ap.add_argument("--captures", default="fixtures/captures")
    ap.add_argument("--shop-url", default=os.getenv("SHOP_URL", "http://localhost:8001"))
    ap.add_argument("--notice", help="optional saved text of the official notice page (enrich_recall)")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
