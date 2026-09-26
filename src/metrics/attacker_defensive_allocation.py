"""Attacker-level marking allocation using an explicit nearest-ball proxy."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .defensive_line_structure import _home_attacking_signs


ALLOCATION_METRICS = [
    "defenders_nearest_to_ball_carrier_count", "defenders_nearest_to_off_ball_attacker_count",
    "off_ball_penalty_corridor_attackers_unmarked_over_3m",
    "off_ball_penalty_corridor_attackers_unmarked_over_5m",
    "off_ball_penalty_corridor_attackers_unmarked_over_8m",
    "off_ball_penalty_corridor_nearest_defender_distance_min",
    "off_ball_penalty_corridor_nearest_defender_distance_median",
    "carrier_defender_overload_2plus", "carrier_defender_overload_3plus",
]


def calculate_attacker_defensive_allocation(
    tracking_players: pd.DataFrame, ball_tracking: pd.DataFrame, match_info: Mapping,
) -> dict[str, pd.DataFrame]:
    """Calculate frame metrics and attacker-level marking context.

    The attacking player closest to the ball is labelled
    ``is_ball_carrier_proxy``. This is only a geometric proxy: it is never
    presented as verified possession. Every other attacking outfield player is
    off-ball. A defender is allocated to the attacker nearest to that defender
    by Euclidean pitch distance. The penalty corridor is the focal defending
    team's tactical x <= -36m and |y| <= 20.16m.
    """
    required = {"frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "player_id", "position", "x", "y"}
    missing = required - set(tracking_players.columns)
    if missing:
        raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")
    ball_required = {"frame", "period", "ball_x", "ball_y"}
    missing = ball_required - set(ball_tracking.columns)
    if missing:
        raise ValueError(f"ball_tracking is missing required columns: {sorted(missing)}")
    home_id = match_info["home_team"]["id"]
    team_ids = {home_id, match_info["away_team"]["id"]}
    signs = _home_attacking_signs(match_info)
    keys = ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
    team_frames = tracking_players[keys].drop_duplicates()
    available = tracking_players.loc[tracking_players.x.notna() & tracking_players.y.notna() & tracking_players.position.ne("Goalkeeper")].copy()
    groups = {key: group for key, group in available.groupby(["frame", "period", "team_id"], sort=False)}
    balls = { (row.frame, row.period): row for row in ball_tracking.drop_duplicates(["frame", "period"])[["frame", "period", "ball_x", "ball_y"]].itertuples(index=False) }
    frame_rows, attacker_rows = [], []
    for row in team_frames.itertuples(index=False):
        frame, timestamp, elapsed, period, defending_id, acronym = row
        base = {"frame": frame, "timestamp": timestamp, "elapsed_seconds": elapsed, "period": period, "team_id": defending_id, "team_acronym": acronym}
        ball = balls.get((frame, period))
        attacking_id = next((team_id for team_id in team_ids if team_id != defending_id), None)
        defenders = groups.get((frame, period, defending_id))
        attackers = groups.get((frame, period, attacking_id))
        if ball is None or pd.isna(ball.ball_x) or pd.isna(ball.ball_y) or defenders is None or attackers is None or defenders.empty or attackers.empty:
            frame_rows.append(base)
            continue
        bx, by = ball.ball_x, ball.ball_y
        sign = signs[int(period)] * (1 if defending_id == home_id else -1)
        attacker_ball_distance = np.hypot(attackers.x.to_numpy() - bx, attackers.y.to_numpy() - by)
        carrier_position = int(attacker_ball_distance.argmin())
        distances = np.hypot(
            attackers.x.to_numpy()[:, None] - defenders.x.to_numpy()[None, :],
            attackers.y.to_numpy()[:, None] - defenders.y.to_numpy()[None, :],
        )
        nearest_defender = distances.min(axis=1)
        defender_nearest_attacker = distances.argmin(axis=0)
        carrier_defenders = int((defender_nearest_attacker == carrier_position).sum())
        off_ball = np.arange(len(attackers)) != carrier_position
        tactical_x = attackers.x.to_numpy() * sign
        corridor = (tactical_x <= -36) & (np.abs(attackers.y.to_numpy()) <= 20.16)
        off_ball_corridor = off_ball & corridor
        base.update({
            "defenders_nearest_to_ball_carrier_count": carrier_defenders,
            "defenders_nearest_to_off_ball_attacker_count": int((defender_nearest_attacker != carrier_position).sum()),
            "off_ball_penalty_corridor_attackers_unmarked_over_3m": int((off_ball_corridor & (nearest_defender > 3)).sum()),
            "off_ball_penalty_corridor_attackers_unmarked_over_5m": int((off_ball_corridor & (nearest_defender > 5)).sum()),
            "off_ball_penalty_corridor_attackers_unmarked_over_8m": int((off_ball_corridor & (nearest_defender > 8)).sum()),
            "off_ball_penalty_corridor_nearest_defender_distance_min": float(nearest_defender[off_ball_corridor].min()) if off_ball_corridor.any() else np.nan,
            "off_ball_penalty_corridor_nearest_defender_distance_median": float(np.median(nearest_defender[off_ball_corridor])) if off_ball_corridor.any() else np.nan,
            "carrier_defender_overload_2plus": carrier_defenders >= 2,
            "carrier_defender_overload_3plus": carrier_defenders >= 3,
        })
        for position, attacker in enumerate(attackers.itertuples(index=False)):
            attacker_rows.append({**base, "attacking_team_id": attacking_id, "attacker_player_id": attacker.player_id,
                                  "attacker_x": attacker.x, "attacker_y": attacker.y,
                                  "attacker_tactical_x_in_defending_coordinates": tactical_x[position],
                                  "attacker_ball_distance": attacker_ball_distance[position],
                                  "nearest_defender_distance": nearest_defender[position],
                                  "is_ball_carrier_proxy": position == carrier_position,
                                  "is_off_ball": position != carrier_position,
                                  "in_defending_penalty_corridor": corridor[position]})
        frame_rows.append(base)
    frame_metrics = pd.DataFrame(frame_rows)
    for column in ALLOCATION_METRICS:
        if column not in frame_metrics:
            frame_metrics[column] = np.nan
    return {"frame_metrics": frame_metrics, "attacker_context": pd.DataFrame(attacker_rows)}
