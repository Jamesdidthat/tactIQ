"""Descriptive Team Shape summaries grouped by tactical phase."""

from __future__ import annotations

import pandas as pd


SUMMARY_COLUMNS = [
    "team_id",
    "team_acronym",
    "possession_status",
    "tactical_phase",
    "frame_count",
    "represented_seconds",
    "phase_interval_count",
    "median_outfield_width",
    "q25_outfield_width",
    "q75_outfield_width",
    "median_outfield_length",
    "q25_outfield_length",
    "q75_outfield_length",
]


def summarize_phase_shape(team_shape_with_context: pd.DataFrame) -> pd.DataFrame:
    """Summarise native-coordinate Team Shape by team and tactical phase.

    Unlabelled Team Shape rows are excluded. In- and out-of-possession contexts
    remain separate through ``possession_status``. Values are descriptive only:
    no directional normalisation, tactical conclusion, or causal claim is made.
    """
    required_index = {"frame", "period", "team_id", "team_acronym"}
    if not required_index.issubset(team_shape_with_context.index.names):
        raise ValueError("Input must retain the Team Shape frame/team MultiIndex.")

    required_columns = {
        "tactical_phase",
        "possession_status",
        "phase_frame_start",
        "phase_frame_end",
        "possession_team_id",
        "outfield_width",
        "outfield_length",
    }
    missing = required_columns - set(team_shape_with_context.columns)
    if missing:
        raise ValueError(f"Input is missing required context columns: {sorted(missing)}")

    rows = team_shape_with_context.reset_index()
    rows = rows.loc[rows["tactical_phase"].notna()].copy()
    group_columns = ["team_id", "team_acronym", "possession_status", "tactical_phase"]
    if rows.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    summary = (
        rows.groupby(group_columns, dropna=False)
        .agg(
            frame_count=("frame", "size"),
            median_outfield_width=("outfield_width", "median"),
            q25_outfield_width=("outfield_width", lambda values: values.quantile(0.25)),
            q75_outfield_width=("outfield_width", lambda values: values.quantile(0.75)),
            median_outfield_length=("outfield_length", "median"),
            q25_outfield_length=("outfield_length", lambda values: values.quantile(0.25)),
            q75_outfield_length=("outfield_length", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )

    interval_counts = (
        rows.groupby(group_columns, dropna=False)
        .apply(
            lambda group: group[
                ["possession_team_id", "phase_frame_start", "phase_frame_end"]
            ].drop_duplicates().shape[0],
            include_groups=False,
        )
        .rename("phase_interval_count")
        .reset_index()
    )
    summary = summary.merge(interval_counts, on=group_columns, validate="one_to_one")
    summary["represented_seconds"] = summary["frame_count"] / 10
    return summary[SUMMARY_COLUMNS].sort_values(group_columns).reset_index(drop=True)
