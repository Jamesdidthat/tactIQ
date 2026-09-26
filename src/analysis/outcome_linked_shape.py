"""Descriptive outcome-linked defensive-shape comparisons."""

from __future__ import annotations

import pandas as pd


def _distribution_summary(
    interval_rows: pd.DataFrame, group_columns: list[str]
) -> pd.DataFrame:
    """Summarise interval-level median shape values without frame weighting."""
    return (
        interval_rows.groupby(group_columns, dropna=False)
        .agg(
            interval_count=("phase_frame_start", "size"),
            median_outfield_width=("interval_median_outfield_width", "median"),
            q25_outfield_width=("interval_median_outfield_width", lambda values: values.quantile(0.25)),
            q75_outfield_width=("interval_median_outfield_width", lambda values: values.quantile(0.75)),
            median_outfield_length=("interval_median_outfield_length", "median"),
            q25_outfield_length=("interval_median_outfield_length", lambda values: values.quantile(0.25)),
            q75_outfield_length=("interval_median_outfield_length", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )


def summarize_defensive_shape_by_outcome(
    team_shape_with_context: pd.DataFrame,
    phases: pd.DataFrame,
    *,
    possession_team_id: int,
    defending_team_id: int,
    min_intervals_per_outcome: int = 5,
) -> dict[str, pd.DataFrame | int]:
    """Compare interval-level defensive shape by whether a possession led to a shot.

    Each matched source phase interval is reduced to one observation: the median
    defending team's outfield width and length across its matched tracking frames.
    This prevents longer phase intervals from receiving greater analytical weight.
    Results are descriptive and do not imply a causal relationship.
    """
    if min_intervals_per_outcome < 1:
        raise ValueError("min_intervals_per_outcome must be at least 1.")
    required_shape = {
        "tactical_phase", "possession_status", "possession_team_id",
        "phase_frame_start", "phase_frame_end", "team_possession_lead_to_shot",
        "outfield_width", "outfield_length",
    }
    missing_shape = required_shape - set(team_shape_with_context.columns)
    if missing_shape:
        raise ValueError(f"Input is missing required context columns: {sorted(missing_shape)}")
    required_phase = {"team_in_possession_id", "frame_start", "frame_end", "team_possession_lead_to_shot"}
    missing_phase = required_phase - set(phases.columns)
    if missing_phase:
        raise ValueError(f"phases is missing required columns: {sorted(missing_phase)}")

    source_intervals = phases.loc[phases["team_in_possession_id"].eq(possession_team_id)]
    source_shot_intervals = int(source_intervals["team_possession_lead_to_shot"].sum())

    rows = team_shape_with_context.reset_index()
    defending_rows = rows.loc[
        rows["team_id"].eq(defending_team_id)
        & rows["possession_team_id"].eq(possession_team_id)
        & rows["possession_status"].eq("out_of_possession")
        & rows["tactical_phase"].notna()
    ].copy()

    interval_keys = [
        "period", "phase_frame_start", "phase_frame_end", "tactical_phase",
        "team_possession_lead_to_shot",
    ]
    intervals = (
        defending_rows.groupby(interval_keys, dropna=False)
        .agg(
            matched_frame_count=("frame", "size"),
            interval_median_outfield_width=("outfield_width", "median"),
            interval_median_outfield_length=("outfield_length", "median"),
        )
        .reset_index()
        .sort_values(["period", "phase_frame_start"])
        .reset_index(drop=True)
    )
    intervals["represented_seconds"] = intervals["matched_frame_count"] / 10

    overall = _distribution_summary(intervals, ["team_possession_lead_to_shot"])

    phase_outcome_counts = (
        intervals.groupby(["tactical_phase", "team_possession_lead_to_shot"])
        .size()
        .unstack(fill_value=0)
    )
    eligible_phase_types = phase_outcome_counts.index[
        phase_outcome_counts.reindex(columns=[False, True], fill_value=0).ge(min_intervals_per_outcome).all(axis=1)
    ]
    by_defending_phase = _distribution_summary(
        intervals.loc[intervals["tactical_phase"].isin(eligible_phase_types)],
        ["tactical_phase", "team_possession_lead_to_shot"],
    )

    matched_interval_keys = set(
        map(tuple, intervals[["phase_frame_start", "phase_frame_end"]].to_numpy())
    )
    source_interval_keys = set(
        map(tuple, source_intervals[["frame_start", "frame_end"]].to_numpy())
    )
    coverage = pd.DataFrame([{
        "source_possession_intervals": len(source_intervals),
        "source_shot_leading_intervals": source_shot_intervals,
        "matched_intervals": len(intervals),
        "unmatched_source_intervals": len(source_interval_keys - matched_interval_keys),
        "min_intervals_per_outcome": min_intervals_per_outcome,
        "defending_phase_types_with_sufficient_both_outcomes": len(eligible_phase_types),
    }])

    return {
        "intervals": intervals,
        "overall": overall,
        "by_defending_phase": by_defending_phase,
        "coverage": coverage,
    }
