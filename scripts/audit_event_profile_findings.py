"""Write a compact review report for a persisted event team profile."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import (
    assemble_match_story, build_match_archetypes, build_metric_relationship_deviations,
    generate_event_profile_findings,
)
from src.api import load_event_profile_artifact


def table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(f"{value:.3f}" if isinstance(value, float) else str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default="artifacts/statsbomb_barcelona_2015_2016_event_profile_v1.json")
    parser.add_argument("--report", default="docs/statsbomb_barcelona_2015_2016_event_findings.md")
    options = parser.parse_args()
    result = generate_event_profile_findings(load_event_profile_artifact(options.artifact))
    archetypes = build_match_archetypes(result)
    relationships = build_metric_relationship_deviations(result.profile)
    relationship_findings = pd.DataFrame([asdict(item) for item in relationships.findings])
    # This match contains all three evidence sources and therefore makes the
    # relationship -> archetype -> single-metric product hierarchy auditable.
    story_match_id = 266961
    story = assemble_match_story(result, story_match_id)
    story_rows = pd.DataFrame([{
        "story_type": item.story_type, "title": item.title,
        "metrics": ", ".join(metric["metric"] for metric in item.supporting_metrics),
        "evidence_level": item.evidence_level, "priority_score": item.priority_score,
        "selection_reason": item.selection_reason,
    } for item in story.story_points])
    findings = pd.DataFrame([asdict(finding) for finding in result.findings])
    top = findings.head(20)[[
        "source_match_id", "finding_family", "title", "observed_value", "season_baseline",
        "signed_deviation", "relative_deviation", "robust_z_score", "evidence_level",
        "contributing_match_count", "coverage",
    ]] if not findings.empty else findings
    report = f"""# Event Profile Finding audit

**Team:** {result.profile.team_name}  
**Matches:** {len(result.profile.match_metrics)}  
**Findings emitted:** {len(result.findings)}  
**Correlated duplicates suppressed:** {len(result.suppressed_duplicates)}  
**Threshold:** absolute robust z >= 1.5, N >= 10, coverage >= 80%  
**Archetype rule:** every component must reach signed robust z >= 0.75, N >= 10, and coverage >= 80%; labels may overlap.

## Rule-based match archetypes

{table(archetypes.season_summary)}

## Recurring families

{table(result.recurring_tendencies)}

## Metric relationships

{table(relationships.relationship_fits[["upstream_metric", "downstream_metric", "slope", "intercept", "spearman_rank_correlation", "slope_leave_one_out_low", "slope_leave_one_out_high", "residual_robust_scale", "contributing_match_count", "coverage"]])}

## Match Story example — {story_match_id}

{table(story_rows)}

## Unusual relationship residuals

{table(relationship_findings[["match_id", "title", "upstream_value", "observed_downstream_value", "expected_downstream_value", "residual", "residual_robust_z", "evidence_level"]]) if not relationship_findings.empty else "No residual passed the robust threshold."}

## Strongest deviations

{table(top)}

Robust scale is `IQR / 1.349`, with scaled MAD only when IQR is zero. Titles are
descriptive and do not classify observations as positive or negative.
"""
    path = Path(options.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"findings={len(result.findings)} suppressed={len(result.suppressed_duplicates)} report={path}")


if __name__ == "__main__":
    main()
