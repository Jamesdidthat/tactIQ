"""Local provider inventory and expansion-readiness planning."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from src.data import (
    StatsBombOpenDataAdapter, load_metrica_sample_game,
    preflight_skillcorner_phase_periods,
)


CAPABILITY_COLUMNS = [
    "has_continuous_tracking", "has_ball_tracking", "has_verified_roles",
    "has_attacking_direction", "has_events", "has_tactical_phases",
    "has_lineups", "has_360_snapshots",
]


@dataclass
class DatasetInventoryResult:
    match_teams: pd.DataFrame
    teams: pd.DataFrame
    providers: pd.DataFrame
    prospective_providers: pd.DataFrame


def _skillcorner_rows(matches_root: Path) -> list[dict]:
    rows = []
    required_suffixes = (
        "_match.json", "_tracking_extrapolated.jsonl", "_dynamic_events.csv",
        "_phases_of_play.csv",
    )
    for directory in sorted(path for path in matches_root.iterdir() if path.is_dir()):
        match_id = directory.name
        metadata_path = directory / f"{match_id}_match.json"
        required = [directory / f"{match_id}{suffix}" for suffix in required_suffixes]
        if not metadata_path.is_file():
            continue
        info = json.loads(metadata_path.read_text(encoding="utf-8"))
        edition = info.get("competition_edition") or {}
        competition = (edition.get("competition") or {}).get("name") or edition.get("name") or "Unknown"
        season = (edition.get("season") or {}).get("name") or "Unknown"
        adapter_ready = all(path.is_file() for path in required)
        issue = preflight_skillcorner_phase_periods(directory) if adapter_ready else "required source files are missing"
        roles = [((player.get("player_role") or {}).get("name")) for player in info.get("players", [])]
        capabilities = {
            "has_continuous_tracking": required[1].is_file(),
            "has_ball_tracking": required[1].is_file(),
            "has_verified_roles": bool(roles) and all(roles),
            "has_attacking_direction": bool(info.get("home_team_side")),
            "has_events": required[2].is_file(),
            "has_tactical_phases": required[3].is_file(),
            "has_lineups": False,
            "has_360_snapshots": False,
        }
        for team in (info.get("home_team") or {}, info.get("away_team") or {}):
            rows.append({
                "provider": "skillcorner_open_data", "competition": competition,
                "season": season, "match_id": int(match_id), "team_id": team.get("id"),
                "team": team.get("name") or team.get("acronym") or str(team.get("id")),
                "canonical_adapter_ready": adapter_ready,
                "team_profile_ready": adapter_ready and issue is None,
                "exclusion_reason": issue,
                "capability_limitations": None,
                **capabilities,
            })
    return rows


def _metrica_rows(metrica_root: Path) -> list[dict]:
    rows = []
    for directory in sorted(path for path in metrica_root.iterdir() if path.is_dir()):
        try:
            bundle = load_metrica_sample_game(directory, frame_stride=1000)
            match_id = bundle.matches.match_id.iloc[0]
            capabilities = {
                column: bool(getattr(bundle.capabilities, column))
                for column in CAPABILITY_COLUMNS
            }
            for team in bundle.teams.itertuples(index=False):
                rows.append({
                    "provider": bundle.provider, "competition": "Metrica Public Sample",
                    "season": "Unspecified", "match_id": match_id,
                    "team_id": team.team_id,
                    "team": bundle.match_info["home_team" if team.home_away == "home" else "away_team"]["name"],
                    "canonical_adapter_ready": True,
                    "team_profile_ready": True,
                    "exclusion_reason": None,
                    "capability_limitations": "verified roles, events, and tactical phases are unavailable",
                    **capabilities,
                })
        except Exception as error:
            rows.append({
                "provider": "metrica_public_sample", "competition": "Metrica Public Sample",
                "season": "Unspecified", "match_id": directory.name,
                "team_id": "unknown", "team": "Unknown",
                "canonical_adapter_ready": False, "team_profile_ready": False,
                "exclusion_reason": str(error),
                "capability_limitations": None,
                **{column: False for column in CAPABILITY_COLUMNS},
            })
    return rows


def _statsbomb_rows(statsbomb_root: Path) -> list[dict]:
    adapter = StatsBombOpenDataAdapter(statsbomb_root)
    rows = []
    for match in adapter.matches().itertuples(index=False):
        capabilities = {
            "has_continuous_tracking": False, "has_ball_tracking": False,
            "has_verified_roles": False, "has_attacking_direction": False,
            "has_events": bool(match.has_events), "has_tactical_phases": False,
            "has_lineups": bool(match.has_lineups),
            "has_360_snapshots": bool(match.has_360_snapshots),
        }
        for team_id, team in (
            (match.home_team_id, match.home_team_name),
            (match.away_team_id, match.away_team_name),
        ):
            rows.append({
                "provider": "statsbomb_open_data", "competition": match.competition_name,
                "season": match.season_name, "match_id": match.match_id,
                "team_id": team_id, "team": team,
                "canonical_adapter_ready": bool(match.has_events and match.has_lineups),
                "team_profile_ready": False, "exclusion_reason": None,
                "capability_limitations": "event-oriented data; no continuous tracking or tactical phases",
                **capabilities,
            })
    return rows


def build_dataset_inventory(
    *,
    skillcorner_root: str | Path = "opendata/data/matches",
    metrica_root: str | Path = "external_data/metrica",
    statsbomb_root: str | Path = "external_data/statsbomb_open_data",
) -> DatasetInventoryResult:
    """Inventory all locally configured matches without computing tactical metrics."""
    rows = []
    skillcorner_path, metrica_path, statsbomb_path = Path(skillcorner_root), Path(metrica_root), Path(statsbomb_root)
    if skillcorner_path.is_dir():
        rows.extend(_skillcorner_rows(skillcorner_path))
    if metrica_path.is_dir():
        rows.extend(_metrica_rows(metrica_path))
    if (statsbomb_path / "data" / "competitions.json").is_file():
        rows.extend(_statsbomb_rows(statsbomb_path))
    match_teams = pd.DataFrame(rows)
    if match_teams.empty:
        empty = pd.DataFrame()
        return DatasetInventoryResult(empty, empty, empty, pd.DataFrame())

    team_keys = ["provider", "competition", "season", "team_id", "team"]
    aggregations = {
        "matches_available": ("match_id", "nunique"),
        "matches_canonical_adapter_ready": ("canonical_adapter_ready", "sum"),
        "matches_team_profile_ready": ("team_profile_ready", "sum"),
        "canonical_adapter_can_process_today": ("canonical_adapter_ready", "all"),
    }
    aggregations.update({column: (column, "all") for column in CAPABILITY_COLUMNS})
    teams = match_teams.groupby(team_keys, dropna=False).agg(**aggregations).reset_index()
    teams = teams.sort_values(
        ["matches_team_profile_ready", "matches_available", "provider", "team"],
        ascending=[False, False, True, True], kind="stable",
    ).reset_index(drop=True)

    provider_rows = []
    for provider, group in match_teams.groupby("provider"):
        matches = group.drop_duplicates("match_id")
        record = {
            "provider": provider,
            "matches_available": int(matches.match_id.nunique()),
            "teams_available": int(group.team_id.nunique()),
            "matches_canonical_adapter_ready": int(matches.canonical_adapter_ready.sum()),
            "matches_team_profile_ready": int(matches.team_profile_ready.sum()),
        }
        for column in CAPABILITY_COLUMNS:
            record[f"{column}_matches"] = int(matches[column].sum())
        provider_rows.append(record)
    providers = pd.DataFrame(provider_rows).sort_values("provider").reset_index(drop=True)
    prospective = pd.DataFrame([] if (statsbomb_path / "data" / "competitions.json").is_file() else [
        {
            "provider": "statsbomb_open_data", "configured_locally": False,
            "adapter_available": False,
            "planning_note": "Prospective event-profile source; 360 is snapshot-based, not continuous tracking.",
        }
    ])
    return DatasetInventoryResult(match_teams, teams, providers, prospective)
