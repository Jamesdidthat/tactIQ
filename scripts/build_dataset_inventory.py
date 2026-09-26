"""Generate TactIQ's local dataset inventory and provider expansion plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.analysis import build_dataset_inventory


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.columns:
        if display[column].dtype == bool:
            display[column] = display[column].map({True: "Yes", False: "No"})
    headers = [str(column) for column in display.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skillcorner-root", default="opendata/data/matches")
    parser.add_argument("--metrica-root", default="external_data/metrica")
    parser.add_argument("--statsbomb-root", default="external_data/statsbomb_open_data")
    parser.add_argument("--json-output", default="artifacts/dataset_inventory_v1.json")
    parser.add_argument("--report-output", default="docs/dataset_inventory_and_provider_expansion.md")
    options = parser.parse_args()

    result = build_dataset_inventory(
        skillcorner_root=options.skillcorner_root, metrica_root=options.metrica_root,
        statsbomb_root=options.statsbomb_root,
    )
    payload = {
        "schema_version": "tactiq.dataset-inventory.v1",
        "match_teams": _records(result.match_teams),
        "teams": _records(result.teams),
        "providers": _records(result.providers),
        "prospective_providers": _records(result.prospective_providers),
    }
    json_path = Path(options.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    requested = [
        "provider", "competition", "season", "team", "matches_available",
        "matches_team_profile_ready", "has_continuous_tracking", "has_verified_roles",
        "has_attacking_direction", "has_events", "has_tactical_phases",
        "has_lineups", "has_360_snapshots",
        "canonical_adapter_can_process_today",
    ]
    provider_table = result.providers.rename(columns={
        "has_continuous_tracking_matches": "continuous tracking",
        "has_ball_tracking_matches": "ball tracking",
        "has_verified_roles_matches": "verified roles",
        "has_attacking_direction_matches": "attacking direction",
        "has_events_matches": "events",
        "has_tactical_phases_matches": "phases",
    })
    max_valid = int(result.teams.matches_team_profile_ready.max()) if not result.teams.empty else 0
    stable_teams = int(result.teams.matches_team_profile_ready.ge(5).sum()) if not result.teams.empty else 0
    report = f"""# Dataset inventory and provider expansion plan

**Inventory schema:** `tactiq.dataset-inventory.v1`

This inventory distinguishes raw match availability, canonical-adapter readiness, and the stricter period-consistent readiness required by the current Team Profile. It does not add tactical metrics or infer unavailable provider capabilities.

## Provider coverage

{_markdown_table(provider_table)}

## Team coverage

{_markdown_table(result.teams[requested])}

## Current exclusions

{_markdown_table(result.match_teams.loc[result.match_teams.exclusion_reason.notna(), ["provider", "match_id", "team", "canonical_adapter_ready", "exclusion_reason"]])}

## Capability-limited but processable matches

{_markdown_table(result.match_teams.loc[result.match_teams.capability_limitations.notna(), ["provider", "match_id", "team", "capability_limitations"]])}

## Expansion decision

- Highest current Team Profile-ready match count for one team: **{max_valid}**.
- Teams with at least five profile-ready matches: **{stable_teams}**.
- SkillCorner remains the only locally configured source with verified roles, events, tactical phases, and continuous tracking together.
- Metrica validates the provider-independent tracking contract, but its one sample match lacks verified roles and mapped canonical events/phases, so it cannot expand stable team profiles.
- StatsBomb Open Data is configured as an event provider. Its 360 data remains explicitly snapshot-based and cannot be presented as continuous tracking.

**Planning conclusion:** the local repository cannot currently reach the 5-10 match range for any team. External data acquisition is the next bottleneck. The fastest useful expansion is either more period-consistent SkillCorner matches for repeated teams or a separately capability-labelled event-profile track from a multi-match event provider.
"""
    report_path = Path(options.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"json={json_path} report={report_path} teams={len(result.teams)} max_profile_ready={max_valid} teams_at_least_5={stable_teams}")


if __name__ == "__main__":
    main()
