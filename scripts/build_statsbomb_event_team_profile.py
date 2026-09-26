"""Build one StatsBomb event-based team-season profile from canonical bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import (
    aggregate_event_team_match_metrics, calculate_event_team_match_metrics,
)
from src.data import StatsBombOpenDataAdapter


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _markdown(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in frame.itertuples(index=False, name=None):
        values = [f"{value:.3f}" if isinstance(value, float) else str(value) for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="external_data/statsbomb_open_data")
    parser.add_argument("--team", default="Barcelona")
    parser.add_argument("--competition-id", type=int, default=11)
    parser.add_argument("--season-id", type=int, default=27)
    parser.add_argument("--output", default="artifacts/statsbomb_barcelona_2015_2016_event_profile_v1.json")
    parser.add_argument("--report", default="docs/statsbomb_barcelona_2015_2016_event_profile.md")
    options = parser.parse_args()

    adapter = StatsBombOpenDataAdapter(options.root)
    identity = adapter.resolve_team(options.team)
    matches = identity["matches"]
    selected = matches.loc[
        matches.competition_id.eq(options.competition_id) & matches.season_id.eq(options.season_id)
    ].sort_values(["match_date", "match_id"], kind="stable")
    if selected.empty:
        raise ValueError("No matches found for the requested team/competition/season.")

    compact_rows, load_exclusions = [], []
    total = len(selected)
    for number, match in enumerate(selected.itertuples(index=False), start=1):
        try:
            bundle = adapter.load_match(int(match.match_id))
            match_metrics = calculate_event_team_match_metrics(bundle)
            selected_team = match_metrics.loc[match_metrics.team_id.eq(identity["team_id"])]
            if len(selected_team) != 1:
                raise ValueError("resolved team does not have exactly one match metric row")
            compact_rows.append(selected_team.iloc[0].to_dict())
            del bundle, match_metrics, selected_team
            print(f"[{number}/{total}] loaded match {match.match_id}", flush=True)
        except Exception as error:
            load_exclusions.append({"match_id": int(match.match_id), "reason": str(error)})
            print(f"[{number}/{total}] skipped match {match.match_id}: {error}", flush=True)

    profile = aggregate_event_team_match_metrics(
        pd.DataFrame(compact_rows), team_id=identity["team_id"],
        team_name=identity["team_name"], competition_id=options.competition_id,
        season_id=options.season_id,
        matches_excluded=pd.DataFrame(load_exclusions, columns=["match_id", "reason"]),
    )
    exclusions = profile.matches_excluded
    metadata = selected.iloc[0]
    payload = {
        "schema_version": "tactiq.event-team-profile.v1",
        "provider": "statsbomb_open_data",
        "team": {"team_id": profile.team_id, "team_name": profile.team_name},
        "competition": {"competition_id": options.competition_id, "competition_name": metadata.competition_name},
        "season": {"season_id": options.season_id, "season_name": metadata.season_name},
        "matches_discovered": int(total), "matches_included": int(len(profile.match_metrics)),
        "matches_excluded": _records(exclusions),
        "coordinate_system": "statsbomb_120x80",
        "definitions": _records(profile.definitions),
        "match_metrics": _records(profile.match_metrics),
        "aggregate_metrics": _records(profile.aggregate_metrics),
    }
    output = Path(options.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    headline = (
        "possession_share_estimate", "passes_attempted", "pass_completion_rate",
        "progressive_passes", "passes_into_final_third", "passes_into_penalty_area",
        "carries", "progressive_carries", "shots", "shots_on_target", "goals", "xg",
        "average_shot_distance", "open_play_shots", "set_play_shots", "pressures",
        "tackles", "interceptions", "recoveries", "high_regains",
        "turnovers_leading_to_shot", "counter_attack_shots",
    )
    summary = profile.aggregate_metrics.loc[profile.aggregate_metrics.metric.isin(headline), [
        "metric", "unit", "median_across_matches", "q25_across_matches",
        "q75_across_matches", "contributing_matches", "coverage",
    ]]
    rate_names = {f"{metric}_per90" for metric in headline} | {"xg_per90"}
    per90 = profile.aggregate_metrics.loc[profile.aggregate_metrics.metric.isin(rate_names), [
        "metric", "unit", "median_across_matches", "q25_across_matches",
        "q75_across_matches", "contributing_matches", "coverage",
    ]]
    report = f"""# {profile.team_name} event tactical profile — {metadata.competition_name} {metadata.season_name}

**Provider:** StatsBomb Open Data  
**Coordinate provenance:** `statsbomb_120x80` (not metres)  
**Matches discovered:** {total}  
**Matches included:** {len(profile.match_metrics)}  
**Matches excluded:** {len(exclusions)}

Every observation is first calculated within one match. The table then reports
the median and quartiles across matches; individual events are never pooled as
historical evidence. Raw counts and `_per90` fields are separate in the JSON artifact.

## Match-weighted headline metrics

{_markdown(summary)}

## Match-weighted per-90 metrics

{_markdown(per90)}

## Definitions and limitations

{_markdown(profile.definitions.loc[profile.definitions.metric.isin(headline)])}

Possession share is explicitly an event-timeline estimate. Transition reporting
is restricted to StatsBomb's explicit `From Counter` play pattern. No tactical
recommendations or generated interpretations are included.
"""
    report_path = Path(options.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({"matches_discovered": total, "matches_included": len(profile.match_metrics), "matches_excluded": len(exclusions)}), flush=True)
    print(f"artifact={output} report={report_path}", flush=True)


if __name__ == "__main__":
    main()
