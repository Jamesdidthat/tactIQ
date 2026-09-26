"""Capture shortlisted explanation outputs and their EvidencePacks for product QA."""

from __future__ import annotations

import json
from pathlib import Path

from src.ai import TacticalExplanationService, explanation_provider_from_environment
from src.api import MatchAnalysisService
from src.data import load_skillcorner_match


ROOT = Path(__file__).resolve().parents[1]
MATCH_ID = "2017461"


def main() -> None:
    service = MatchAnalysisService(
        {MATCH_ID: load_skillcorner_match(ROOT / "opendata" / "data" / "matches" / MATCH_ID)},
        explanation_service=TacticalExplanationService(explanation_provider_from_environment()),
    )
    ranked = service.get_ranked_findings(MATCH_ID)["ranked_findings"]
    records = []
    for finding in ranked[:6]:
        finding_id = finding["finding_id"]
        records.append({
            "rank": finding["rank"],
            "finding": finding,
            "evidence": service.get_finding_detail(MATCH_ID, finding_id)["evidence"],
            "explanation": service.get_finding_explanation(MATCH_ID, finding_id),
        })

    output = ROOT / "artifacts" / "ui_review" / "explanation_qa_inputs_2017461.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    sources = {source: sum(item["explanation"]["metadata"]["source"] == source for item in records) for source in {item["explanation"]["metadata"]["source"] for item in records}}
    print(f"Captured {len(records)} shortlisted findings to {output}")
    print(f"Explanation sources: {sources}")


if __name__ == "__main__":
    main()
