"""Adapter for Metrica Sports' public raw CSV tracking sample.

The adapter emits the provider-agnostic logical tables described in
``docs/dataset_expansion_readiness.md``.  It does not attempt to map Metrica
events to SkillCorner phases or Dynamic Events.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .canonical import CanonicalMatchBundle, ProviderCapabilities, validate_canonical_bundle


PITCH_LENGTH_METRES = 105.0
PITCH_WIDTH_METRES = 68.0


def sample_game_1_role_map() -> dict[str, dict[str, str]]:
    """Return an explicit *demonstration-only* role map for Sample Game 1.

    Metrica's public CSVs identify players only as ``PlayerN`` and do not ship
    a position/goalkeeper roster.  These labels allow the generic line metrics
    to be exercised, but are not provider metadata and must be replaced by a
    vetted roster mapping in production.
    """
    def roles(goalkeeper: str, defenders: Sequence[str], midfielders: Sequence[str], attackers: Sequence[str]) -> dict[str, str]:
        output = {goalkeeper: "Goalkeeper"}
        output.update({player: "Central Defender" for player in defenders})
        output.update({player: "Midfield" for player in midfielders})
        output.update({player: "Center Forward" for player in attackers})
        return output

    return {
        "home": roles("Player11", ["Player1", "Player2", "Player3", "Player4", "Player12"], ["Player5", "Player6", "Player7", "Player8", "Player13"], ["Player9", "Player10", "Player14"]),
        "away": roles("Player25", ["Player15", "Player16", "Player17", "Player18", "Player26"], ["Player19", "Player20", "Player21", "Player22", "Player27"], ["Player23", "Player24", "Player28"]),
    }


def _position_group(position: str) -> str:
    return {
        "Goalkeeper": "Other",
        "Central Defender": "Central Defender",
        "Midfield": "Midfield",
        "Center Forward": "Center Forward",
    }[position]


def _timestamp(seconds: float) -> str:
    hours, remainder = divmod(float(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"


def _player_columns(frame: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Get (player ID, x column, y column) pairs from a raw Metrica CSV."""
    columns = list(frame.columns)
    pairs = []
    for index in range(3, len(columns) - 2, 2):
        player_id = columns[index]
        if not str(player_id).startswith("Player"):
            continue
        pairs.append((str(player_id), columns[index], columns[index + 1]))
    if not pairs:
        raise ValueError("Metrica tracking CSV has no PlayerN x/y column pairs.")
    return pairs


def _read_team_tracking(path: Path, team_id: str, team_code: str, roles: Mapping[str, str] | None, stride: int) -> pd.DataFrame:
    raw = pd.read_csv(path, skiprows=2)
    required = {"Period", "Frame", "Time [s]", "Ball", "Unnamed: 32"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Unexpected Metrica CSV schema; missing {sorted(missing)}")
    raw = raw.iloc[::stride].copy()
    player_pairs = _player_columns(raw)
    role_missing = {player for player, _, _ in player_pairs} - set(roles or {})
    if roles is not None and role_missing:
        raise ValueError(f"No explicit role supplied for Metrica players: {sorted(role_missing)}")

    records = []
    for player_id, x_column, y_column in player_pairs:
        part = raw[["Period", "Frame", "Time [s]", x_column, y_column]].copy()
        part.columns = ["period", "frame", "elapsed_seconds", "source_x", "source_y"]
        part["player_id"] = player_id
        part["team_id"] = team_id
        part["team_acronym"] = team_code
        position = roles[player_id] if roles is not None else pd.NA
        part["position"] = position
        part["position_group"] = _position_group(position) if pd.notna(position) else pd.NA
        records.append(part)
    players = pd.concat(records, ignore_index=True)
    players = players.loc[players.source_x.notna() & players.source_y.notna()].copy()
    # Metrica x is [0, 1] left-to-right and y is [0, 1] top-to-bottom.
    players["x"] = (players.source_x - 0.5) * PITCH_LENGTH_METRES
    players["y"] = (0.5 - players.source_y) * PITCH_WIDTH_METRES
    players["timestamp"] = players.elapsed_seconds.map(_timestamp)
    players["is_detected"] = True
    return players[["frame", "timestamp", "elapsed_seconds", "period", "player_id", "team_id", "team_acronym", "position", "position_group", "x", "y", "is_detected"]]


def _read_ball_tracking(path: Path, stride: int) -> pd.DataFrame:
    raw = pd.read_csv(path, skiprows=2).iloc[::stride].copy()
    ball_y_column = "Unnamed: 32"
    ball = raw[["Period", "Frame", "Time [s]", "Ball", ball_y_column]].copy()
    ball.columns = ["period", "frame", "elapsed_seconds", "source_x", "source_y"]
    ball["ball_x"] = (ball.source_x - 0.5) * PITCH_LENGTH_METRES
    ball["ball_y"] = (0.5 - ball.source_y) * PITCH_WIDTH_METRES
    ball["timestamp"] = ball.elapsed_seconds.map(_timestamp)
    return ball[["frame", "timestamp", "elapsed_seconds", "period", "ball_x", "ball_y"]]


def validate_canonical_metrica_data(result: Mapping[str, Any], *, coordinate_tolerance_metres: float = 6.0) -> None:
    """Validate the core canonical contract emitted by this adapter."""
    match_info = result["match_info"]
    players = result["player_positions"]
    ball = result["ball_positions"]
    teams = {match_info["home_team"]["id"], match_info["away_team"]["id"]}
    required_players = {"frame", "period", "elapsed_seconds", "player_id", "team_id", "x", "y", "position", "position_group"}
    required_ball = {"frame", "period", "elapsed_seconds", "ball_x", "ball_y"}
    if missing := required_players - set(players):
        raise ValueError(f"Canonical player positions missing {sorted(missing)}")
    if missing := required_ball - set(ball):
        raise ValueError(f"Canonical ball positions missing {sorted(missing)}")
    if players.duplicated(["frame", "period", "player_id"]).any():
        raise ValueError("Canonical player positions contain duplicate player-frame rows.")
    if ball.duplicated(["frame", "period"]).any():
        raise ValueError("Canonical ball positions contain duplicate frame rows.")
    if not set(players.team_id.unique()).issubset(teams):
        raise ValueError("Canonical player positions contain a team absent from metadata.")
    if coordinate_tolerance_metres < 0:
        raise ValueError("coordinate_tolerance_metres must be non-negative.")
    length, width = match_info["pitch_length"], match_info["pitch_width"]
    # Metrica's measured normalized coordinates can be a little outside 0..1
    # at the touchline. Preserve those observations rather than silently clip
    # them, but reject values that cannot plausibly be pitch tracking.
    x_bounds = (-length / 2 - coordinate_tolerance_metres, length / 2 + coordinate_tolerance_metres)
    y_bounds = (-width / 2 - coordinate_tolerance_metres, width / 2 + coordinate_tolerance_metres)
    if not players.x.between(*x_bounds).all() or not players.y.between(*y_bounds).all():
        raise ValueError("Player coordinates exceed declared pitch bounds plus tolerance.")
    observed_ball = ball.dropna(subset=["ball_x", "ball_y"])
    if not observed_ball.empty and (not observed_ball.ball_x.between(*x_bounds).all() or not observed_ball.ball_y.between(*y_bounds).all()):
        raise ValueError("Observed ball coordinates exceed declared pitch bounds plus tolerance.")
    periods = set(players.period.unique())
    direction_periods = set(range(1, len(match_info["home_team_side"]) + 1))
    if not periods.issubset(direction_periods):
        raise ValueError("Every canonical tracking period requires an attacking-direction entry.")


def load_metrica_sample_game(
    data_dir: str | Path,
    *,
    match_id: str = "metrica_sample_game_1",
    frame_stride: int = 5,
    role_map: Mapping[str, Mapping[str, str]] | None = None,
    allow_assumed_roles: bool = False,
    home_team_side: Sequence[str] = ("left_to_right", "right_to_left"),
) -> CanonicalMatchBundle:
    """Load Sample Game 1 into the canonical tracking and metadata tables.

    ``frame_stride=5`` produces a declared 5 Hz view from the source's 25 Hz
    frames, keeping the demonstration light while preserving elapsed time.  Use
    ``frame_stride=1`` for the full public sample.  No event table is converted
    because SkillCorner event/phase mappings are explicitly out of scope.
    Metrica's public CSVs lack verified role metadata. Passing
    ``allow_assumed_roles=True`` enables the clearly labelled Sample Game 1
    development role map; without it, role-dependent analyses are gated off.
    """
    if frame_stride < 1:
        raise ValueError("frame_stride must be at least one.")
    if len(home_team_side) != 2 or set(home_team_side) - {"left_to_right", "right_to_left"}:
        raise ValueError("home_team_side must specify valid directions for both periods.")
    root = Path(data_dir)
    home_path = root / "Sample_Game_1_RawTrackingData_Home_Team.csv"
    away_path = root / "Sample_Game_1_RawTrackingData_Away_Team.csv"
    if not home_path.is_file() or not away_path.is_file():
        raise FileNotFoundError("Expected Metrica Sample Game 1 home and away tracking CSVs.")
    if role_map is not None and not allow_assumed_roles:
        raise ValueError("A Metrica role map requires allow_assumed_roles=True.")
    roles = dict(role_map or sample_game_1_role_map()) if allow_assumed_roles else None
    if roles is not None and set(roles) != {"home", "away"}:
        raise ValueError("role_map must contain explicit 'home' and 'away' player mappings.")
    home_id, away_id = "metrica_home", "metrica_away"
    players = pd.concat([
        _read_team_tracking(home_path, home_id, "HOME", roles["home"] if roles else None, frame_stride),
        _read_team_tracking(away_path, away_id, "AWAY", roles["away"] if roles else None, frame_stride),
    ], ignore_index=True)
    ball = _read_ball_tracking(home_path, frame_stride)
    metadata_players = []
    for team_key, team_id in (("home", home_id), ("away", away_id)):
        team_players = [player for player in players.loc[players.team_id.eq(team_id), "player_id"].unique()]
        for player_id in team_players:
            position = roles[team_key][player_id] if roles else pd.NA
            metadata_players.append({"id": player_id, "team_id": team_id, "first_name": player_id, "last_name": "", "number": pd.NA, "player_role": {"name": position, "position_group": _position_group(position) if pd.notna(position) else pd.NA}})
    match_info = {
        "id": match_id,
        "provider": "metrica_public_sample",
        "pitch_length": PITCH_LENGTH_METRES,
        "pitch_width": PITCH_WIDTH_METRES,
        "home_team": {"id": home_id, "name": "Metrica Home", "acronym": "HOME"},
        "away_team": {"id": away_id, "name": "Metrica Away", "acronym": "AWAY"},
        "home_team_side": list(home_team_side),
        "players": metadata_players,
        "sample_rate_hz": 25.0 / frame_stride,
        "role_map_provenance": "sample_game_1_demonstration_assumption" if roles else "unavailable_in_public_csv",
    }
    players.insert(0, "match_id", match_id)
    ball.insert(0, "match_id", match_id)
    roster = pd.DataFrame([{
        "match_id": match_id, "player_id": player["id"], "team_id": player["team_id"],
        "position": player["player_role"]["name"], "position_group": player["player_role"]["position_group"],
        "is_goalkeeper": player["player_role"]["name"] == "Goalkeeper",
    } for player in metadata_players])
    directions = pd.DataFrame([
        {"match_id": match_id, "period": period, "team_id": team_id, "attacking_x_sign": sign}
        for period, home_side in enumerate(home_team_side, start=1)
        for team_id, sign in ((home_id, 1 if home_side == "left_to_right" else -1), (away_id, -1 if home_side == "left_to_right" else 1))
    ])
    bundle = CanonicalMatchBundle(
        provider="metrica_public_sample", match_info=match_info,
        matches=pd.DataFrame([{"match_id": match_id, "pitch_length_m": PITCH_LENGTH_METRES, "pitch_width_m": PITCH_WIDTH_METRES}]),
        teams=pd.DataFrame([{"match_id": match_id, "team_id": home_id, "team_code": "HOME", "home_away": "home"}, {"match_id": match_id, "team_id": away_id, "team_code": "AWAY", "home_away": "away"}]),
        roster=roster, player_positions=players, ball_positions=ball, attacking_directions=directions,
        capabilities=ProviderCapabilities(True, True, False, True, False, False, has_assumed_roles=roles is not None),
        raw={"event_file": root / "Sample_Game_1_RawEventsData.csv"},
    )
    validate_canonical_bundle(bundle)
    validate_canonical_metrica_data(bundle)
    return bundle
