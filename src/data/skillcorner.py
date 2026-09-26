"""SkillCorner-to-canonical match adapter without changing existing metrics."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from .canonical import CanonicalMatchBundle, ProviderCapabilities, validate_canonical_bundle
from .tracking import PLAYER_TRACKING_COLUMNS, _player_metadata, _timestamp_to_seconds


def preflight_skillcorner_phase_periods(match_dir: str | Path) -> str | None:
    """Return a deterministic phase/tracking period issue without materializing tracking."""
    directory = Path(match_dir)
    match_id = directory.name
    phases_path = directory / f"{match_id}_phases_of_play.csv"
    tracking_path = directory / f"{match_id}_tracking_extrapolated.jsonl"
    if not phases_path.is_file() or not tracking_path.is_file():
        return "required phase or tracking file is missing"
    with phases_path.open("r", encoding="utf-8-sig", newline="") as source:
        phases = [
            (int(row["frame_start"]), int(row["frame_end"]), int(row["period"]))
            for row in csv.DictReader(source)
        ]
    tracked_periods = {}
    with tracking_path.open("r", encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record.get("player_data"):
                tracked_periods[int(record["frame"])] = int(record["period"])
    for frame_start, frame_end, period in phases:
        if any(
            tracked_periods[frame] != period
            for frame in range(frame_start, frame_end)
            if frame in tracked_periods
        ):
            return "canonical tactical-phase and tracking periods disagree"
    return None


def _load_tracking_stream(
    tracking_path: Path,
    match_info: dict,
    match_id: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stream SkillCorner JSONL into canonical player and ball tables.

    The canonical adapter previously retained the source text, every parsed
    frame dictionary, a raw DataFrame, and both flattened tables at once.  A
    full match consequently used far more memory than its canonical output.
    Nothing in the provider-independent analysis stack consumes raw tracking,
    so build the same canonical rows directly while reading the file once.
    """
    player_columns: dict[str, list] = {
        "frame": [], "timestamp": [], "elapsed_seconds": [], "period": [],
        "player_id": [], "x": [], "y": [], "is_detected": [],
    }
    ball_columns: dict[str, list] = {
        "match_id": [], "frame": [], "timestamp": [], "elapsed_seconds": [],
        "period": [], "ball_x": [], "ball_y": [],
    }

    with tracking_path.open("r", encoding="utf-8") as source:
        for line in source:
            frame_record = json.loads(line)
            frame = frame_record.get("frame")
            timestamp = frame_record.get("timestamp")
            elapsed_seconds = _timestamp_to_seconds(timestamp)
            period = frame_record.get("period")

            ball = frame_record.get("ball_data") or {}
            ball_columns["match_id"].append(match_id)
            ball_columns["frame"].append(frame)
            ball_columns["timestamp"].append(timestamp)
            ball_columns["elapsed_seconds"].append(elapsed_seconds)
            ball_columns["period"].append(period)
            ball_columns["ball_x"].append(ball.get("x"))
            ball_columns["ball_y"].append(ball.get("y"))

            for player in frame_record.get("player_data") or ():
                player_columns["frame"].append(frame)
                player_columns["timestamp"].append(timestamp)
                player_columns["elapsed_seconds"].append(elapsed_seconds)
                player_columns["period"].append(period)
                player_columns["player_id"].append(player.get("player_id"))
                player_columns["x"].append(player.get("x"))
                player_columns["y"].append(player.get("y"))
                player_columns["is_detected"].append(player.get("is_detected"))

    players = pd.DataFrame(player_columns)
    if players.empty:
        players = pd.DataFrame(columns=PLAYER_TRACKING_COLUMNS)
    else:
        players = players.merge(
            _player_metadata(match_info), on="player_id", how="left", validate="many_to_one"
        )
        players["period"] = players["period"].astype("Int64")
        players["team_id"] = players["team_id"].astype("Int64")
        players["player_number"] = players["player_number"].astype("Int64")
        players["is_detected"] = players["is_detected"].astype("boolean")
        players = players[PLAYER_TRACKING_COLUMNS]
    players.insert(0, "match_id", match_id)
    return players, pd.DataFrame(ball_columns)


def _canonical_events(dynamic: pd.DataFrame, match_id: int) -> pd.DataFrame:
    result = pd.DataFrame({
        "match_id": dynamic["match_id"], "event_id": dynamic["event_id"], "period": dynamic["period"],
        "event_index": dynamic.get("index"),
        "team_id": dynamic["team_id"], "event_type": dynamic["event_type"], "end_type": dynamic.get("end_type"),
        "frame_start": dynamic.get("frame_start"), "frame_end": dynamic.get("frame_end"),
        "elapsed_start_s": dynamic.get("time_start"), "elapsed_end_s": dynamic.get("time_end"),
        "minute": dynamic.get("minute_start"), "second": dynamic.get("second_start"),
        "player_id": dynamic.get("player_id"), "possession_id": dynamic.get("phase_index"),
        "possession_team_id": dynamic.get("team_id"), "play_pattern": dynamic.get("team_in_possession_phase_type"),
        "start_type": dynamic.get("start_type"), "lead_to_shot": dynamic.get("lead_to_shot"),
        "lead_to_goal": dynamic.get("lead_to_goal"), "location_x": dynamic.get("x_start"),
        "location_y": dynamic.get("y_start"), "end_location_x": dynamic.get("x_end"),
        "end_location_y": dynamic.get("y_end"), "game_state": dynamic.get("game_state"),
    })
    result["is_shot"] = result.event_type.eq("player_possession") & result.end_type.eq("shot")
    if not result.match_id.eq(match_id).all():
        raise ValueError("Dynamic Events match IDs do not match metadata.")
    return result


def _canonical_phases(phases: pd.DataFrame, match_id: int) -> pd.DataFrame:
    result = pd.DataFrame({
        "match_id": phases["match_id"], "period": phases["period"],
        "frame_start": phases["frame_start"], "frame_end_exclusive": phases["frame_end"],
        "possession_team_id": phases["team_in_possession_id"],
        "attacking_phase_type": phases.get("team_in_possession_phase_type"),
        "defending_phase_type": phases.get("team_out_of_possession_phase_type"),
        "leads_to_shot": phases.get("team_possession_lead_to_shot"),
        "leads_to_goal": phases.get("team_possession_lead_to_goal"),
        "phase_provider": "skillcorner",
    })
    if not result.match_id.eq(match_id).all():
        raise ValueError("Phase match IDs do not match metadata.")
    return result


def load_skillcorner_match(match_dir: str | Path) -> CanonicalMatchBundle:
    """Load one local SkillCorner Open Data directory into the common bundle."""
    directory = Path(match_dir)
    match_id = int(directory.name)
    metadata_path = directory / f"{match_id}_match.json"
    tracking_path = directory / f"{match_id}_tracking_extrapolated.jsonl"
    phases_path = directory / f"{match_id}_phases_of_play.csv"
    events_path = directory / f"{match_id}_dynamic_events.csv"
    for path in (metadata_path, tracking_path, phases_path, events_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing SkillCorner source file: {path.name}")
    match_info = json.loads(metadata_path.read_text(encoding="utf-8"))
    players, balls = _load_tracking_stream(tracking_path, match_info, match_id)
    teams = pd.DataFrame([{
        "match_id": match_id, "team_id": item["id"], "team_code": item["acronym"], "home_away": side,
    } for item, side in ((match_info["home_team"], "home"), (match_info["away_team"], "away"))])
    roster = pd.DataFrame([{
        "match_id": match_id, "player_id": player["id"], "team_id": player["team_id"],
        "player_number": player.get("number"),
        "position": (player.get("player_role") or {}).get("name"),
        "position_group": (player.get("player_role") or {}).get("position_group"),
        "is_goalkeeper": (player.get("player_role") or {}).get("name") == "Goalkeeper",
    } for player in match_info["players"]])
    directions = pd.DataFrame([
        {"match_id": match_id, "period": period, "team_id": team["id"], "attacking_x_sign": sign}
        for period, home_side in enumerate(match_info["home_team_side"], start=1)
        for team, sign in ((match_info["home_team"], 1 if home_side == "left_to_right" else -1), (match_info["away_team"], -1 if home_side == "left_to_right" else 1))
    ])
    dynamic = pd.read_csv(events_path, low_memory=False)
    phases = pd.read_csv(phases_path)
    bundle = CanonicalMatchBundle(
        provider="skillcorner_open_data", match_info=match_info,
        matches=pd.DataFrame([{"match_id": match_id, "pitch_length_m": match_info["pitch_length"], "pitch_width_m": match_info["pitch_width"]}]),
        teams=teams, roster=roster, player_positions=players, ball_positions=balls,
        attacking_directions=directions,
        events=_canonical_events(dynamic, match_id), tactical_phases=_canonical_phases(phases, match_id),
        capabilities=ProviderCapabilities(True, True, True, True, True, True),
        raw={"dynamic_events": dynamic, "phases": phases},
    )
    validate_canonical_bundle(bundle)
    return bundle
