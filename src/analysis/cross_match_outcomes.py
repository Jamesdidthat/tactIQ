"""Cross-match descriptive comparisons of interval-level defensive shape."""

from __future__ import annotations

import pandas as pd


def _outcome_summary(rows: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    return (
        rows.groupby(group_columns, dropna=False)
        .agg(
            interval_count=("match_id", "size"),
            median_outfield_width=("median_outfield_width", "median"),
            q25_outfield_width=("median_outfield_width", lambda values: values.quantile(0.25)),
            q75_outfield_width=("median_outfield_width", lambda values: values.quantile(0.75)),
            median_outfield_length=("median_outfield_length", "median"),
            q25_outfield_length=("median_outfield_length", lambda values: values.quantile(0.25)),
            q75_outfield_length=("median_outfield_length", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )


def _median_difference(summary: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    metrics = ["median_outfield_width", "median_outfield_length"]
    difference_columns = group_columns + [
        "median_width_difference_shot_minus_non_shot",
        "median_length_difference_shot_minus_non_shot",
    ]
    if summary.empty:
        return pd.DataFrame(columns=difference_columns)
    if not group_columns:
        by_outcome = summary.set_index("team_possession_lead_to_shot")
        return pd.DataFrame([{
            "median_width_difference_shot_minus_non_shot": (
                by_outcome.loc[True, "median_outfield_width"]
                - by_outcome.loc[False, "median_outfield_width"]
            ),
            "median_length_difference_shot_minus_non_shot": (
                by_outcome.loc[True, "median_outfield_length"]
                - by_outcome.loc[False, "median_outfield_length"]
            ),
        }])
    pivot = summary.pivot(index=group_columns, columns="team_possession_lead_to_shot", values=metrics)
    pivot = pivot.reindex(columns=pd.MultiIndex.from_product([metrics, [False, True]]))
    result = pivot.reset_index()
    result["median_width_difference_shot_minus_non_shot"] = (
        result[("median_outfield_width", True)] - result[("median_outfield_width", False)]
    )
    result["median_length_difference_shot_minus_non_shot"] = (
        result[("median_outfield_length", True)] - result[("median_outfield_length", False)]
    )
    result.columns = [column if isinstance(column, str) else column[0] for column in result.columns]
    return result[difference_columns]


def compare_defensive_shape_by_shot_outcome(
    intervals: pd.DataFrame,
    processing_log: pd.DataFrame,
    *,
    min_intervals_per_outcome: int = 5,
) -> dict[str, pd.DataFrame]:
    """Describe shot vs non-shot interval shape, including team-relative values.

    The input is already one row per defending-team/opposition-phase interval;
    this function does no duration weighting and makes no causal inference.
    """
    required = {
        "match_id", "defending_team_id", "defending_team_acronym",
        "team_possession_lead_to_shot", "median_outfield_width", "median_outfield_length",
    }
    missing = required - set(intervals.columns)
    if missing:
        raise ValueError(f"intervals is missing required columns: {sorted(missing)}")
    if min_intervals_per_outcome < 1:
        raise ValueError("min_intervals_per_outcome must be at least 1.")

    rows = intervals.copy()
    outcome_column = "team_possession_lead_to_shot"
    pooled = _outcome_summary(rows, [outcome_column])
    pooled_differences = _median_difference(pooled, [])

    team_baselines = rows.groupby("defending_team_id")[
        ["median_outfield_width", "median_outfield_length"]
    ].median().rename(columns={
        "median_outfield_width": "team_median_defensive_width",
        "median_outfield_length": "team_median_defensive_length",
    })
    relative_rows = rows.join(team_baselines, on="defending_team_id")
    relative_rows["median_outfield_width"] = (
        relative_rows["median_outfield_width"] - relative_rows["team_median_defensive_width"]
    )
    relative_rows["median_outfield_length"] = (
        relative_rows["median_outfield_length"] - relative_rows["team_median_defensive_length"]
    )
    team_relative = _outcome_summary(relative_rows, [outcome_column])
    team_relative_differences = _median_difference(team_relative, [])

    team_counts = rows.groupby(["defending_team_id", outcome_column]).size().unstack(fill_value=0)
    eligible_team_ids = team_counts.index[
        team_counts.reindex(columns=[False, True], fill_value=0).ge(min_intervals_per_outcome).all(axis=1)
    ]
    by_team = _outcome_summary(
        rows.loc[rows["defending_team_id"].isin(eligible_team_ids)],
        ["defending_team_id", "defending_team_acronym", outcome_column],
    )
    by_team_differences = _median_difference(
        by_team, ["defending_team_id", "defending_team_acronym"]
    )

    skipped_matches = processing_log.loc[
        processing_log["status"].eq("skipped"), ["match_id", "status", "message"]
    ].copy()
    return {
        "pooled": pooled,
        "pooled_median_differences": pooled_differences,
        "team_relative": team_relative,
        "team_relative_median_differences": team_relative_differences,
        "by_team": by_team,
        "by_team_median_differences": by_team_differences,
        "skipped_matches": skipped_matches,
    }


def compare_phase_relative_defensive_shape_by_shot_outcome(
    intervals: pd.DataFrame,
    *,
    pooled_min_intervals_per_outcome: int = 10,
    team_phase_min_intervals_per_outcome: int = 5,
) -> dict[str, pd.DataFrame]:
    """Compare shot outcomes after centring shape within team and defensive phase.

    Every interval's width and length are expressed as deviations from its
    defending team's median within the same ``defending_phase_type``. The input
    remains interval-level, so long possessions are not weighted more heavily.
    """
    required = {
        "match_id", "defending_team_id", "defending_team_acronym",
        "defending_phase_type", "team_possession_lead_to_shot",
        "median_outfield_width", "median_outfield_length",
    }
    missing = required - set(intervals.columns)
    if missing:
        raise ValueError(f"intervals is missing required columns: {sorted(missing)}")
    if pooled_min_intervals_per_outcome < 1 or team_phase_min_intervals_per_outcome < 1:
        raise ValueError("Minimum interval thresholds must be at least 1.")

    rows = intervals.copy()
    outcome = "team_possession_lead_to_shot"
    baseline = rows.groupby(["defending_team_id", "defending_phase_type"])[
        ["median_outfield_width", "median_outfield_length"]
    ].median().rename(columns={
        "median_outfield_width": "team_phase_baseline_width",
        "median_outfield_length": "team_phase_baseline_length",
    })
    relative_rows = rows.join(baseline, on=["defending_team_id", "defending_phase_type"])
    relative_rows["median_outfield_width"] = (
        relative_rows["median_outfield_width"] - relative_rows["team_phase_baseline_width"]
    )
    relative_rows["median_outfield_length"] = (
        relative_rows["median_outfield_length"] - relative_rows["team_phase_baseline_length"]
    )

    pooled_counts = relative_rows.groupby(["defending_phase_type", outcome]).size().unstack(fill_value=0)
    eligible_phases = pooled_counts.index[
        pooled_counts.reindex(columns=[False, True], fill_value=0)
        .ge(pooled_min_intervals_per_outcome).all(axis=1)
    ]
    pooled = _outcome_summary(
        relative_rows.loc[relative_rows["defending_phase_type"].isin(eligible_phases)],
        ["defending_phase_type", outcome],
    )
    pooled_differences = _median_difference(pooled, ["defending_phase_type"])

    team_phase_counts = relative_rows.groupby(
        ["defending_team_id", "defending_team_acronym", "defending_phase_type", outcome]
    ).size().unstack(fill_value=0)
    eligible_team_phases = team_phase_counts.index[
        team_phase_counts.reindex(columns=[False, True], fill_value=0)
        .ge(team_phase_min_intervals_per_outcome).all(axis=1)
    ]
    indexed_rows = relative_rows.set_index(
        ["defending_team_id", "defending_team_acronym", "defending_phase_type"], drop=False
    )
    by_team_phase = _outcome_summary(
        indexed_rows.loc[indexed_rows.index.isin(eligible_team_phases)].reset_index(drop=True),
        ["defending_team_id", "defending_team_acronym", "defending_phase_type", outcome],
    )
    by_team_phase_differences = _median_difference(
        by_team_phase,
        ["defending_team_id", "defending_team_acronym", "defending_phase_type"],
    )
    return {
        "pooled_by_phase": pooled,
        "pooled_phase_median_differences": pooled_differences,
        "per_team_phase": by_team_phase,
        "per_team_phase_median_differences": by_team_phase_differences,
    }
