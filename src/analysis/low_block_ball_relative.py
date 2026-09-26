"""Ball-relative descriptive analysis for compact low-block intervals."""

from __future__ import annotations

import pandas as pd


BALL_RELATIVE_METRICS = {
    "defence_line_to_ball_distance": "median_defence_line_to_ball_distance",
    "midfield_line_to_ball_distance": "median_midfield_line_to_ball_distance",
    "attack_line_to_ball_distance": "median_attack_line_to_ball_distance",
    "deepest_defender_to_ball_distance": "median_deepest_defender_to_ball_distance",
    "highest_attacker_to_ball_distance": "median_highest_attacker_to_ball_distance",
}


def _summarise(relative: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    long = relative.melt(
        id_vars=group_columns,
        value_vars=list(BALL_RELATIVE_METRICS),
        var_name="metric",
        value_name="deviation_metres",
    ).dropna(subset=["deviation_metres"])
    return (
        long.groupby(group_columns + ["metric"], dropna=False)
        .agg(
            interval_count=("deviation_metres", "size"),
            median_deviation_metres=("deviation_metres", "median"),
            q25_deviation_metres=("deviation_metres", lambda values: values.quantile(0.25)),
            q75_deviation_metres=("deviation_metres", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )


def _differences(summary: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    columns = keys + [
        "metric", "non_shot_median_deviation_metres", "shot_median_deviation_metres",
        "median_difference_shot_minus_non_shot_metres",
    ]
    if summary.empty:
        return pd.DataFrame(columns=columns)
    pivot = summary.pivot(
        index=keys + ["metric"],
        columns="team_possession_lead_to_shot",
        values="median_deviation_metres",
    ).reindex(columns=[False, True])
    result = pivot.rename(columns={
        False: "non_shot_median_deviation_metres",
        True: "shot_median_deviation_metres",
    }).reset_index()
    result["median_difference_shot_minus_non_shot_metres"] = (
        result["shot_median_deviation_metres"] - result["non_shot_median_deviation_metres"]
    )
    return result[columns]


def compare_low_block_ball_relative_by_shot_outcome(
    intervals: pd.DataFrame,
    *,
    min_intervals_per_team_outcome: int = 5,
) -> dict[str, pd.DataFrame]:
    """Compare team-relative low-block line-to-ball distances by shot outcome.

    Frame-level signed distances use ``line_normalized_x - ball_normalized_x``:
    positive values place the line nearer the opponent's goal than the ball.
    Intervals require complete line structure; a missing ball leaves only that
    metric unavailable, without frame or interval imputation. Baselines are
    each defending team's eligible low-block median for the corresponding metric.
    """
    required = {
        "defending_phase_type", "defending_team_id", "defending_team_acronym",
        "team_possession_lead_to_shot", "matched_frame_count", "complete_line_frame_count",
        "ball_available_frame_count", "defending_half_ball_frame_count", "ball_depth_zone",
        *BALL_RELATIVE_METRICS.values(),
    }
    missing = required - set(intervals.columns)
    if missing:
        raise ValueError(f"intervals is missing required columns: {sorted(missing)}")
    if min_intervals_per_team_outcome < 1:
        raise ValueError("min_intervals_per_team_outcome must be at least 1.")

    low_block = intervals.loc[intervals["defending_phase_type"].eq("low_block")].copy()
    complete = low_block.loc[
        low_block["matched_frame_count"].gt(0)
        & low_block["complete_line_frame_count"].eq(low_block["matched_frame_count"])
    ].copy()
    matched_frames = int(complete["matched_frame_count"].sum())
    ball_frames = int(complete["ball_available_frame_count"].sum())
    quality = pd.DataFrame([{
        "low_block_intervals": len(low_block),
        "complete_line_intervals": len(complete),
        "incomplete_line_intervals": len(low_block) - len(complete),
        "matched_frame_count": matched_frames,
        "ball_available_frame_count": ball_frames,
        "missing_ball_frame_count": matched_frames - ball_frames,
        "ball_frame_coverage": ball_frames / matched_frames if matched_frames else float("nan"),
        "intervals_without_ball": int(complete["ball_available_frame_count"].eq(0).sum()),
        "intervals_with_defending_half_ball": int(complete["ball_depth_zone"].notna().sum()),
    }])
    if complete.empty:
        empty = pd.DataFrame(columns=[
            "team_possession_lead_to_shot", "metric", "interval_count",
            "median_deviation_metres", "q25_deviation_metres", "q75_deviation_metres",
        ])
        return {
            "quality": quality, "pooled": empty,
            "pooled_median_differences": _differences(empty, []),
            "pooled_by_ball_depth_zone": empty,
            "pooled_zone_median_differences": _differences(empty, ["ball_depth_zone"]),
            "per_team": empty,
            "per_team_median_differences": _differences(empty, [
                "defending_team_id", "defending_team_acronym"
            ]),
        }

    source_columns = list(BALL_RELATIVE_METRICS.values())
    baselines = complete.groupby("defending_team_id")[source_columns].median().rename(
        columns={column: f"baseline_{column}" for column in source_columns}
    )
    relative = complete.join(baselines, on="defending_team_id")
    for metric, source_column in BALL_RELATIVE_METRICS.items():
        relative[metric] = relative[source_column] - relative[f"baseline_{source_column}"]

    outcome = "team_possession_lead_to_shot"
    pooled = _summarise(relative, [outcome])
    pooled_differences = _differences(pooled, [])
    zoned = relative.loc[relative["ball_depth_zone"].notna()]
    pooled_by_zone = _summarise(zoned, ["ball_depth_zone", outcome])
    pooled_zone_differences = _differences(pooled_by_zone, ["ball_depth_zone"])

    # Require enough available-ball observations for every outcome and metric.
    available = relative.dropna(subset=list(BALL_RELATIVE_METRICS))
    counts = available.groupby(["defending_team_id", outcome]).size().unstack(fill_value=0)
    eligible_teams = counts.index[
        counts.reindex(columns=[False, True], fill_value=0)
        .ge(min_intervals_per_team_outcome).all(axis=1)
    ]
    per_team = _summarise(
        relative.loc[relative["defending_team_id"].isin(eligible_teams)],
        ["defending_team_id", "defending_team_acronym", outcome],
    )
    per_team_differences = _differences(
        per_team, ["defending_team_id", "defending_team_acronym"]
    )
    return {
        "quality": quality,
        "pooled": pooled,
        "pooled_median_differences": pooled_differences,
        "pooled_by_ball_depth_zone": pooled_by_zone,
        "pooled_zone_median_differences": pooled_zone_differences,
        "per_team": per_team,
        "per_team_median_differences": per_team_differences,
    }
