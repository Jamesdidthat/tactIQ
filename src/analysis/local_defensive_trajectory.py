"""Attach ball-local defensive context to matched pre-shot windows."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.data import flatten_player_tracking
from src.metrics import (
    calculate_defensive_line_structure,
    calculate_local_defensive_context,
    calculate_attacker_defensive_allocation,
    calculate_ball_goal_passing_lanes,
    extract_ball_tracking,
)

from .shot_sequence_temporal import audit_shot_sequence_timing, _time_to_seconds
from .pre_shot_trajectory import build_pre_shot_trajectory_analysis


def build_local_defensive_context_trajectory(
    matches_root: str | Path, *, local_radius_metres: float = 10.0,
    existing_trajectory: dict[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build matched shot/control trajectories for the local-context metrics.

    A metric-pair is retained only when both windows have its full 51 frames
    (−5.0 seconds through the outcome frame), so missing coordinates never
    become an apparent zero or an imputed defensive action.
    """
    root = Path(matches_root)
    audit = audit_shot_sequence_timing(root)
    # Reuse the established full player-tracking + phase-context gate. This
    # prevents the local module from enlarging the comparison population merely
    # because geometry happened to be available outside labelled phase context.
    existing = existing_trajectory or build_pre_shot_trajectory_analysis(root)
    existing_pairs = (
        existing["window_features"]
        .loc[lambda rows: rows.metric.eq("total_outfield_length")]
        .groupby(["segment", "match_id", "event_id"])["outcome"].nunique()
        .eq(2).rename("is_existing_pair").reset_index().query("is_existing_pair")
        .drop(columns="is_existing_pair")
    )
    full = audit["pre_shot_windows"].loc[
        lambda rows: rows.window_seconds.eq(5) & rows.player_tracking_frames.eq(50),
        ["match_id", "event_id"],
    ]
    pairs = (
        audit["shots"].merge(full, on=["match_id", "event_id"])
        .merge(audit["control_windows"], left_on=["match_id", "event_id"], right_on=["match_id", "shot_event_id"])
    )
    value_rows: list[dict] = []
    attacker_contexts: list[pd.DataFrame] = []
    for match_id, match_pairs in pairs.groupby("match_id"):
        match_dir = root / str(match_id)
        with (match_dir / f"{match_id}_match.json").open(encoding="utf-8") as file:
            match_info = json.load(file)
        raw_records = [json.loads(line) for line in (match_dir / f"{match_id}_tracking_extrapolated.jsonl").open(encoding="utf-8")]
        raw = pd.DataFrame(raw_records)
        # The reusable metric operates on every supplied team-frame. For this
        # attachment pass, supply exactly the frames used by a shot/control
        # window rather than materialising the whole match unnecessarily.
        required_frames = set()
        for pair in match_pairs.itertuples(index=False):
            required_frames.update(range(int(pair.shot_frame) - 50, int(pair.shot_frame) + 1))
            required_frames.update(range(int(pair.control_frame) - 50, int(pair.control_frame) + 1))
        raw = raw.loc[raw.frame.isin(required_frames)].copy()
        raw["elapsed_seconds"] = raw.timestamp.map(
            lambda timestamp: _time_to_seconds(timestamp) if pd.notna(timestamp) else None
        )
        players = flatten_player_tracking(raw, match_info)
        lines = calculate_defensive_line_structure(players, match_info)
        context = calculate_local_defensive_context(
            players, extract_ball_tracking(raw), lines, match_info,
            local_radius_metres=local_radius_metres,
        )
        allocation = calculate_attacker_defensive_allocation(
            players, extract_ball_tracking(raw), match_info,
        )
        geometry = calculate_ball_goal_passing_lanes(
            players, extract_ball_tracking(raw), match_info,
        )
        allocation_keys = ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
        context = context.merge(allocation["frame_metrics"], on=allocation_keys, how="left")
        context = context.merge(geometry["frame_metrics"], on=allocation_keys, how="left")
        attacker_contexts.append(allocation["attacker_context"].assign(match_id=match_id))
        metric_columns = [
            column for column in context.columns
            if column not in {"frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "ball_x", "ball_y", "ball_normalized_x"}
        ]
        for pair in match_pairs.itertuples(index=False):
            for outcome, end_frame in (("shot", pair.shot_frame), ("control", pair.control_frame)):
                window = context.loc[
                    context.team_id.eq(pair.defending_team_id) & context.frame.between(end_frame - 50, end_frame)
                ].copy()
                window["relative_frame"] = window.frame - end_frame
                for row in window[["relative_frame"] + metric_columns].itertuples(index=False):
                    for metric, value in zip(metric_columns, row[1:]):
                        value_rows.append({
                            "match_id": match_id, "event_id": pair.event_id,
                            "defending_phase": pair.defending_phase, "outcome": outcome,
                            "relative_frame": row[0], "metric": metric, "value": value,
                        })
    values = pd.DataFrame(value_rows)
    expected = set(range(-50, 1))
    coverage = (
        values.groupby(["match_id", "event_id", "outcome", "metric"])
        .agg(frame_count=("relative_frame", "nunique"), available_frame_count=("value", "count"))
        .reset_index()
    )
    valid = coverage.loc[
        coverage.frame_count.eq(len(expected)) & coverage.available_frame_count.eq(len(expected)),
        ["match_id", "event_id", "outcome", "metric"],
    ]
    paired = (
        valid.groupby(["match_id", "event_id", "metric"])["outcome"].nunique()
        .eq(2).rename("is_pair").reset_index().query("is_pair").drop(columns="is_pair")
    )
    retained = values.merge(paired, on=["match_id", "event_id", "metric"])
    segments = pd.concat([
        retained.assign(segment="all"),
        retained.loc[retained.defending_phase.ne("defending_set_play")].assign(segment="open_play"),
        retained.loc[retained.defending_phase.eq("defending_set_play")].assign(segment="defending_set_play"),
    ], ignore_index=True)
    segments = segments.merge(existing_pairs, on=["segment", "match_id", "event_id"], how="inner")
    points = segments.loc[segments.relative_frame.isin([-50, -20, 0])]
    trajectories = (
        points.groupby(["segment", "metric", "outcome", "relative_frame"])
        .agg(pair_count=("value", "size"), median=("value", "median"), q25=("value", lambda x: x.quantile(.25)), q75=("value", lambda x: x.quantile(.75)))
        .reset_index()
    )
    wide = points.pivot(index=["segment", "match_id", "event_id", "metric", "relative_frame"], columns="outcome", values="value").dropna().reset_index()
    wide["paired_difference"] = wide.shot - wide.control
    differences = (
        wide.groupby(["segment", "metric", "relative_frame"])
        .agg(pair_count=("paired_difference", "size"), median_shot_minus_control=("paired_difference", "median"), q25=("paired_difference", lambda x: x.quantile(.25)), q75=("paired_difference", lambda x: x.quantile(.75)))
        .reset_index()
    )
    quality = (
        coverage.groupby(["metric", "outcome"])
        .agg(windows=("event_id", "size"), full_metric_windows=("available_frame_count", lambda x: int(x.eq(51).sum())), median_available_frames=("available_frame_count", "median"))
        .reset_index()
    )
    raw_pair_coverage = paired.groupby("metric").size().rename("raw_geometry_matched_pairs").reset_index()
    qualified_pair_coverage = (
        segments.groupby(["segment", "metric", "match_id", "event_id"])["outcome"].nunique()
        .eq(2).rename("is_pair").reset_index().query("is_pair")
        .groupby(["segment", "metric"]).size().rename("phase_qualified_matched_pairs").reset_index()
    )
    return {
        "coverage": quality.merge(raw_pair_coverage, on="metric", how="outer"),
        "phase_qualified_pair_coverage": qualified_pair_coverage,
        "window_values": segments,
        "point_trajectories": trajectories,
        "point_paired_differences": differences,
        "attacker_context": pd.concat(attacker_contexts, ignore_index=True) if attacker_contexts else pd.DataFrame(),
    }
