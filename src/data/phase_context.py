"""Expand SkillCorner phase intervals into team-frame tactical context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


CONTEXT_COLUMNS = [
    "match_id",
    "frame",
    "period",
    "team_id",
    "possession_status",
    "tactical_phase",
    "possession_team_id",
    "phase_frame_start",
    "phase_frame_end",
    "phase_duration",
    "team_possession_lead_to_shot",
    "team_possession_lead_to_goal",
]

JOIN_KEYS = ["frame", "period", "team_id"]


def _match_team_ids(match_info: Mapping[str, Any]) -> set[int]:
    return {match_info["home_team"]["id"], match_info["away_team"]["id"]}


def expand_phase_context(
    phases: pd.DataFrame, match_info: Mapping[str, Any]
) -> pd.DataFrame:
    """Return one tactical-context row per phase frame and match team.

    SkillCorner phase intervals use an inclusive start and exclusive end:
    ``frame_start <= frame < frame_end``. No frames are created outside those
    intervals, so phase gaps remain unlabelled.
    """
    required = {
        "match_id", "frame_start", "frame_end", "period", "duration",
        "team_in_possession_id", "team_in_possession_phase_type",
        "team_out_of_possession_phase_type", "team_possession_lead_to_shot",
        "team_possession_lead_to_goal",
    }
    missing = required - set(phases.columns)
    if missing:
        raise ValueError(f"phases is missing required columns: {sorted(missing)}")

    match_id = match_info["id"]
    if not phases["match_id"].eq(match_id).all():
        raise ValueError("Every phase row must belong to match_info['id'].")

    match_team_ids = _match_team_ids(match_info)
    expected_durations = (phases["frame_end"] - phases["frame_start"]) / 10
    if not (phases["duration"] - expected_durations).abs().lt(1e-9).all():
        raise ValueError(
            "Phase durations must equal (frame_end - frame_start) / 10 at 10 Hz."
        )
    context_rows: list[dict[str, Any]] = []

    for phase in phases.itertuples(index=False):
        phase_data = phase._asdict()
        possession_team_id = phase_data["team_in_possession_id"]
        if possession_team_id not in match_team_ids:
            raise ValueError("A phase row references a team outside this match.")

        other_team_id = next(iter(match_team_ids - {possession_team_id}))
        frame_start = int(phase_data["frame_start"])
        frame_end = int(phase_data["frame_end"])
        if frame_end <= frame_start:
            raise ValueError("Each phase interval must have frame_end > frame_start.")

        common = {
            "match_id": match_id,
            "period": phase_data["period"],
            "possession_team_id": possession_team_id,
            "phase_frame_start": frame_start,
            "phase_frame_end": frame_end,
            "phase_duration": phase_data["duration"],
            "team_possession_lead_to_shot": phase_data["team_possession_lead_to_shot"],
            "team_possession_lead_to_goal": phase_data["team_possession_lead_to_goal"],
        }
        for frame in range(frame_start, frame_end):
            context_rows.extend(
                (
                    {
                        **common,
                        "frame": frame,
                        "team_id": possession_team_id,
                        "possession_status": "in_possession",
                        "tactical_phase": phase_data["team_in_possession_phase_type"],
                    },
                    {
                        **common,
                        "frame": frame,
                        "team_id": other_team_id,
                        "possession_status": "out_of_possession",
                        "tactical_phase": phase_data["team_out_of_possession_phase_type"],
                    },
                )
            )

    context = pd.DataFrame.from_records(context_rows, columns=CONTEXT_COLUMNS)
    _validate_context_rows(context, match_info)
    return context.sort_values(JOIN_KEYS).reset_index(drop=True)


def _validate_context_rows(
    phase_context: pd.DataFrame, match_info: Mapping[str, Any]
) -> None:
    """Raise a clear error for invalid interval expansion output."""
    if phase_context.duplicated(JOIN_KEYS).any():
        raise ValueError("Duplicate team-frame phase-context rows were created.")
    if not phase_context["match_id"].eq(match_info["id"]).all():
        raise ValueError("Phase context has a match_id inconsistent with match metadata.")
    boundary_valid = (
        phase_context["frame"].ge(phase_context["phase_frame_start"])
        & phase_context["frame"].lt(phase_context["phase_frame_end"])
    )
    if not boundary_valid.all():
        raise ValueError("A phase-context frame falls outside its source interval.")
    if not set(phase_context["team_id"]).issubset(_match_team_ids(match_info)):
        raise ValueError("Phase context has a team outside the match metadata.")


def join_phase_context_to_team_shape(
    team_shape: pd.DataFrame,
    phase_context: pd.DataFrame,
    match_info: Mapping[str, Any],
) -> pd.DataFrame:
    """Left-join phase context to Team Shape, preserving unlabelled phase gaps."""
    if not isinstance(team_shape.index, pd.MultiIndex):
        raise ValueError("team_shape must use a MultiIndex containing frame, period, and team_id.")
    missing_index_names = set(JOIN_KEYS) - set(team_shape.index.names)
    if missing_index_names:
        raise ValueError(f"team_shape index is missing: {sorted(missing_index_names)}")
    _validate_context_rows(phase_context, match_info)

    shape_rows = team_shape.reset_index()
    if shape_rows.duplicated(JOIN_KEYS).any():
        raise ValueError("team_shape has duplicate frame-period-team rows.")

    # Validate period agreement wherever a phase frame is represented in Team Shape.
    phase_periods = phase_context[["frame", "period"]].drop_duplicates()
    tracked_periods = shape_rows[["frame", "period"]].drop_duplicates()
    period_check = phase_periods.merge(
        tracked_periods, on="frame", how="inner", suffixes=("_phase", "_shape")
    )
    if not period_check["period_phase"].eq(period_check["period_shape"]).all():
        raise ValueError("Phase and Team Shape period values disagree for the same frame.")

    context_values = [column for column in CONTEXT_COLUMNS if column not in JOIN_KEYS]
    joined = shape_rows.merge(
        phase_context[JOIN_KEYS + context_values],
        on=JOIN_KEYS,
        how="left",
        validate="one_to_one",
    )
    return joined.set_index(team_shape.index.names).sort_index()


def audit_phase_context_join(
    team_shape: pd.DataFrame,
    phase_context: pd.DataFrame,
    match_info: Mapping[str, Any],
) -> dict[str, int | bool]:
    """Return coverage and validation facts without changing join behaviour."""
    _validate_context_rows(phase_context, match_info)
    shape_rows = team_shape.reset_index()
    context_keys = phase_context[JOIN_KEYS].drop_duplicates()
    shape_keys = shape_rows[JOIN_KEYS].drop_duplicates()

    phase_unmatched = context_keys.merge(shape_keys, on=JOIN_KEYS, how="left", indicator=True)
    shape_unmatched = shape_keys.merge(context_keys, on=JOIN_KEYS, how="left", indicator=True)
    boundary_valid = (
        phase_context["frame"].ge(phase_context["phase_frame_start"])
        & phase_context["frame"].lt(phase_context["phase_frame_end"])
    ).all()

    return {
        "context_team_frame_rows": len(phase_context),
        "duplicate_context_team_frames": int(phase_context.duplicated(JOIN_KEYS).sum()),
        "interval_boundaries_valid": bool(boundary_valid),
        "unmatched_phase_team_frames": int((phase_unmatched["_merge"] == "left_only").sum()),
        "unmatched_shape_team_frames": int((shape_unmatched["_merge"] == "left_only").sum()),
    }
