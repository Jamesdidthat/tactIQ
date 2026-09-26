"""Audit local StatsBomb Open Data 360 readiness without changing analysis rules."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis.moment_patterns import classify_moment_patterns
from src.analysis.representative_moments import RepresentativeMoment, _event_mask
from src.data import StatsBombOpenDataAdapter


FAMILIES = (
    "penalty_area_entries", "final_third_entries", "shots", "interceptions",
    "high_regains", "counter_attacks", "set_play_shots",
)
CURRENT_MINIMUM = 3
STRONGER_THRESHOLDS = (5, 10)


def _record(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        **identity, "event_match_ids": set(), "snapshot_match_ids": set(),
        "eligible_event_ids": set(), "aligned_event_ids": set(),
        "families": {family: {
            "eligible": 0, "aligned": 0, "event_patterns": Counter(),
            "aligned_patterns": Counter(),
        } for family in FAMILIES},
    }


def _moment(row: dict[str, Any], shot_median: float | None) -> RepresentativeMoment:
    relevant = {
        "xg": row["shot_xg"], "start_coordinates": row["start_coordinates"],
        "end_coordinates": row["end_coordinates"], "play_pattern": row["play_pattern"],
        "shot_type": row["shot_type"], "shot_outcome": row["shot_outcome"],
    }
    if shot_median is not None:
        relevant["team_season_shot_xg_distribution"] = {"median": shot_median}
    return RepresentativeMoment(
        match_id=row["match_id"], team_id=row["team_id"], team_name=row["team_name"],
        opponent_id="audit", opponent_name="audit", match_date=row["match_date"],
        minute=row["minute"], second=row["second"], period=row["period"],
        event_id=row["event_id"], event_type=row["event_type"], metric=row["family"],
        family=row["family"], description="Audit event.", relevant_values=relevant,
        score_state=None, score_state_verified=False, score_state_team_id=row["team_id"],
        score_state_team_name=row["team_name"], source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable", reason_selected="coverage_audit",
        evidence_side="team_history",
    )


def _family_output(family: str, values: dict[str, Any]) -> dict[str, Any]:
    eligible, aligned = values["eligible"], values["aligned"]
    aligned_patterns = dict(sorted(values["aligned_patterns"].items()))
    return {
        "family": family,
        "eligible_event_moments": eligible,
        "aligned_360_moments": aligned,
        "alignment_coverage": aligned / eligible if eligible else 0.0,
        "event_pattern_counts": dict(sorted(values["event_patterns"].items())),
        "aligned_360_pattern_counts": aligned_patterns,
        "patterns_meeting_threshold_3": sum(count >= CURRENT_MINIMUM for count in aligned_patterns.values()),
        "patterns_meeting_threshold_5": sum(count >= 5 for count in aligned_patterns.values()),
        "patterns_meeting_threshold_10": sum(count >= 10 for count in aligned_patterns.values()),
    }


def _finalize(record: dict[str, Any]) -> dict[str, Any]:
    families = [_family_output(family, record["families"][family]) for family in FAMILIES]
    event_matches = len(record["event_match_ids"])
    snapshot_matches = len(record["snapshot_match_ids"])
    eligible = len(record["eligible_event_ids"])
    aligned = len(record["aligned_event_ids"])
    patterns_3 = sum(row["patterns_meeting_threshold_3"] for row in families)
    patterns_5 = sum(row["patterns_meeting_threshold_5"] for row in families)
    patterns_10 = sum(row["patterns_meeting_threshold_10"] for row in families)
    stable = snapshot_matches >= 5 and (aligned / eligible if eligible else 0.0) >= .25 and patterns_10 >= 3
    excluded = {"event_match_ids", "snapshot_match_ids", "eligible_event_ids", "aligned_event_ids", "families"}
    return {
        **{key: value for key, value in record.items() if key not in excluded},
        "matches_with_events": event_matches,
        "matches_with_any_360": snapshot_matches,
        "match_360_percentage": snapshot_matches / event_matches if event_matches else 0.0,
        "distinct_eligible_event_moments": eligible,
        "distinct_aligned_360_moments": aligned,
        "distinct_moment_alignment_coverage": aligned / eligible if eligible else 0.0,
        "patterns_meeting_threshold_3": patterns_3,
        "patterns_meeting_threshold_5": patterns_5,
        "patterns_meeting_threshold_10": patterns_10,
        "stable_pattern_context_ready": stable,
        "family_coverage": families,
    }


def build_audit(root: Path) -> dict[str, Any]:
    adapter = StatsBombOpenDataAdapter(root)
    matches = adapter.matches().sort_values(["competition_id", "season_id", "match_date", "match_id"], kind="stable")
    materialized_event_ids = {int(path.stem) for path in (root / "data" / "events").glob("*.json")}
    materialized_snapshot_ids = {int(path.stem) for path in (root / "data" / "three-sixty").glob("*.json")}
    indexed_ids = set(matches.match_id.astype(int))
    readable_event_ids = materialized_event_ids & indexed_ids
    readable_snapshot_ids = materialized_snapshot_ids & indexed_ids
    competition_records: dict[tuple[int, int], dict[str, Any]] = {}
    team_records: dict[tuple[int, int, int], dict[str, Any]] = {}
    for match in matches.itertuples(index=False):
        competition_key = (int(match.competition_id), int(match.season_id))
        competition_records.setdefault(competition_key, _record({
            "competition_id": competition_key[0], "competition_name": str(match.competition_name),
            "season_id": competition_key[1], "season_name": str(match.season_name),
        }))
        for team_id, team_name in ((match.home_team_id, match.home_team_name), (match.away_team_id, match.away_team_name)):
            team_key = (*competition_key, int(team_id))
            team_records.setdefault(team_key, _record({
                "competition_id": competition_key[0], "competition_name": str(match.competition_name),
                "season_id": competition_key[1], "season_name": str(match.season_name),
                "team_id": int(team_id), "team_name": str(team_name),
            }))

    eligible_rows: list[dict[str, Any]] = []
    shot_xg: dict[tuple[int, int, int], list[float]] = {}
    event_matches = matches.loc[matches.match_id.isin(readable_event_ids)]
    for match in event_matches.itertuples(index=False):
        competition_key = (int(match.competition_id), int(match.season_id))
        events = adapter._events(int(match.match_id))  # Canonical adapter mapping; audit avoids lineup requirements.
        snapshots = adapter._snapshots(int(match.match_id)) if int(match.match_id) in readable_snapshot_ids else None
        aligned_ids = set() if snapshots is None or snapshots.empty else set(snapshots.event_id.astype(str))
        has_actual_360 = bool(aligned_ids)
        competition_records[competition_key]["event_match_ids"].add(int(match.match_id))
        if has_actual_360:
            competition_records[competition_key]["snapshot_match_ids"].add(int(match.match_id))
        for team_id, team_name in ((match.home_team_id, match.home_team_name), (match.away_team_id, match.away_team_name)):
            team_key = (*competition_key, int(team_id))
            team_record = team_records[team_key]
            team_record["event_match_ids"].add(int(match.match_id))
            if has_actual_360:
                team_record["snapshot_match_ids"].add(int(match.match_id))
            team_shots = events.loc[events.team_id.eq(team_id) & events.event_type.eq("Shot"), "shot_xg"].dropna()
            shot_xg.setdefault(team_key, []).extend(float(value) for value in team_shots)
            for family in FAMILIES:
                selected = events.loc[_event_mask(events, family, team_id)]
                for event in selected.itertuples(index=False):
                    start = None if pd.isna(event.location_x) or pd.isna(event.location_y) else [float(event.location_x), float(event.location_y)]
                    end = None if pd.isna(event.end_location_x) or pd.isna(event.end_location_y) else [float(event.end_location_x), float(event.end_location_y)]
                    eligible_rows.append({
                        "competition_key": competition_key, "team_key": team_key,
                        "match_id": int(match.match_id), "match_date": str(match.match_date),
                        "team_id": int(team_id), "team_name": str(team_name), "family": family,
                        "event_id": str(event.event_id), "event_type": str(event.event_type),
                        "minute": int(event.minute), "second": int(event.second), "period": int(event.period),
                        "start_coordinates": start, "end_coordinates": end,
                        "play_pattern": None if pd.isna(event.play_pattern) else str(event.play_pattern),
                        "shot_type": None if pd.isna(event.shot_type) else str(event.shot_type),
                        "shot_outcome": None if pd.isna(event.shot_outcome) else str(event.shot_outcome),
                        "shot_xg": None if pd.isna(event.shot_xg) else float(event.shot_xg),
                        "aligned": str(event.event_id) in aligned_ids,
                    })

    medians = {key: float(pd.Series(values).median()) for key, values in shot_xg.items() if values}
    for row in eligible_rows:
        keys = classify_moment_patterns(_moment(row, medians.get(row["team_key"])))
        for record_key, records in ((row["competition_key"], competition_records), (row["team_key"], team_records)):
            record = records[record_key]
            record["eligible_event_ids"].add(row["event_id"])
            record["families"][row["family"]]["eligible"] += 1
            record["families"][row["family"]]["event_patterns"].update(keys)
            if row["aligned"]:
                record["aligned_event_ids"].add(row["event_id"])
                record["families"][row["family"]]["aligned"] += 1
                record["families"][row["family"]]["aligned_patterns"].update(keys)

    teams = [_finalize(team_records[key]) for key in sorted(team_records)]
    competitions = [_finalize(competition_records[key]) for key in sorted(competition_records)]
    stable_by_competition = Counter(
        (row["competition_id"], row["season_id"]) for row in teams if row["stable_pattern_context_ready"]
    )
    for row in competitions:
        row["team_seasons_stable_pattern_context_ready"] = stable_by_competition[(row["competition_id"], row["season_id"])]

    def ranking(row):
        return (-row["patterns_meeting_threshold_10"], -row["distinct_aligned_360_moments"], -row["match_360_percentage"], row.get("team_name", row["competition_name"]))

    ranked_teams = sorted((row for row in teams if row["matches_with_events"] > 0), key=ranking)
    ranked_competitions = sorted((row for row in competitions if row["matches_with_events"] > 0), key=ranking)
    suitable = [row for row in ranked_teams if row["stable_pattern_context_ready"]][:10]
    pilot = [row for row in ranked_teams if row["matches_with_any_360"] > 0][:10]
    family_totals = []
    for family in FAMILIES:
        rows = [next(item for item in row["family_coverage"] if item["family"] == family) for row in competitions]
        eligible = sum(row["eligible_event_moments"] for row in rows)
        aligned = sum(row["aligned_360_moments"] for row in rows)
        family_totals.append({
            "family": family, "eligible_event_moments": eligible, "aligned_360_moments": aligned,
            "alignment_coverage": aligned / eligible if eligible else 0.0,
            "competition_season_patterns_meeting_3": sum(row["patterns_meeting_threshold_3"] for row in rows),
            "competition_season_patterns_meeting_5": sum(row["patterns_meeting_threshold_5"] for row in rows),
            "competition_season_patterns_meeting_10": sum(row["patterns_meeting_threshold_10"] for row in rows),
        })
    asset_rows = adapter.repository_asset_coverage().to_dict("records")
    return {
        "schema_version": "statsbomb_360_readiness_v1",
        "audit_date": date.today().isoformat(), "provider": "statsbomb_open_data",
        "repository_root": str(root.resolve()),
        "configuration": {
            "current_spatial_summary_minimum": CURRENT_MINIMUM,
            "stronger_audit_thresholds": list(STRONGER_THRESHOLDS),
            "stable_team_season_definition": {
                "minimum_matches_with_360": 5, "minimum_distinct_alignment_coverage": .25,
                "minimum_family_pattern_combinations_with_at_least_10_aligned_examples": 3,
                "note": "Audit-only readiness definition; it does not change product thresholds.",
            },
        },
        "repository": {
            "indexed_matches": int(len(matches)), "matches_with_events": int(len(readable_event_ids)),
            "matches_with_any_360": int(sum(row["matches_with_any_360"] for row in competitions)),
            "competition_seasons": len(competitions), "team_seasons": len(teams),
            "stable_team_seasons": sum(row["stable_pattern_context_ready"] for row in teams),
            "materialized_event_blobs": len(materialized_event_ids),
            "materialized_indexed_event_blobs": len(readable_event_ids),
            "materialized_360_blobs": len(materialized_snapshot_ids),
            "materialized_indexed_360_blobs": len(readable_snapshot_ids),
            "git_tree_asset_coverage": asset_rows,
        },
        "family_totals": family_totals,
        "competition_seasons": competitions, "team_seasons": teams,
        "rankings": {
            "competition_seasons": ranked_competitions,
            "team_seasons": ranked_teams,
        },
        "validation_shortlist": {
            "suitable_team_seasons": suitable,
            "suitable_count": len(suitable),
            "best_available_nonqualifying_pilots": pilot,
            "note": "No 5-10 item shortlist is fabricated when fewer team-seasons satisfy the explicit readiness definition.",
        },
        "limitations": [
            "Only physically materialized blobs available in the local repository checkout are audited; Git tree promises are reported separately and are not treated as readable data.",
            "Events from matches without a local 360 blob are never treated as spatially observed.",
            "Pattern thresholds count family-plus-pattern combinations and may overlap because moment labels can be multi-label.",
            "StatsBomb 360 is partial event-linked visible-area context, not continuous tracking.",
        ],
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    repository = audit["repository"]
    lines = [
        "# StatsBomb 360 coverage and product-readiness audit", "",
        f"Audit date: {audit['audit_date']}", "",
        "## Outcome", "",
        f"The local checkout contains **{repository['matches_with_events']} event-enabled matches** but only **{repository['matches_with_any_360']} match with an actual 360 snapshot file**. No team-season satisfies the conservative stable-pattern-context readiness definition.", "",
        "The current product minimum remains **3 aligned 360 examples per pattern**. Thresholds of 5 and 10 are audit comparisons only.", "",
        "## Repository coverage", "",
        "| Metric | Count |", "|---|---:|",
        f"| Indexed matches | {repository['indexed_matches']} |",
        f"| Matches with events | {repository['matches_with_events']} |",
        f"| Matches with any 360 | {repository['matches_with_any_360']} |",
        f"| Materialized event blobs | {repository['materialized_event_blobs']} |",
        f"| Materialized 360 blobs | {repository['materialized_360_blobs']} |",
        f"| Competition-seasons | {repository['competition_seasons']} |",
        f"| Team-seasons | {repository['team_seasons']} |",
        f"| Stable 360 team-seasons | {repository['stable_team_seasons']} |", "",
        "The partial clone's Git tree advertises additional blobs, but they are not counted as usable because they are not locally readable without hydration.", "",
        "## Coverage by supported moment family", "",
        "| Family | Eligible events | Aligned 360 | Coverage | Pattern groups N>=3 | N>=5 | N>=10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit["family_totals"]:
        lines.append(f"| {row['family'].replace('_', ' ').title()} | {row['eligible_event_moments']} | {row['aligned_360_moments']} | {_pct(row['alignment_coverage'])} | {row['competition_season_patterns_meeting_3']} | {row['competition_season_patterns_meeting_5']} | {row['competition_season_patterns_meeting_10']} |")
    lines.extend(["", "## Best-supported competition-seasons", "", "| Rank | Competition-season | Event matches | 360 matches | Match coverage | Aligned moments | Alignment | Patterns N>=3 / 5 / 10 | Stable team-seasons |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|"])
    for rank, row in enumerate(audit["rankings"]["competition_seasons"][:10], 1):
        lines.append(f"| {rank} | {row['competition_name']} - {row['season_name']} | {row['matches_with_events']} | {row['matches_with_any_360']} | {_pct(row['match_360_percentage'])} | {row['distinct_aligned_360_moments']} | {_pct(row['distinct_moment_alignment_coverage'])} | {row['patterns_meeting_threshold_3']} / {row['patterns_meeting_threshold_5']} / {row['patterns_meeting_threshold_10']} | {row['team_seasons_stable_pattern_context_ready']} |")
    lines.extend(["", "## Best-supported team-seasons", "", "| Rank | Team-season | Event matches | 360 matches | Match coverage | Aligned moments | Alignment | Patterns N>=3 / 5 / 10 | Ready |", "|---:|---|---:|---:|---:|---:|---:|---:|---|"])
    for rank, row in enumerate(audit["rankings"]["team_seasons"][:10], 1):
        lines.append(f"| {rank} | {row['team_name']} - {row['competition_name']} {row['season_name']} | {row['matches_with_events']} | {row['matches_with_any_360']} | {_pct(row['match_360_percentage'])} | {row['distinct_aligned_360_moments']} | {_pct(row['distinct_moment_alignment_coverage'])} | {row['patterns_meeting_threshold_3']} / {row['patterns_meeting_threshold_5']} / {row['patterns_meeting_threshold_10']} | {'Yes' if row['stable_pattern_context_ready'] else 'No'} |")
    shortlist = audit["validation_shortlist"]
    lines.extend(["", "## Product-validation shortlist", ""])
    if shortlist["suitable_team_seasons"]:
        for row in shortlist["suitable_team_seasons"]:
            lines.append(f"- {row['team_name']} - {row['competition_name']} {row['season_name']}")
    else:
        lines.extend([
            "**No team-season in the local checkout is suitable for stable 360 pattern-context validation.** A requested 5-10 item shortlist cannot be produced honestly from one 360-enabled match.", "",
            "Best available single-match pilots (not stable team-season validation):",
        ])
        for row in shortlist["best_available_nonqualifying_pilots"]:
            lines.append(f"- {row['team_name']} - {row['competition_name']} {row['season_name']}: {row['matches_with_any_360']}/{row['matches_with_events']} matches with 360, {_pct(row['distinct_moment_alignment_coverage'])} event-moment alignment.")
    lines.extend(["", "## Readiness definition and limitations", "", "A team-season is marked stable only with at least five 360-enabled matches, at least 25% distinct eligible-event alignment, and at least three family-pattern combinations containing ten aligned examples. This is an audit-only definition and does not change the current product minimum of three.", ""])
    for limitation in audit["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(["", "The JSON artifact contains exhaustive competition-season, team-season, and family-level records. Spatial coverage is never extrapolated from matches without 360.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("external_data/statsbomb_open_data"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/statsbomb_360_readiness.json"))
    parser.add_argument("--markdown", type=Path, default=Path("docs/statsbomb_360_readiness.md"))
    options = parser.parse_args()
    result = build_audit(options.root)
    options.json.parent.mkdir(parents=True, exist_ok=True)
    options.markdown.parent.mkdir(parents=True, exist_ok=True)
    options.json.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    write_markdown(result, options.markdown)
    print(json.dumps({
        "matches_with_events": result["repository"]["matches_with_events"],
        "matches_with_360": result["repository"]["matches_with_any_360"],
        "stable_team_seasons": result["repository"]["stable_team_seasons"],
        "suitable_shortlist": result["validation_shortlist"]["suitable_count"],
    }, indent=2))
