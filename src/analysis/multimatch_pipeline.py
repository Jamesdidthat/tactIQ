"""Sequential multi-match processing for SkillCorner open-data matches."""

from __future__ import annotations

import gc
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from src.data import expand_phase_context, join_phase_context_to_team_shape
from src.metrics.defensive_line_structure import POSITION_GROUP_TO_LINE


LOGGER = logging.getLogger(__name__)

INTERVAL_OUTPUT_COLUMNS = [
    "match_id",
    "match_date",
    "defending_team_id",
    "defending_team_acronym",
    "attacking_team_id",
    "attacking_team_acronym",
    "period",
    "phase_frame_start",
    "phase_frame_end",
    "phase_duration",
    "defending_phase_type",
    "team_possession_lead_to_shot",
    "team_possession_lead_to_goal",
    "matched_frame_count",
    "expected_frame_count",
    "coverage_ratio",
    "represented_seconds",
    "median_player_count",
    "median_outfield_width",
    "median_outfield_length",
    "complete_line_frame_count",
    "median_defence_to_midfield_gap",
    "median_midfield_to_attack_gap",
    "median_defence_tactical_median_x",
    "median_midfield_tactical_median_x",
    "median_attack_tactical_median_x",
    "median_total_outfield_length",
    "median_defence_tactical_vertical_range",
    "median_midfield_tactical_vertical_range",
    "median_attack_tactical_vertical_range",
    "median_defence_tactical_median_absolute_deviation",
    "median_midfield_tactical_median_absolute_deviation",
    "median_attack_tactical_median_absolute_deviation",
    "median_deepest_defender_x",
    "median_highest_attacker_x",
    "median_deepest_outfield_x",
    "median_highest_outfield_x",
    "median_total_outfield_vertical_range",
    "ball_available_frame_count",
    "defending_half_ball_frame_count",
    "median_ball_normalized_x",
    "median_defending_half_ball_normalized_x",
    "ball_depth_zone",
    "median_defence_line_to_ball_distance",
    "median_midfield_line_to_ball_distance",
    "median_attack_line_to_ball_distance",
    "median_deepest_defender_to_ball_distance",
    "median_highest_attacker_to_ball_distance",
]


@dataclass
class MultiMatchPipelineResult:
    """Compact interval output plus a record of matches processed or skipped."""

    intervals: pd.DataFrame
    processing_log: pd.DataFrame


def discover_match_directories(matches_root: str | Path) -> list[Path]:
    """Return sorted match directories containing the three required data files."""
    root = Path(matches_root)
    if not root.is_dir():
        raise FileNotFoundError(f"Match directory root does not exist: {root}")

    return sorted(
        (path for path in root.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )


def _load_match(match_dir: Path) -> tuple[dict[str, Any], Path, pd.DataFrame]:
    match_id = int(match_dir.name)
    metadata_path = match_dir / f"{match_id}_match.json"
    tracking_path = match_dir / f"{match_id}_tracking_extrapolated.jsonl"
    phases_path = match_dir / f"{match_id}_phases_of_play.csv"
    required_paths = (metadata_path, tracking_path, phases_path)
    missing = [path.name for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {', '.join(missing)}")

    with metadata_path.open(encoding="utf-8") as file:
        match_info = json.load(file)
    phases = pd.read_csv(phases_path)
    return match_info, tracking_path, phases


def _timestamp_to_seconds(timestamp: str) -> float:
    hours, minutes, seconds = timestamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _span(values: list[float]) -> float:
    return max(values) - min(values)


def _defending_half_ball_zone(normalized_x: float) -> str | None:
    """Return a coarse defending-half zone for attack-normalised ball x."""
    if pd.isna(normalized_x) or normalized_x >= 0:
        return None
    if normalized_x < -35:
        return "deep_defending_half"
    if normalized_x < -17.5:
        return "middle_defending_half"
    return "front_defending_half"


def _build_team_shape_from_tracking_stream(
    tracking_path: Path, match_info: dict[str, Any]
) -> pd.DataFrame:
    """Stream raw JSONL into compact Team Shape rows using the verified ID mapping.

    Each raw ``player_data`` record is flattened against ``players[].id`` for its
    current frame, then aggregated immediately. This is equivalent to building
    Team Shape from the flattened player dataframe, without retaining 800k+ rows
    per match during a multi-match batch run.
    """
    team_acronyms = {
        match_info["home_team"]["id"]: match_info["home_team"]["acronym"],
        match_info["away_team"]["id"]: match_info["away_team"]["acronym"],
    }
    player_metadata = {
        player["id"]: {
            "team_id": player["team_id"],
            "is_goalkeeper": (player.get("player_role") or {}).get("name") == "Goalkeeper",
            "position_group": (player.get("player_role") or {}).get("position_group"),
        }
        for player in match_info["players"]
    }
    home_attacking_signs = {
        period: {"left_to_right": 1, "right_to_left": -1}[side]
        for period, side in enumerate(match_info["home_team_side"], start=1)
    }
    home_team_id = match_info["home_team"]["id"]
    rows: list[dict[str, Any]] = []
    with tracking_path.open(encoding="utf-8") as file:
        for line in file:
            frame_data = json.loads(line)
            player_data = frame_data["player_data"]
            if not player_data:
                continue
            team_players: dict[int, list[tuple[float, float, bool, str | None]]] = {
                team_id: [] for team_id in team_acronyms
            }
            for tracked_player in player_data:
                player_id = tracked_player["player_id"]
                if player_id not in player_metadata:
                    raise ValueError(f"Tracking player ID {player_id} is missing from match metadata.")
                metadata = player_metadata[player_id]
                team_players[metadata["team_id"]].append(
                    (
                        tracked_player["x"], tracked_player["y"], metadata["is_goalkeeper"],
                        metadata["position_group"],
                    )
                )

            timestamp = frame_data["timestamp"]
            if timestamp is None:
                continue
            period = frame_data["period"]
            if period not in home_attacking_signs:
                raise ValueError(f"No home_team_side direction exists for period {period}.")
            for team_id, players in team_players.items():
                if not players:
                    continue
                x_values = [player[0] for player in players]
                y_values = [player[1] for player in players]
                outfield = [player for player in players if not player[2]]
                outfield_x = [player[0] for player in outfield]
                outfield_y = [player[1] for player in outfield]
                tactical_sign = home_attacking_signs[period] if team_id == home_team_id else -home_attacking_signs[period]
                line_players = {
                    line: [
                        player for player in players
                        if POSITION_GROUP_TO_LINE.get(player[3]) == line
                    ]
                    for line in ("defence", "midfield", "attack")
                }
                line_tactical_medians = {
                    line: (
                        median(player[0] * tactical_sign for player in line_values)
                        if line_values else float("nan")
                    )
                    for line, line_values in line_players.items()
                }
                line_tactical_values = {
                    line: [player[0] * tactical_sign for player in line_values]
                    for line, line_values in line_players.items()
                }
                line_vertical_ranges = {
                    line: max(values) - min(values) if values else float("nan")
                    for line, values in line_tactical_values.items()
                }
                line_mads = {
                    line: median(abs(value - line_tactical_medians[line]) for value in values)
                    if values else float("nan")
                    for line, values in line_tactical_values.items()
                }
                line_complete = all(line_players.values())
                mapped_outfield_x = [
                    player[0] * tactical_sign for player in players
                    if player[3] in POSITION_GROUP_TO_LINE
                ]
                ball_data = frame_data.get("ball_data") or {}
                ball_x = ball_data.get("x")
                ball_normalized_x = (
                    ball_x * tactical_sign if ball_x is not None else float("nan")
                )
                deepest_defender_x = (
                    min(line_tactical_values["defence"])
                    if line_tactical_values["defence"] else float("nan")
                )
                highest_attacker_x = (
                    max(line_tactical_values["attack"])
                    if line_tactical_values["attack"] else float("nan")
                )
                rows.append({
                    "frame": frame_data["frame"],
                    "timestamp": timestamp,
                    "elapsed_seconds": _timestamp_to_seconds(timestamp),
                    "period": period,
                    "team_id": team_id,
                    "team_acronym": team_acronyms[team_id],
                    "full_team_width": _span(y_values),
                    "full_team_length": _span(x_values),
                    "full_team_centroid_x": sum(x_values) / len(x_values),
                    "full_team_centroid_y": sum(y_values) / len(y_values),
                    "outfield_width": _span(outfield_y) if outfield else float("nan"),
                    "outfield_length": _span(outfield_x) if outfield else float("nan"),
                    "outfield_centroid_x": sum(outfield_x) / len(outfield_x) if outfield else float("nan"),
                    "outfield_centroid_y": sum(outfield_y) / len(outfield_y) if outfield else float("nan"),
                    "player_count": len(players),
                    "line_structure_complete": line_complete,
                    "defence_to_midfield_gap": (
                        line_tactical_medians["midfield"] - line_tactical_medians["defence"]
                        if line_complete else float("nan")
                    ),
                    "midfield_to_attack_gap": (
                        line_tactical_medians["attack"] - line_tactical_medians["midfield"]
                        if line_complete else float("nan")
                    ),
                    "defence_tactical_median_x": line_tactical_medians["defence"],
                    "midfield_tactical_median_x": line_tactical_medians["midfield"],
                    "attack_tactical_median_x": line_tactical_medians["attack"],
                    "total_outfield_length": (
                        max(mapped_outfield_x) - min(mapped_outfield_x)
                        if mapped_outfield_x else float("nan")
                    ),
                    "defence_tactical_vertical_range": line_vertical_ranges["defence"],
                    "midfield_tactical_vertical_range": line_vertical_ranges["midfield"],
                    "attack_tactical_vertical_range": line_vertical_ranges["attack"],
                    "defence_tactical_median_absolute_deviation": line_mads["defence"],
                    "midfield_tactical_median_absolute_deviation": line_mads["midfield"],
                    "attack_tactical_median_absolute_deviation": line_mads["attack"],
                    "deepest_outfield_x": min(mapped_outfield_x) if mapped_outfield_x else float("nan"),
                    "highest_outfield_x": max(mapped_outfield_x) if mapped_outfield_x else float("nan"),
                    "deepest_defender_x": deepest_defender_x,
                    "highest_attacker_x": highest_attacker_x,
                    "total_outfield_vertical_range": (
                        max(mapped_outfield_x) - min(mapped_outfield_x)
                        if mapped_outfield_x else float("nan")
                    ),
                    "ball_normalized_x": ball_normalized_x,
                    # Signed distance is line x minus ball x. Positive means a
                    # line is closer to the opponent goal than the ball.
                    "defence_line_to_ball_distance": line_tactical_medians["defence"] - ball_normalized_x,
                    "midfield_line_to_ball_distance": line_tactical_medians["midfield"] - ball_normalized_x,
                    "attack_line_to_ball_distance": line_tactical_medians["attack"] - ball_normalized_x,
                    "deepest_defender_to_ball_distance": deepest_defender_x - ball_normalized_x,
                    "highest_attacker_to_ball_distance": highest_attacker_x - ball_normalized_x,
                })
    return pd.DataFrame(rows).set_index(
        ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
    ).sort_index()


def _build_interval_output(
    team_shape_with_context: pd.DataFrame, match_info: dict[str, Any]
) -> pd.DataFrame:
    """Reduce joined Team Shape to one observation per defending phase interval."""
    team_acronyms = {
        match_info["home_team"]["id"]: match_info["home_team"]["acronym"],
        match_info["away_team"]["id"]: match_info["away_team"]["acronym"],
    }
    rows = team_shape_with_context.reset_index()
    defending_rows = rows.loc[
        rows["possession_status"].eq("out_of_possession")
        & rows["tactical_phase"].notna()
    ].copy()
    group_columns = [
        "team_id", "team_acronym", "possession_team_id", "period",
        "phase_frame_start", "phase_frame_end", "phase_duration", "tactical_phase",
        "team_possession_lead_to_shot", "team_possession_lead_to_goal",
    ]
    output = (
        defending_rows.groupby(group_columns, dropna=False)
        .agg(
            matched_frame_count=("frame", "size"),
            median_player_count=("player_count", "median"),
            median_outfield_width=("outfield_width", "median"),
            median_outfield_length=("outfield_length", "median"),
            complete_line_frame_count=("line_structure_complete", "sum"),
            median_defence_to_midfield_gap=("defence_to_midfield_gap", "median"),
            median_midfield_to_attack_gap=("midfield_to_attack_gap", "median"),
            median_defence_tactical_median_x=("defence_tactical_median_x", "median"),
            median_midfield_tactical_median_x=("midfield_tactical_median_x", "median"),
            median_attack_tactical_median_x=("attack_tactical_median_x", "median"),
            median_total_outfield_length=("total_outfield_length", "median"),
            median_defence_tactical_vertical_range=("defence_tactical_vertical_range", "median"),
            median_midfield_tactical_vertical_range=("midfield_tactical_vertical_range", "median"),
            median_attack_tactical_vertical_range=("attack_tactical_vertical_range", "median"),
            median_defence_tactical_median_absolute_deviation=("defence_tactical_median_absolute_deviation", "median"),
            median_midfield_tactical_median_absolute_deviation=("midfield_tactical_median_absolute_deviation", "median"),
            median_attack_tactical_median_absolute_deviation=("attack_tactical_median_absolute_deviation", "median"),
            median_deepest_defender_x=("deepest_defender_x", "median"),
            median_highest_attacker_x=("highest_attacker_x", "median"),
            median_deepest_outfield_x=("deepest_outfield_x", "median"),
            median_highest_outfield_x=("highest_outfield_x", "median"),
            median_total_outfield_vertical_range=("total_outfield_vertical_range", "median"),
            ball_available_frame_count=("ball_normalized_x", "count"),
            defending_half_ball_frame_count=(
                "ball_normalized_x", lambda values: values.lt(0).sum()
            ),
            median_ball_normalized_x=("ball_normalized_x", "median"),
            median_defending_half_ball_normalized_x=(
                "ball_normalized_x", lambda values: values.loc[values.lt(0)].median()
            ),
            median_defence_line_to_ball_distance=("defence_line_to_ball_distance", "median"),
            median_midfield_line_to_ball_distance=("midfield_line_to_ball_distance", "median"),
            median_attack_line_to_ball_distance=("attack_line_to_ball_distance", "median"),
            median_deepest_defender_to_ball_distance=("deepest_defender_to_ball_distance", "median"),
            median_highest_attacker_to_ball_distance=("highest_attacker_to_ball_distance", "median"),
        )
        .reset_index()
        .rename(columns={
            "team_id": "defending_team_id",
            "team_acronym": "defending_team_acronym",
            "possession_team_id": "attacking_team_id",
            "tactical_phase": "defending_phase_type",
        })
    )
    output["match_id"] = match_info["id"]
    output["match_date"] = pd.to_datetime(match_info["date_time"], utc=True).date()
    output["attacking_team_acronym"] = output["attacking_team_id"].map(team_acronyms)
    output["expected_frame_count"] = output["phase_frame_end"] - output["phase_frame_start"]
    output["coverage_ratio"] = output["matched_frame_count"] / output["expected_frame_count"]
    output["represented_seconds"] = output["matched_frame_count"] / 10
    output["ball_depth_zone"] = output["median_defending_half_ball_normalized_x"].map(
        _defending_half_ball_zone
    )
    return output[INTERVAL_OUTPUT_COLUMNS]


def _validate_interval_output(intervals: pd.DataFrame) -> None:
    keys = ["match_id", "period", "phase_frame_start", "phase_frame_end", "defending_team_id"]
    if intervals.duplicated(keys).any():
        raise ValueError("Output contains duplicate match-phase-defending-team observations.")
    if (intervals["matched_frame_count"] > intervals["expected_frame_count"]).any():
        raise ValueError("An interval has more matched frames than its source interval length.")
    if not intervals["coverage_ratio"].between(0, 1).all():
        raise ValueError("Interval coverage ratios must lie between zero and one.")


def process_skillcorner_matches(
    matches_root: str | Path,
    match_directories: Iterable[Path] | None = None,
) -> MultiMatchPipelineResult:
    """Process SkillCorner matches one at a time into compact interval outputs.

    Processing errors are logged and retained in ``processing_log``; one bad
    match never prevents the remaining valid matches from being analysed.
    """
    directories = list(match_directories) if match_directories is not None else discover_match_directories(matches_root)
    outputs: list[pd.DataFrame] = []
    log_rows: list[dict[str, str | int]] = []

    for match_dir in directories:
        match_id = int(match_dir.name)
        try:
            match_info, tracking_path, phases = _load_match(match_dir)
            team_shape = _build_team_shape_from_tracking_stream(tracking_path, match_info)
            phase_context = expand_phase_context(phases, match_info)
            joined = join_phase_context_to_team_shape(team_shape, phase_context, match_info)
            intervals = _build_interval_output(joined, match_info)
            _validate_interval_output(intervals)
            outputs.append(intervals)
            log_rows.append({"match_id": match_id, "status": "processed", "message": ""})
        except Exception as error:  # Retain a diagnostic and continue with other matches.
            LOGGER.exception("Skipping match %s", match_id)
            log_rows.append({"match_id": match_id, "status": "skipped", "message": str(error)})
        finally:
            # Explicitly release frame-level objects before processing the next match.
            team_shape = None
            phase_context = None
            joined = None
            gc.collect()

    combined = (
        pd.concat(outputs, ignore_index=True)
        if outputs else pd.DataFrame(columns=INTERVAL_OUTPUT_COLUMNS)
    )
    if not combined.empty:
        _validate_interval_output(combined)
    return MultiMatchPipelineResult(
        intervals=combined.sort_values(
            ["match_id", "period", "phase_frame_start", "defending_team_id"]
        ).reset_index(drop=True),
        processing_log=pd.DataFrame(log_rows),
    )
