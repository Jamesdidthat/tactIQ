"""Provider-independent adapter for StatsBomb Open Data events and 360 snapshots."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

import pandas as pd

from .canonical import CanonicalMatchBundle, ProviderCapabilities, validate_canonical_bundle


STATSBOMB_PROVIDER = "statsbomb_open_data"
STATSBOMB_EVENT_COORDINATE_SYSTEM = "statsbomb_120x80"


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class StatsBombOpenDataAdapter:
    """Lazy reader for an official StatsBomb Open Data checkout.

    360 freeze frames are event-linked anonymous spatial snapshots. They are
    deliberately returned in ``event_snapshots`` and never in continuous
    ``player_positions``.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.data_root = self.root / "data"
        if not (self.data_root / "competitions.json").is_file():
            raise FileNotFoundError("StatsBomb data/competitions.json was not found.")
        self._matches: pd.DataFrame | None = None
        self._tree_ids: dict[str, set[int]] = {}

    def competitions(self) -> pd.DataFrame:
        rows = []
        for item in _json(self.data_root / "competitions.json"):
            rows.append({
                "provider": STATSBOMB_PROVIDER,
                "competition_id": item["competition_id"], "season_id": item["season_id"],
                "country_name": item.get("country_name"), "competition_name": item.get("competition_name"),
                "competition_gender": item.get("competition_gender"),
                "competition_youth": item.get("competition_youth"),
                "competition_international": item.get("competition_international"),
                "season_name": item.get("season_name"),
                "match_available": item.get("match_available"),
                "match_available_360": item.get("match_available_360"),
            })
        result = pd.DataFrame(rows)
        if result.duplicated(["competition_id", "season_id"]).any():
            raise ValueError("StatsBomb competitions contain duplicate competition-season keys.")
        return result

    def _repository_ids(self, kind: str) -> set[int]:
        if kind in self._tree_ids:
            return self._tree_ids[kind]
        local = {int(path.stem) for path in (self.data_root / kind).glob("*.json")} if (self.data_root / kind).is_dir() else set()
        git_dir = self.root / ".git"
        if git_dir.exists():
            command = [
                "git", "-c", f"safe.directory={self.root.resolve().as_posix()}",
                "-C", str(self.root), "ls-tree", "-r", "--name-only", "HEAD",
                f"data/{kind}",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode == 0:
                local.update(
                    int(Path(line).stem) for line in completed.stdout.splitlines()
                    if line.endswith(".json") and Path(line).stem.isdigit()
                )
        self._tree_ids[kind] = local
        return local

    def matches(self) -> pd.DataFrame:
        if self._matches is not None:
            return self._matches.copy()
        event_ids = self._repository_ids("events")
        lineup_ids = self._repository_ids("lineups")
        snapshot_ids = self._repository_ids("three-sixty")
        rows = []
        for path in sorted((self.data_root / "matches").glob("*/*.json")):
            for item in _json(path):
                competition, season = item["competition"], item["season"]
                rows.append({
                    "provider": STATSBOMB_PROVIDER, "match_id": item["match_id"],
                    "match_date": item.get("match_date"), "kick_off": item.get("kick_off"),
                    "competition_id": competition["competition_id"],
                    "competition_name": competition["competition_name"],
                    "country_name": competition.get("country_name"),
                    "season_id": season["season_id"], "season_name": season["season_name"],
                    "home_team_id": item["home_team"]["home_team_id"],
                    "home_team_name": item["home_team"]["home_team_name"],
                    "away_team_id": item["away_team"]["away_team_id"],
                    "away_team_name": item["away_team"]["away_team_name"],
                    "home_score": item.get("home_score"), "away_score": item.get("away_score"),
                    "competition_stage": (item.get("competition_stage") or {}).get("name"),
                    "has_events": item["match_id"] in event_ids,
                    "has_lineups": item["match_id"] in lineup_ids,
                    "has_360_snapshots": item["match_id"] in snapshot_ids,
                })
        result = pd.DataFrame(rows)
        if result.empty or result.match_id.duplicated().any():
            raise ValueError("StatsBomb match inventory is empty or contains duplicate match IDs.")
        self._matches = result
        return result.copy()

    def repository_asset_coverage(self) -> pd.DataFrame:
        """Audit official data blobs against the current match metadata index.

        The upstream repository can retain historical event/lineup blobs whose
        match metadata is no longer listed. They remain visible in this audit,
        but are not assigned to a competition or team without authoritative
        match metadata.
        """
        match_ids = set(self.matches().match_id.astype(int))
        rows = []
        for kind in ("events", "lineups", "three-sixty"):
            asset_ids = self._repository_ids(kind)
            rows.append({
                "asset_type": kind,
                "repository_blobs": len(asset_ids),
                "indexed_matches": len(asset_ids & match_ids),
                "unindexed_blobs": len(asset_ids - match_ids),
                "indexed_matches_missing_blob": len(match_ids - asset_ids),
            })
        return pd.DataFrame(rows)

    def resolve_team(self, team: str | int) -> dict:
        matches = self.matches()
        if isinstance(team, int) or str(team).isdigit():
            team_id = int(team)
            selected = matches.loc[matches.home_team_id.eq(team_id) | matches.away_team_id.eq(team_id)]
            names = pd.concat([
                selected.loc[selected.home_team_id.eq(team_id), "home_team_name"],
                selected.loc[selected.away_team_id.eq(team_id), "away_team_name"],
            ]).dropna()
        else:
            normalized = str(team).strip().casefold()
            selected = matches.loc[
                matches.home_team_name.str.casefold().eq(normalized)
                | matches.away_team_name.str.casefold().eq(normalized)
            ]
            identifiers = pd.concat([
                selected.loc[selected.home_team_name.str.casefold().eq(normalized), "home_team_id"],
                selected.loc[selected.away_team_name.str.casefold().eq(normalized), "away_team_id"],
            ]).dropna().unique()
            if len(identifiers) != 1:
                raise KeyError(f"StatsBomb team name {team!r} is absent or ambiguous.")
            team_id = int(identifiers[0])
            names = pd.Series([str(team)])
        if selected.empty:
            raise KeyError(f"StatsBomb team {team!r} was not found.")
        return {
            "provider": STATSBOMB_PROVIDER, "team_id": team_id,
            "team_name": names.mode().iloc[0],
            "match_ids": tuple(sorted(int(value) for value in selected.match_id.unique())),
            "matches": selected.sort_values(["match_date", "match_id"], kind="stable").reset_index(drop=True),
        }

    def _match_row(self, match_id: int) -> pd.Series:
        selected = self.matches().loc[lambda frame: frame.match_id.eq(int(match_id))]
        if len(selected) != 1:
            raise KeyError(f"StatsBomb match {match_id!r} was not found.")
        return selected.iloc[0]

    def _asset_json(self, kind: str, match_id: int) -> Any:
        """Read a materialized asset or lazily hydrate it from the partial clone."""
        relative = Path("data") / kind / f"{match_id}.json"
        path = self.root / relative
        if path.is_file():
            return _json(path)
        if match_id not in self._repository_ids(kind):
            raise FileNotFoundError(f"StatsBomb {kind} data is unavailable for match {match_id}.")
        command = [
            "git", "-c", f"safe.directory={self.root.resolve().as_posix()}",
            "-C", str(self.root), "show", f"HEAD:{relative.as_posix()}",
        ]
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise FileNotFoundError(
                f"StatsBomb {kind} blob for match {match_id} could not be read from the configured clone: {detail}"
            )
        return json.loads(completed.stdout.decode("utf-8"))

    def _lineups(self, match_id: int) -> pd.DataFrame:
        rows = []
        for team in self._asset_json("lineups", match_id):
            for player in team.get("lineup", []):
                positions = player.get("positions") or []
                position_names = [item.get("position") for item in positions if item.get("position")]
                rows.append({
                    "match_id": match_id, "player_id": player["player_id"], "team_id": team["team_id"],
                    "player_name": player.get("player_name"), "player_nickname": player.get("player_nickname"),
                    "player_number": player.get("jersey_number"),
                    "position": position_names[0] if position_names else pd.NA,
                    "position_group": pd.NA,
                    "is_goalkeeper": "Goalkeeper" in position_names,
                    "position_history": positions,
                })
        roster = pd.DataFrame(rows)
        if roster.duplicated(["match_id", "player_id"]).any():
            raise ValueError("StatsBomb lineup contains duplicate player IDs within a match.")
        return roster

    def _events(self, match_id: int) -> pd.DataFrame:
        rows = []
        for event in self._asset_json("events", match_id):
            location = event.get("location") or [None, None]
            event_type = (event.get("type") or {}).get("name")
            detail = event.get(event_type.lower().replace(" ", "_"), {}) if event_type else {}
            end_location = detail.get("end_location") or [None, None]
            rows.append({
                "match_id": match_id, "event_id": event["id"], "event_index": event.get("index"),
                "period": event.get("period"), "timestamp": event.get("timestamp"),
                "minute": event.get("minute"), "second": event.get("second"),
                "elapsed_seconds": (event.get("minute") or 0) * 60 + (event.get("second") or 0),
                "team_id": (event.get("team") or {}).get("id"),
                "player_id": (event.get("player") or {}).get("id"),
                "event_type": event_type, "event_type_id": (event.get("type") or {}).get("id"),
                "possession_id": event.get("possession"),
                "possession_team_id": (event.get("possession_team") or {}).get("id"),
                "play_pattern": (event.get("play_pattern") or {}).get("name"),
                "duration": event.get("duration"), "location_x": location[0], "location_y": location[1],
                "end_location_x": end_location[0], "end_location_y": end_location[1],
                "outcome": (detail.get("outcome") or {}).get("name"),
                "shot_xg": (event.get("shot") or {}).get("statsbomb_xg"),
                "shot_outcome": ((event.get("shot") or {}).get("outcome") or {}).get("name"),
                "shot_type": ((event.get("shot") or {}).get("type") or {}).get("name"),
                "pass_outcome": ((event.get("pass") or {}).get("outcome") or {}).get("name"),
                "duel_type": ((event.get("duel") or {}).get("type") or {}).get("name"),
                "ball_recovery_failure": (event.get("ball_recovery") or {}).get("recovery_failure", False),
                "is_shot": event_type == "Shot",
                "coordinate_system": STATSBOMB_EVENT_COORDINATE_SYSTEM,
                "attributes": {key: value for key, value in event.items() if key in {"pass", "shot", "carry", "dribble", "duel", "clearance", "interception", "ball_recovery"}},
            })
        events = pd.DataFrame(rows)
        if events.event_id.duplicated().any():
            raise ValueError("StatsBomb events contain duplicate event IDs.")
        return events

    def _snapshots(self, match_id: int) -> pd.DataFrame | None:
        if match_id not in self._repository_ids("three-sixty"):
            return None
        rows = []
        for snapshot in self._asset_json("three-sixty", match_id):
            freeze_frame = snapshot.get("freeze_frame") or []
            for index, player in enumerate(freeze_frame):
                location = player.get("location") or [None, None]
                rows.append({
                    "match_id": match_id, "event_id": snapshot["event_uuid"],
                    "snapshot_player_index": index, "teammate": player.get("teammate"),
                    "actor": player.get("actor"), "keeper": player.get("keeper"),
                    "location_x": location[0], "location_y": location[1],
                    "visible_area": snapshot.get("visible_area"),
                    "coordinate_system": STATSBOMB_EVENT_COORDINATE_SYSTEM,
                })
        return pd.DataFrame(rows)

    def load_match(self, match_id: int) -> CanonicalMatchBundle:
        match = self._match_row(match_id)
        roster = self._lineups(int(match_id))
        events = self._events(int(match_id))
        snapshots = self._snapshots(int(match_id)) if bool(match.has_360_snapshots) else None
        teams = pd.DataFrame([
            {"match_id": match_id, "team_id": match.home_team_id, "team_code": match.home_team_name, "team_name": match.home_team_name, "home_away": "home"},
            {"match_id": match_id, "team_id": match.away_team_id, "team_code": match.away_team_name, "team_name": match.away_team_name, "home_away": "away"},
        ])
        match_info = {
            "id": match_id, "provider": STATSBOMB_PROVIDER,
            "competition": match.competition_name, "season": match.season_name,
            "home_team": {"id": match.home_team_id, "name": match.home_team_name, "acronym": match.home_team_name},
            "away_team": {"id": match.away_team_id, "name": match.away_team_name, "acronym": match.away_team_name},
            "event_coordinate_system": STATSBOMB_EVENT_COORDINATE_SYSTEM,
        }
        capabilities = ProviderCapabilities(
            has_continuous_tracking=False, has_ball_tracking=False,
            has_verified_roles=False, has_attacking_direction=False,
            has_events=True, has_tactical_phases=False, has_lineups=True,
            has_360_snapshots=snapshots is not None,
        )
        bundle = CanonicalMatchBundle(
            provider=STATSBOMB_PROVIDER, match_info=match_info,
            matches=pd.DataFrame([{
                "match_id": match_id, "pitch_length_m": pd.NA, "pitch_width_m": pd.NA,
                "event_pitch_length": 120.0, "event_pitch_width": 80.0,
                "event_coordinate_system": STATSBOMB_EVENT_COORDINATE_SYSTEM,
                "match_date": match.match_date, "competition_id": match.competition_id,
                "season_id": match.season_id,
                "home_team_id": match.home_team_id, "home_team_name": match.home_team_name,
                "away_team_id": match.away_team_id, "away_team_name": match.away_team_name,
                "home_score": match.home_score, "away_score": match.away_score,
            }]),
            teams=teams, roster=roster,
            player_positions=_empty(["match_id", "frame", "period", "elapsed_seconds", "player_id", "team_id", "x", "y"]),
            ball_positions=_empty(["match_id", "frame", "period", "elapsed_seconds", "ball_x", "ball_y"]),
            attacking_directions=_empty(["match_id", "period", "team_id", "attacking_x_sign"]),
            events=events, tactical_phases=None, event_snapshots=snapshots,
            capabilities=capabilities,
            raw={"source_root": str(self.root), "events_are_continuous_tracking": False},
        )
        validate_canonical_bundle(bundle)
        validate_statsbomb_bundle(bundle)
        return bundle


def validate_statsbomb_bundle(bundle: CanonicalMatchBundle) -> None:
    if bundle.provider != STATSBOMB_PROVIDER:
        raise ValueError("StatsBomb validation requires the StatsBomb provider ID.")
    if bundle.capabilities.has_continuous_tracking:
        raise ValueError("StatsBomb Open Data must not be declared continuous tracking.")
    if not bundle.capabilities.has_events or not bundle.capabilities.has_lineups:
        raise ValueError("StatsBomb event bundles require events and lineups.")
    if not bundle.player_positions.empty or not bundle.ball_positions.empty:
        raise ValueError("StatsBomb event/360 data must not populate continuous tracking tables.")
    team_ids = set(bundle.teams.team_id)
    if not set(bundle.roster.team_id).issubset(team_ids):
        raise ValueError("StatsBomb lineup references an unknown team.")
    if not set(bundle.events.team_id.dropna()).issubset(team_ids):
        raise ValueError("StatsBomb events reference an unknown team.")
    if bundle.event_snapshots is not None:
        if not set(bundle.event_snapshots.event_id).issubset(set(bundle.events.event_id)):
            raise ValueError("StatsBomb 360 snapshot references an unknown event UUID.")


def statsbomb_team_coverage(adapter: StatsBombOpenDataAdapter) -> pd.DataFrame:
    """Return competition-season-team coverage and explicit 5/10/20 thresholds."""
    matches = adapter.matches()
    home = matches[["competition_id", "competition_name", "season_id", "season_name", "match_id", "home_team_id", "home_team_name", "has_360_snapshots"]].rename(columns={"home_team_id": "team_id", "home_team_name": "team"})
    away = matches[["competition_id", "competition_name", "season_id", "season_name", "match_id", "away_team_id", "away_team_name", "has_360_snapshots"]].rename(columns={"away_team_id": "team_id", "away_team_name": "team"})
    rows = pd.concat([home, away], ignore_index=True)
    result = rows.groupby(["competition_id", "competition_name", "season_id", "season_name", "team_id", "team"], dropna=False).agg(
        matches_available=("match_id", "nunique"),
        matches_with_360=("has_360_snapshots", "sum"),
    ).reset_index()
    for threshold in (5, 10, 20):
        result[f"at_least_{threshold}_matches"] = result.matches_available.ge(threshold)
    return result.sort_values(["matches_available", "competition_name", "season_name", "team"], ascending=[False, True, True, True], kind="stable").reset_index(drop=True)
