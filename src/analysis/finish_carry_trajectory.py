"""Descriptive matched trajectories for the overlapping finish-plus-carry subset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .attacking_sequence_audit import build_shot_sequence_descriptors
from .local_defensive_trajectory import build_local_defensive_context_trajectory


LOCAL_METRICS = [
    "defenders_within_5m", "defenders_within_10m", "defenders_within_15m",
    "defender_ball_concentration_10m", "nearest_defender_distance",
    "second_nearest_defender_distance", "third_nearest_defender_distance",
    "attackers_in_central_danger_zone", "attackers_in_defending_penalty_area_corridor",
    "attackers_without_defender_within_5m", "attackers_without_defender_within_8m",
    "defenders_nearest_to_ball_carrier_count", "defenders_nearest_to_off_ball_attacker_count",
    "off_ball_penalty_corridor_attackers_unmarked_over_3m",
    "off_ball_penalty_corridor_attackers_unmarked_over_5m",
    "off_ball_penalty_corridor_attackers_unmarked_over_8m",
    "off_ball_penalty_corridor_nearest_defender_distance_min",
    "off_ball_penalty_corridor_nearest_defender_distance_median",
    "carrier_defender_overload_2plus", "carrier_defender_overload_3plus",
    "ball_distance_to_goal_centre", "ball_angle_to_goal_degrees", "defenders_in_ball_goal_corridor",
    "minimum_defender_clearance_to_ball_goal_segment", "open_penalty_corridor_passing_options_over_1m",
    "open_penalty_corridor_passing_options_over_2m", "open_penalty_corridor_passing_options_over_3m",
    "carrier_proxy_central_route_unobstructed",
]
NORMALIZED_METRICS = [
    "total_outfield_length", "defence_tactical_median_x", "midfield_tactical_median_x",
    "attack_tactical_median_x", "deepest_defender_x", "defence_line_to_ball_distance",
    "midfield_line_to_ball_distance", "attack_line_to_ball_distance",
]
POINT_FIELDS = {"value_minus_5": -50, "value_minus_2": -20, "value_at_0": 0}
CHANGE_FIELDS = ["change_minus_5_to_0", "change_minus_2_to_0"]


def _summarize_wide_differences(
    wide: pd.DataFrame, *, group: str, source: str, point_columns: dict[str, int],
    change_columns: list[str],
) -> list[dict]:
    rows = []
    for metric, metric_rows in wide.groupby("metric"):
        for field, relative_frame in point_columns.items():
            values = metric_rows[(field, "shot")] - metric_rows[(field, "control")]
            rows.append({"comparison_group": group, "source": source, "metric": metric,
                         "measure": f"point_{relative_frame}", "relative_frame": relative_frame,
                         "pair_count": values.notna().sum(), "median_shot_minus_control": values.median(),
                         "q25": values.quantile(.25), "q75": values.quantile(.75)})
        for field in change_columns:
            values = metric_rows[(field, "shot")] - metric_rows[(field, "control")]
            rows.append({"comparison_group": group, "source": source, "metric": metric,
                         "measure": field, "relative_frame": pd.NA,
                         "pair_count": values.notna().sum(), "median_shot_minus_control": values.median(),
                         "q25": values.quantile(.25), "q75": values.quantile(.75)})
    return rows


def summarize_finish_carry_matched_trajectories(matches_root: str | Path) -> dict[str, pd.DataFrame]:
    """Compare finish+carry pairs with the disjoint open-play complement.

    Existing Team Shape and line metrics retain their phase/team baseline
    normalisation from the trajectory engine. Local ball-context values are
    raw, but their within-pair shot-minus-control differences are invariant to
    subtracting any shared team-phase baseline.
    """
    root = Path(matches_root)
    descriptors = build_shot_sequence_descriptors(root)
    matched = descriptors["open_play_matched_pairs"]
    shots = descriptors["descriptors"].merge(matched, on=["match_id", "shot_event_id"], how="inner")
    shots["comparison_group"] = "complement_open_play"
    finish_carry = shots.shot_possession_phase.eq("finish") & shots.any_carry
    shots.loc[finish_carry, "comparison_group"] = "finish_and_carry"
    group_keys = shots[["match_id", "shot_event_id", "comparison_group"]]

    local = build_local_defensive_context_trajectory(
        root, existing_trajectory={"window_features": descriptors["trajectory_window_features"]}
    )["window_values"]
    local = local.loc[local.segment.eq("open_play") & local.metric.isin(LOCAL_METRICS)].merge(
        group_keys, left_on=["match_id", "event_id"], right_on=["match_id", "shot_event_id"], how="inner"
    )
    local_wide = local.pivot(
        index=["comparison_group", "match_id", "event_id", "metric", "relative_frame"],
        columns="outcome", values="value"
    ).dropna().reset_index()
    point_rows = []
    for group, group_rows in local_wide.groupby("comparison_group"):
        for metric, metric_rows in group_rows.groupby("metric"):
            for frame in (-50, -20, 0):
                values = metric_rows.loc[metric_rows.relative_frame.eq(frame), "shot"] - metric_rows.loc[metric_rows.relative_frame.eq(frame), "control"]
                point_rows.append({"comparison_group": group, "source": "local_context", "metric": metric,
                                   "measure": f"point_{frame}", "relative_frame": frame,
                                   "pair_count": values.notna().sum(), "median_shot_minus_control": values.median(),
                                   "q25": values.quantile(.25), "q75": values.quantile(.75)})
            values_by_outcome = metric_rows.pivot(index=["match_id", "event_id"], columns="relative_frame", values=["shot", "control"])
            for start, field in [(-50, "change_minus_5_to_0"), (-20, "change_minus_2_to_0")]:
                values = (values_by_outcome[("shot", 0)] - values_by_outcome[("shot", start)]) - (values_by_outcome[("control", 0)] - values_by_outcome[("control", start)])
                point_rows.append({"comparison_group": group, "source": "local_context", "metric": metric,
                                   "measure": field, "relative_frame": pd.NA, "pair_count": values.notna().sum(),
                                   "median_shot_minus_control": values.median(), "q25": values.quantile(.25), "q75": values.quantile(.75)})

    features = descriptors["trajectory_window_features"].loc[
        lambda rows: rows.segment.eq("open_play") & rows.metric.isin(NORMALIZED_METRICS)
    ].merge(group_keys, left_on=["match_id", "event_id"], right_on=["match_id", "shot_event_id"], how="inner")
    feature_wide = features.pivot(
        index=["comparison_group", "match_id", "event_id", "metric"], columns="outcome",
        values=list(POINT_FIELDS) + CHANGE_FIELDS,
    ).dropna()
    for group, group_rows in feature_wide.groupby(level="comparison_group"):
        point_rows.extend(_summarize_wide_differences(
            group_rows, group=group, source="phase_team_normalized",
            point_columns=POINT_FIELDS, change_columns=CHANGE_FIELDS,
        ))
    coverage = shots.groupby("comparison_group").size().rename("complete_matched_pairs").reset_index()
    return {"pair_coverage": coverage, "paired_differences": pd.DataFrame(point_rows)}
