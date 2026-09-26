"""Team-relative defensive line-structure metrics from player tracking."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


LINE_STRUCTURE_INDEX = [
    "frame",
    "timestamp",
    "elapsed_seconds",
    "period",
    "team_id",
    "team_acronym",
]

# This mapping is deliberately based on the values inspected in all ten supplied
# match metadata files. ``Other`` contains Goalkeeper and Substitute, and is not
# an outfield tactical line.
POSITION_GROUP_TO_LINE = {
    "Central Defender": "defence",
    "Full Back": "defence",
    "Midfield": "midfield",
    "Center Forward": "attack",
    "Wide Attacker": "attack",
}
LINE_ORDER = ("defence", "midfield", "attack")


def _median_absolute_deviation(values: pd.Series) -> float:
    """Return median absolute distance from the series median."""
    centre = values.median()
    return (values - centre).abs().median()


def _home_attacking_signs(match_info: Mapping[str, Any]) -> dict[int, int]:
    """Return the home team's attacking x sign by period.

    ``home_team_side`` records the side/goal direction of the home team. A
    home value of ``left_to_right`` means attacking toward increasing native x;
    the away team necessarily attacks in the opposite direction.
    """
    sides = match_info.get("home_team_side")
    if not isinstance(sides, (list, tuple)) or not sides:
        raise ValueError("match_info['home_team_side'] must contain one side per period.")

    side_to_sign = {"left_to_right": 1, "right_to_left": -1}
    signs: dict[int, int] = {}
    for period, side in enumerate(sides, start=1):
        if side not in side_to_sign:
            raise ValueError(f"Unsupported home team side for period {period}: {side!r}")
        signs[period] = side_to_sign[side]
    return signs


def calculate_defensive_line_structure(
    tracking_players: pd.DataFrame,
    match_info: Mapping[str, Any],
) -> pd.DataFrame:
    """Calculate native and attack-normalised tactical line metrics per team-frame.

    Native SkillCorner x is retained in the ``*_native_median_x`` columns.
    ``*_tactical_median_x`` is native x multiplied by the team's period-specific
    attacking sign, so higher values always mean closer to the opponent's goal.

    A line is available only when at least one tracked, positioned player maps
    explicitly to it. Missing lines and gaps therefore remain ``NaN``; no
    formation or player-role inference is performed. ``line_structure_complete``
    is true only where all three outfield lines are available.
    """
    required = set(LINE_STRUCTURE_INDEX + ["player_id", "position_group", "x", "y"])
    missing = required - set(tracking_players.columns)
    if missing:
        raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")

    home_team = match_info.get("home_team") or {}
    away_team = match_info.get("away_team") or {}
    home_team_id = home_team.get("id")
    away_team_id = away_team.get("id")
    if home_team_id is None or away_team_id is None:
        raise ValueError("match_info must contain home_team.id and away_team.id.")
    attacking_sign_by_period = _home_attacking_signs(match_info)

    duplicate_keys = ["frame", "team_id", "player_id"]
    if tracking_players.duplicated(duplicate_keys).any():
        raise ValueError("tracking_players must have at most one row per frame, team, and player.")

    team_frames = tracking_players[LINE_STRUCTURE_INDEX].drop_duplicates().copy()
    unknown_team_ids = set(team_frames["team_id"].dropna().unique()) - {home_team_id, away_team_id}
    if unknown_team_ids:
        raise ValueError(f"Tracking contains teams absent from match metadata: {sorted(unknown_team_ids)}")
    unknown_periods = set(team_frames["period"].dropna().astype(int).unique()) - set(attacking_sign_by_period)
    if unknown_periods:
        raise ValueError(f"No home_team_side direction exists for periods: {sorted(unknown_periods)}")

    team_frame_home_sign = team_frames["period"].astype(int).map(attacking_sign_by_period)
    team_frames["attacking_direction_sign"] = team_frame_home_sign.where(
        team_frames["team_id"].eq(home_team_id), -team_frame_home_sign
    )

    rows = tracking_players.loc[
        tracking_players["position_group"].isin(POSITION_GROUP_TO_LINE)
        & tracking_players["x"].notna()
        & tracking_players["y"].notna()
    ].copy()
    if rows.empty:
        result = team_frames.set_index(LINE_STRUCTURE_INDEX)
        for line in LINE_ORDER:
            result[f"{line}_line_player_count"] = 0
            result[f"{line}_native_median_x"] = float("nan")
            result[f"{line}_tactical_median_x"] = float("nan")
            result[f"{line}_tactical_min_x"] = float("nan")
            result[f"{line}_tactical_max_x"] = float("nan")
            result[f"{line}_tactical_vertical_range"] = float("nan")
            result[f"{line}_tactical_median_absolute_deviation"] = float("nan")
            result[f"{line}_line_available"] = False
        result["outfield_player_count"] = 0
        for column in (
            "outfield_native_min_x", "outfield_native_max_x",
            "outfield_tactical_min_x", "outfield_tactical_max_x",
            "defence_to_midfield_gap", "midfield_to_attack_gap", "total_outfield_length",
            "deepest_outfield_x", "highest_outfield_x", "deepest_defender_x",
            "highest_attacker_x", "total_outfield_vertical_range",
        ):
            result[column] = float("nan")
        result["line_structure_complete"] = False
        return result.sort_index()

    rows["line"] = rows["position_group"].map(POSITION_GROUP_TO_LINE)
    home_sign = rows["period"].astype(int).map(attacking_sign_by_period)
    rows["attacking_direction_sign"] = home_sign.where(rows["team_id"].eq(home_team_id), -home_sign)
    rows["tactical_x"] = rows["x"] * rows["attacking_direction_sign"]

    line_metrics = (
        rows.groupby(LINE_STRUCTURE_INDEX + ["line"], dropna=False)
        .agg(
            line_player_count=("player_id", "nunique"),
            native_median_x=("x", "median"),
            tactical_median_x=("tactical_x", "median"),
            tactical_min_x=("tactical_x", "min"),
            tactical_max_x=("tactical_x", "max"),
            tactical_vertical_range=("tactical_x", lambda values: values.max() - values.min()),
            tactical_median_absolute_deviation=("tactical_x", _median_absolute_deviation),
        )
        .unstack("line")
        .reindex(columns=pd.MultiIndex.from_product([
            [
                "line_player_count", "native_median_x", "tactical_median_x",
                "tactical_min_x", "tactical_max_x", "tactical_vertical_range",
                "tactical_median_absolute_deviation",
            ], LINE_ORDER
        ]))
    )
    line_metrics.columns = [
        f"{line}_{metric}" for metric, line in line_metrics.columns
    ]

    outfield = (
        rows.groupby(LINE_STRUCTURE_INDEX, dropna=False)
        .agg(
            outfield_player_count=("player_id", "nunique"),
            outfield_native_min_x=("x", "min"),
            outfield_native_max_x=("x", "max"),
            outfield_tactical_min_x=("tactical_x", "min"),
            outfield_tactical_max_x=("tactical_x", "max"),
        )
    )
    result = team_frames.set_index(LINE_STRUCTURE_INDEX).join(outfield, how="left")
    result = result.join(line_metrics, how="left")
    result["outfield_player_count"] = result["outfield_player_count"].fillna(0).astype(int)
    for line in LINE_ORDER:
        result[f"{line}_line_available"] = result[f"{line}_line_player_count"].notna()

    result["defence_to_midfield_gap"] = (
        result["midfield_tactical_median_x"] - result["defence_tactical_median_x"]
    ).where(result["defence_line_available"] & result["midfield_line_available"])
    result["midfield_to_attack_gap"] = (
        result["attack_tactical_median_x"] - result["midfield_tactical_median_x"]
    ).where(result["midfield_line_available"] & result["attack_line_available"])
    result["total_outfield_length"] = (
        result["outfield_tactical_max_x"] - result["outfield_tactical_min_x"]
    )
    result["deepest_outfield_x"] = result["outfield_tactical_min_x"]
    result["highest_outfield_x"] = result["outfield_tactical_max_x"]
    result["deepest_defender_x"] = result["defence_tactical_min_x"]
    result["highest_attacker_x"] = result["attack_tactical_max_x"]
    result["total_outfield_vertical_range"] = result["total_outfield_length"]
    result["line_structure_complete"] = result[
        [f"{line}_line_available" for line in LINE_ORDER]
    ].all(axis=1)

    return result.sort_index()
