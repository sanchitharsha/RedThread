"""
Stub CPSC connector — returns fixture data when USE_STUBS=1.
M2 replaces this file with the real CPSC API client.
Signature MUST stay: def fetch_recall(ref: str) -> RecallRecord
"""
from __future__ import annotations

from contracts.models import RecallRecord, RecallScope


def fetch_recall(ref: str) -> RecallRecord:
    """
    Stub: returns a fake RecallRecord with obviously placeholder data.
    Real implementation calls the CPSC API.
    """
    return RecallRecord(
        authority="CPSC",
        recall_number=ref or "PLACEHOLDER-RECALL-000",
        title="PLACEHOLDER Recall Title — Not Real Data",
        description="PLACEHOLDER recall description. This is stub data.",
        url=f"https://www.cpsc.gov/Recalls/PLACEHOLDER/{ref or 'PLACEHOLDER'}",
        brand="PLACEHOLDER-BRAND",
        product_name="PLACEHOLDER Widget",
        models=["MODEL-AAA"],
        gtins=["0000000000000"],
        hazard="PLACEHOLDER hazard: risk of PLACEHOLDER injury.",
        remedy="PLACEHOLDER remedy: contact manufacturer for PLACEHOLDER.",
        units_affected="PLACEHOLDER units",
        scope=RecallScope(kind="all_units", description="All units"),
        manufacture_dates="",
        sold_at=["PLACEHOLDER-STORE"],
        images=[],
        source_tier="A",
        raw={"_stub": True},
    )
