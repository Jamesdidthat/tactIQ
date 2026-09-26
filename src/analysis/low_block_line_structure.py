"""Outcome-linked low-block comparisons using interval-level line structure."""

from __future__ import annotations

import pandas as pd


LINE_METRICS = {
    "defence_to_midfield_gap": "median_defence_to_midfield_gap",
    "midfield_to_attack_gap": "median_midfield_to_attack_gap",
    "defence_line_position": "median_defence_tactical_median_x",
    "midfield_line_position": "median_midfield_tactical_median_x",
    "attack_line_position": "median_attack_tactical_median_x",
    "total_outfield_length": "median_total_outfield_length",
    "defence_line_range": "median_defence_tactical_vertical_range",
    "midfield_line_range": "median_midfield_tactical_vertical_range",
    "attack_line_range": "median_attack_tactical_vertical_range",
    "defence_line_median_absolute_deviation": "median_defence_tactical_median_absolute_deviation",
    "midfield_line_median_absolute_deviation": "median_midfield_tactical_median_absolute_deviation",
    "attack_line_median_absolute_deviation": "median_attack_tactical_median_absolute_deviation",
    "deepest_defender_position": "median_deepest_defender_x",
    "highest_attacker_position": "median_highest_attacker_x",
    "total_vertical_range": "median_total_outfield_vertical_range",
}


def _summarise(rows: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    """Return outcome summaries in long metric form."""
    long_rows = rows.melt(
        id_vars=group_columns,
        value_vars=list(LINE_METRICS),
        var_name="metric",
        value_name="deviation_metres",
    )
    return (
        long_rows.groupby(group_columns + ["metric"], dropna=False)
        .agg(
            interval_count=("deviation_metres", "size"),
            median_deviation_metres=("deviation_metres", "median"),
            q25_deviation_metres=("deviation_metres", lambda values: values.quantile(0.25)),
            q75_deviation_metres=("deviation_metres", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )


def _differences(summary: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=keys + [
            "metric", "median_difference_shot_minus_non_shot_metres"
        ])
    pivot = summary.pivot(
        index=keys + ["metric"],
        columns="team_possession_lead_to_shot",
        values="median_deviation_metres",
    ).reindex(columns=[False, True])
    return pivot.rename(columns={
        False: "non_shot_median_deviation_metres",
        True: "shot_median_deviation_metres",
    }).assign(
        median_difference_shot_minus_non_shot_metres=lambda values: (
            values["shot_median_deviation_metres"]
            - values["non_shot_median_deviation_metres"]
        )
    ).reset_index()


def compare_low_block_line_structure_by_shot_outcome(
    intervals: pd.DataFrame,
    *,
    min_intervals_per_team_outcome: int = 5,
) -> dict[str, pd.DataFrame]:
    """Describe shot outcomes after low-block team-relative line normalisation.

    An interval is eligible only if its line structure is complete for every
    represented tracking frame. Each eligible interval's metric is centred on
    the defending team's median for that metric across its eligible low-block
    intervals. This is descriptive, one-observation-per-interval analysis.
    """
    required = {
        "defending_phase_type", "defending_team_id", "defending_team_acronym",
        "team_possession_lead_to_shot", "matched_frame_count", "complete_line_frame_count",
        *LINE_METRICS.values(),
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
    excluded = low_block.loc[~low_block.index.isin(complete.index)].copy()

    quality = pd.DataFrame([{
        "low_block_intervals": len(low_block),
        "complete_line_intervals": len(complete),
        "excluded_incomplete_line_mapping": len(excluded),
    }])
    if complete.empty:
        empty_summary = pd.DataFrame(columns=[
            "team_possession_lead_to_shot", "metric", "interval_count",
            "median_deviation_metres", "q25_deviation_metres", "q75_deviation_metres",
        ])
        return {
            "quality": quality,
            "pooled": empty_summary,
            "pooled_median_differences": _differences(empty_summary, []),
            "per_team": empty_summary,
            "per_team_median_differences": _differences(empty_summary, [
                "defending_team_id", "defending_team_acronym"
            ]),
        }

    baseline_columns = list(LINE_METRICS.values())
    baselines = complete.groupby("defending_team_id")[baseline_columns].median().rename(
        columns={column: f"baseline_{column}" for column in baseline_columns}
    )
    relative = complete.join(baselines, on="defending_team_id")
    for metric, column in LINE_METRICS.items():
        relative[metric] = relative[column] - relative[f"baseline_{column}"]

    outcome = "team_possession_lead_to_shot"
    pooled = _summarise(relative, [outcome])
    pooled_differences = _differences(pooled, [])

    counts = relative.groupby(["defending_team_id", outcome]).size().unstack(fill_value=0)
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
        "per_team": per_team,
        "per_team_median_differences": per_team_differences,
    }
