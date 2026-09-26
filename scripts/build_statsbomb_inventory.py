"""Build complete StatsBomb competition/team coverage from local metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

# Keep this script directly runnable from a source checkout without requiring an
# editable package install.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.data import StatsBombOpenDataAdapter, statsbomb_team_coverage


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="external_data/statsbomb_open_data")
    parser.add_argument("--json-output", default="artifacts/statsbomb_inventory_v1.json")
    parser.add_argument("--report-output", default="docs/statsbomb_open_data_inventory.md")
    options = parser.parse_args()

    adapter = StatsBombOpenDataAdapter(options.root)
    competitions, matches = adapter.competitions(), adapter.matches()
    asset_coverage = adapter.repository_asset_coverage()
    teams = statsbomb_team_coverage(adapter)
    match_team_rows = pd.concat([
        matches[["match_id", "home_team_id", "home_team_name"]].rename(columns={"home_team_id": "team_id", "home_team_name": "team"}),
        matches[["match_id", "away_team_id", "away_team_name"]].rename(columns={"away_team_id": "team_id", "away_team_name": "team"}),
    ], ignore_index=True)
    global_teams = match_team_rows.groupby(["team_id", "team"]).agg(matches_available=("match_id", "nunique")).reset_index()
    for threshold in (5, 10, 20):
        global_teams[f"at_least_{threshold}_matches"] = global_teams.matches_available.ge(threshold)
    global_teams = global_teams.sort_values(["matches_available", "team"], ascending=[False, True], kind="stable").reset_index(drop=True)

    competition_seasons = teams.groupby(["competition_id", "competition_name", "season_id", "season_name"]).agg(
        matches_available=("matches_available", lambda values: int(values.sum() / 2)),
        teams_available=("team_id", "nunique"),
        teams_at_least_5=("at_least_5_matches", "sum"),
        teams_at_least_10=("at_least_10_matches", "sum"),
        teams_at_least_20=("at_least_20_matches", "sum"),
        matches_with_360=("matches_with_360", lambda values: int(values.sum() / 2)),
    ).reset_index().sort_values(["matches_available", "competition_name", "season_name"], ascending=[False, True, True], kind="stable")

    summary = {
        "competition_seasons": int(len(competitions)),
        "matches": int(matches.match_id.nunique()),
        "teams": int(global_teams.team_id.nunique()),
        "matches_with_events": int(matches.has_events.sum()),
        "matches_with_lineups": int(matches.has_lineups.sum()),
        "matches_with_360_snapshots": int(matches.has_360_snapshots.sum()),
        "matches_with_continuous_tracking": 0,
        "competition_team_seasons_at_least_5": int(teams.at_least_5_matches.sum()),
        "competition_team_seasons_at_least_10": int(teams.at_least_10_matches.sum()),
        "competition_team_seasons_at_least_20": int(teams.at_least_20_matches.sum()),
        "global_teams_at_least_5": int(global_teams.at_least_5_matches.sum()),
        "global_teams_at_least_10": int(global_teams.at_least_10_matches.sum()),
        "global_teams_at_least_20": int(global_teams.at_least_20_matches.sum()),
    }
    for row in asset_coverage.itertuples(index=False):
        key = str(row.asset_type).replace("-", "_")
        summary[f"repository_{key}_blobs"] = int(row.repository_blobs)
        summary[f"unindexed_{key}_blobs"] = int(row.unindexed_blobs)
    payload = {
        "schema_version": "tactiq.statsbomb-inventory.v1", "provider": "statsbomb_open_data",
        "capabilities": {"has_events": True, "has_lineups": True, "has_360_snapshots": "per_match", "has_continuous_tracking": False},
        "summary": summary, "competitions": _records(competitions),
        "asset_coverage": _records(asset_coverage),
        "competition_seasons": _records(competition_seasons),
        "competition_season_teams": _records(teams), "global_teams": _records(global_teams),
    }
    json_path = Path(options.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    top_competitions = competition_seasons.head(20)[["competition_name", "season_name", "matches_available", "teams_available", "teams_at_least_5", "teams_at_least_10", "teams_at_least_20", "matches_with_360"]]
    top_teams = teams.head(30)[["competition_name", "season_name", "team", "matches_available", "matches_with_360", "at_least_5_matches", "at_least_10_matches", "at_least_20_matches"]]
    report = f"""# StatsBomb Open Data canonical-ingestion inventory

**Schema:** `tactiq.statsbomb-inventory.v1`  
**Provider:** `statsbomb_open_data`

## Canonical boundary

- Events: available for {summary['matches_with_events']:,} matches.
- Lineups: available for {summary['matches_with_lineups']:,} matches.
- 360 snapshots: available for {summary['matches_with_360_snapshots']:,} matches and stored only as event-linked snapshots.
- Continuous tracking: **not available** and always declared `False`.
- StatsBomb's 120 x 80 locations retain explicit `statsbomb_120x80` coordinate provenance; they are not labelled as metres.

## Coverage summary

| Measure | Count |
| --- | ---: |
| Competition-season datasets | {summary['competition_seasons']:,} |
| Matches | {summary['matches']:,} |
| Distinct team IDs | {summary['teams']:,} |
| Competition-season-team samples with 5+ matches | {summary['competition_team_seasons_at_least_5']:,} |
| Competition-season-team samples with 10+ matches | {summary['competition_team_seasons_at_least_10']:,} |
| Competition-season-team samples with 20+ matches | {summary['competition_team_seasons_at_least_20']:,} |
| Global teams with 5+ matches | {summary['global_teams_at_least_5']:,} |
| Global teams with 10+ matches | {summary['global_teams_at_least_10']:,} |
| Global teams with 20+ matches | {summary['global_teams_at_least_20']:,} |

## Repository asset audit

{_table(asset_coverage)}

The official Git tree contains {summary['unindexed_events_blobs']:,} event and
lineup blobs that are not present in the current match metadata index. They are
reported here but excluded from competition/team coverage because their team
and competition identity cannot be resolved authoritatively from the configured
metadata.

## Largest competition-season datasets

{_table(top_competitions)}

## Largest team samples within one competition-season

{_table(top_teams)}

## Local checkout configuration

The official repository is configured as a partial clone at `{Path(options.root)}`. All competition and match metadata are materialized for complete coverage counts. Representative match `3764440` includes events, lineups, and 360; match `9880` includes events and lineups without 360. Other event/lineup blobs remain available from the official Git tree and can be materialized on demand without changing the adapter.

This report proves ingestion and coverage only. It adds no tactical metrics and makes no claim that sparse 360 freeze frames form a continuous trajectory.
"""
    report_path = Path(options.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    print(f"json={json_path} report={report_path}")


if __name__ == "__main__":
    main()
