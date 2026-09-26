"""Ball-centred local defensive context from SkillCorner tracking."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .defensive_line_structure import POSITION_GROUP_TO_LINE, _home_attacking_signs


LOCAL_CONTEXT_COLUMNS = [
    "frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym",
    "ball_x", "ball_y", "ball_normalized_x", "nearest_defender_distance",
    "second_nearest_defender_distance", "third_nearest_defender_distance",
    "defenders_within_5m", "defenders_within_10m", "defenders_within_15m",
    "defending_outfield_goal_side_count", "defenders_within_local_radius",
    "attackers_within_local_radius", "local_numerical_balance",
    "attackers_goal_side_of_ball_count", "attackers_ahead_of_nearest_defender_count",
    "attackers_without_defender_within_3m", "attackers_without_defender_within_5m",
    "attackers_without_defender_within_8m", "attacker_nearest_defender_distance_median",
    "attacker_nearest_defender_distance_max", "attackers_between_defence_and_midfield_count",
    "attackers_in_defending_penalty_area_corridor", "attackers_in_central_danger_zone",
    "defender_ball_concentration_10m",
    "defence_line_to_ball_distance", "ball_between_defence_and_midfield",
    "nearest_defender_line_separation",
]


def extract_ball_tracking(tracking_raw: pd.DataFrame) -> pd.DataFrame:
    """Extract ball coordinates without altering the raw tracking dataframe."""
    required = {"frame", "timestamp", "elapsed_seconds", "period", "ball_data"}
    missing = required - set(tracking_raw.columns)
    if missing:
        raise ValueError(f"tracking_raw is missing required columns: {sorted(missing)}")
    rows = []
    for record in tracking_raw[["frame", "timestamp", "elapsed_seconds", "period", "ball_data"]].itertuples(index=False):
        ball = record.ball_data or {}
        rows.append({"frame": record.frame, "timestamp": record.timestamp,
                     "elapsed_seconds": record.elapsed_seconds, "period": record.period,
                     "ball_x": ball.get("x"), "ball_y": ball.get("y")})
    return pd.DataFrame(rows)


def calculate_local_defensive_context(
    tracking_players: pd.DataFrame,
    ball_tracking: pd.DataFrame,
    line_structure: pd.DataFrame,
    match_info: Mapping,
    *,
    local_radius_metres: float = 10.0,
) -> pd.DataFrame:
    """Calculate local ball context for each represented team-frame.

    A defender is any tracked, non-goalkeeper player on the focal team; an
    attacker is a non-goalkeeper player on the opposing team. Distances are
    Euclidean native-pitch metres. Goal-side and line features use the existing
    team-relative coordinate: lower tactical x is closer to the focal team's
    own goal. Missing ball, focal-player, opponent-player, or line data stays
    missing; no player position is inferred.

    ``nearest_defender_line_separation`` is the absolute tactical-x distance
    from the nearest defender to the median of the *other* mapped defenders.
    It is unavailable when that player is not mapped to the defensive line or
    there is no other mapped defender.

    Attacker coverage is evaluated in the focal defending team's tactical
    coordinates. "Goal-side" and "ahead" mean lower tactical x (closer to the
    focal team's goal). The penalty-area corridor is tactical x <= -36.0 m and
    |y| <= 20.16 m; the central danger zone is the central defending half
    (tactical x < 0 and |y| <= 20.16 m). These thresholds use a 105 x 68 m
    pitch and are deliberately explicit rather than inferred from events.
    """
    if local_radius_metres <= 0:
        raise ValueError("local_radius_metres must be positive.")
    player_required = {"frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "player_id", "position", "position_group", "x", "y"}
    ball_required = {"frame", "timestamp", "elapsed_seconds", "period", "ball_x", "ball_y"}
    missing = player_required - set(tracking_players.columns)
    if missing:
        raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")
    missing = ball_required - set(ball_tracking.columns)
    if missing:
        raise ValueError(f"ball_tracking is missing required columns: {sorted(missing)}")

    home_id = match_info["home_team"]["id"]
    team_ids = {home_id, match_info["away_team"]["id"]}
    signs = _home_attacking_signs(match_info)
    keys = ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
    team_frames = tracking_players[keys].drop_duplicates().copy()
    if not set(team_frames.team_id.dropna()).issubset(team_ids):
        raise ValueError("tracking_players contains a team absent from match_info.")
    balls = ball_tracking.drop_duplicates(["frame", "period"])
    if balls.duplicated(["frame", "period"]).any():
        raise ValueError("ball_tracking must have at most one row per frame and period.")
    lines = line_structure.reset_index()
    line_columns = ["frame", "period", "team_id", "defence_tactical_median_x", "midfield_tactical_median_x"]
    missing = set(line_columns) - set(lines.columns)
    if missing:
        raise ValueError(f"line_structure is missing required columns: {sorted(missing)}")
    ball_by_frame = {
        (row.frame, row.period): row
        for row in balls[["frame", "period", "ball_x", "ball_y"]].itertuples(index=False)
    }
    line_by_team_frame = {
        (row.frame, row.period, row.team_id): row
        for row in lines[line_columns].itertuples(index=False)
    }

    available = tracking_players.loc[tracking_players.x.notna() & tracking_players.y.notna()].copy()
    available["is_outfield"] = available.position.ne("Goalkeeper")
    available["tactical_sign"] = available.period.astype(int).map(signs)
    available.loc[available.team_id.ne(home_id), "tactical_sign"] *= -1
    available["tactical_x"] = available.x * available.tactical_sign
    groups = {key: group for key, group in available.groupby(["frame", "period", "team_id"], sort=False)}
    rows = []
    for team_frame in team_frames.itertuples(index=False):
        frame, timestamp, elapsed, period, team_id, acronym = team_frame
        base = {"frame": frame, "timestamp": timestamp, "elapsed_seconds": elapsed, "period": period, "team_id": team_id, "team_acronym": acronym}
        ball = ball_by_frame.get((frame, period))
        if ball is None or pd.isna(ball.ball_x) or pd.isna(ball.ball_y):
            rows.append(base)
            continue
        bx, by = ball.ball_x, ball.ball_y
        sign = signs[int(period)] * (1 if team_id == home_id else -1)
        base.update({"ball_x": bx, "ball_y": by, "ball_normalized_x": bx * sign})
        defenders = groups.get((frame, period, team_id))
        opponent_id = next((candidate for candidate in team_ids if candidate != team_id), None)
        opponents = groups.get((frame, period, opponent_id))
        if defenders is None:
            rows.append(base)
            continue
        defenders = defenders.loc[defenders.is_outfield]
        if defenders.empty:
            rows.append(base)
            continue
        distances = np.hypot(defenders.x.to_numpy() - bx, defenders.y.to_numpy() - by)
        distances.sort()
        nearest_index = defenders.index[np.argmin(np.hypot(defenders.x - bx, defenders.y - by))]
        nearest = defenders.loc[nearest_index]
        base.update({
            "nearest_defender_distance": distances[0],
            "second_nearest_defender_distance": distances[1] if len(distances) > 1 else np.nan,
            "third_nearest_defender_distance": distances[2] if len(distances) > 2 else np.nan,
            "defenders_within_5m": int((distances <= 5).sum()),
            "defenders_within_10m": int((distances <= 10).sum()),
            "defenders_within_15m": int((distances <= 15).sum()),
            "defending_outfield_goal_side_count": int((defenders.tactical_x < bx * sign).sum()),
            "defenders_within_local_radius": int((distances <= local_radius_metres).sum()),
            "defender_ball_concentration_10m": float((distances <= 10).sum() / len(defenders)),
        })
        if opponents is not None:
            attackers = opponents.loc[opponents.is_outfield]
            attacker_distances = np.hypot(attackers.x.to_numpy() - bx, attackers.y.to_numpy() - by)
            base["attackers_within_local_radius"] = int((attacker_distances <= local_radius_metres).sum())
            base["local_numerical_balance"] = base["defenders_within_local_radius"] - base["attackers_within_local_radius"]
            if not attackers.empty:
                attackers_focal_x = attackers.x * sign
                attacker_defender_distances = np.hypot(
                    attackers.x.to_numpy()[:, None] - defenders.x.to_numpy()[None, :],
                    attackers.y.to_numpy()[:, None] - defenders.y.to_numpy()[None, :],
                )
                nearest_to_attacker = attacker_defender_distances.min(axis=1)
                base.update({
                    "attackers_goal_side_of_ball_count": int((attackers_focal_x < bx * sign).sum()),
                    "attackers_ahead_of_nearest_defender_count": int((attackers_focal_x < nearest.tactical_x).sum()),
                    "attackers_without_defender_within_3m": int((nearest_to_attacker > 3).sum()),
                    "attackers_without_defender_within_5m": int((nearest_to_attacker > 5).sum()),
                    "attackers_without_defender_within_8m": int((nearest_to_attacker > 8).sum()),
                    "attacker_nearest_defender_distance_median": float(np.median(nearest_to_attacker)),
                    "attacker_nearest_defender_distance_max": float(np.max(nearest_to_attacker)),
                    "attackers_in_defending_penalty_area_corridor": int(((attackers_focal_x <= -36) & (attackers.y.abs() <= 20.16)).sum()),
                    "attackers_in_central_danger_zone": int(((attackers_focal_x < 0) & (attackers.y.abs() <= 20.16)).sum()),
                })
        line = line_by_team_frame.get((frame, period, team_id))
        if line is not None:
            defence_x, midfield_x = line.defence_tactical_median_x, line.midfield_tactical_median_x
            if pd.notna(defence_x): base["defence_line_to_ball_distance"] = defence_x - bx * sign
            if pd.notna(defence_x) and pd.notna(midfield_x):
                base["ball_between_defence_and_midfield"] = bool(min(defence_x, midfield_x) <= bx * sign <= max(defence_x, midfield_x))
                base["attackers_between_defence_and_midfield_count"] = int(
                    ((attackers.x * sign >= min(defence_x, midfield_x))
                     & (attackers.x * sign <= max(defence_x, midfield_x))).sum()
                ) if opponents is not None and not attackers.empty else np.nan
        rest = defenders.loc[(defenders.index != nearest_index) & defenders.position_group.map(POSITION_GROUP_TO_LINE).eq("defence")]
        if POSITION_GROUP_TO_LINE.get(nearest.position_group) == "defence" and not rest.empty:
            base["nearest_defender_line_separation"] = abs(nearest.tactical_x - rest.tactical_x.median())
        rows.append(base)
    result = pd.DataFrame(rows)
    for column in LOCAL_CONTEXT_COLUMNS:
        if column not in result: result[column] = np.nan
    return result[LOCAL_CONTEXT_COLUMNS].sort_values(["frame", "team_id"]).reset_index(drop=True)
