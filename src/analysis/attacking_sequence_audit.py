"""Descriptive Dynamic Events audit for the ten seconds before validated shots."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .shot_sequence_temporal import audit_shot_sequence_timing
from .pre_shot_trajectory import build_pre_shot_trajectory_analysis


ACTION_COLUMNS = [
    "event_id", "index", "match_id", "frame_start", "frame_end", "time_start", "time_end",
    "period", "team_id", "team_shortname", "event_type", "event_subtype", "start_type",
    "end_type", "carry", "quick_pass", "high_pass", "forward_momentum", "pass_outcome",
    "pass_range", "pass_direction", "pass_ahead", "n_opponents_bypassed",
    "first_line_break", "second_last_line_break", "last_line_break",
    "team_in_possession_phase_type", "lead_to_shot", "lead_to_goal",
]


def audit_attacking_pre_shot_sequences(matches_root: str | Path) -> dict[str, pd.DataFrame]:
    """Return ordered attacking Dynamic Events in the ten seconds before each shot.

    The validated-shot set is inherited from ``audit_shot_sequence_timing``.
    All same-team Dynamic Events are retained in ``events``; the narrower
    ``player_possession_actions`` table is the defensible on-ball sequence.
    It does not call a cross, cutback, through ball, or dribble unless an
    explicit source field exists (the supplied schema does not provide those
    labels).
    """
    root = Path(matches_root)
    timing = audit_shot_sequence_timing(root)
    shots = timing["shots"].copy()
    valid_ids = set(timing["processing_log"].loc[
        timing["processing_log"].status.eq("processed"), "match_id"
    ])
    event_rows: list[pd.DataFrame] = []
    schema_rows: list[dict] = []
    for match_id in sorted(valid_ids):
        path = root / str(match_id) / f"{match_id}_dynamic_events.csv"
        dynamic = pd.read_csv(path, low_memory=False)
        available = [column for column in ACTION_COLUMNS if column in dynamic.columns]
        schema_rows.extend({
            "match_id": match_id, "column": column,
            "non_null_count": int(dynamic[column].notna().sum()),
            "unique_count": int(dynamic[column].nunique(dropna=True)),
        } for column in available)
        match_shots = shots.loc[shots.match_id.eq(match_id)]
        for shot in match_shots.itertuples(index=False):
            # frame_end is the verified instant of the shot. Events ending at
            # that frame are the shot itself and are excluded from its lead-up.
            sequence = dynamic.loc[
                dynamic.team_id.eq(shot.team_id)
                & dynamic.period.eq(shot.period)
                & dynamic.frame_end.lt(shot.shot_frame)
                & dynamic.frame_end.ge(shot.shot_frame - 100),
                available,
            ].copy()
            sequence["shot_event_id"] = shot.event_id
            sequence["shot_frame"] = shot.shot_frame
            sequence["frames_before_shot"] = shot.shot_frame - sequence.frame_end
            event_rows.append(sequence)
    events = pd.concat(event_rows, ignore_index=True) if event_rows else pd.DataFrame()
    events = events.sort_values(["match_id", "shot_event_id", "frame_end", "frame_start", "index"])
    player_actions = events.loc[events.event_type.eq("player_possession")].copy()
    previous = (
        player_actions.sort_values(["match_id", "shot_event_id", "frame_end", "frame_start", "index"])
        .groupby(["match_id", "shot_event_id"], as_index=False).tail(1).copy()
    )
    previous["identifiable_preceding_action"] = previous.end_type.notna() & previous.frames_before_shot.between(0, 100)
    preceding = shots[["match_id", "event_id", "shot_frame", "team_id", "team_shortname", "period"]].rename(columns={"event_id": "shot_event_id"}).merge(
        previous.drop(columns=["team_id", "team_shortname", "period"], errors="ignore"),
        on=["match_id", "shot_event_id", "shot_frame"], how="left", suffixes=("", "_preceding"),
    )
    preceding["identifiable_preceding_action"] = preceding.identifiable_preceding_action.eq(True)
    # Relevant categorical values across the validated-match source files.
    categories = []
    for column in ("event_type", "event_subtype", "start_type", "end_type", "pass_outcome", "pass_range", "pass_direction", "team_in_possession_phase_type"):
        if column in events:
            for value, count in events[column].value_counts(dropna=False).items():
                categories.append({"column": column, "value": value, "count": int(count)})
    return {
        "validated_shots": shots,
        "schema": pd.DataFrame(schema_rows),
        "categorical_values_in_sequences": pd.DataFrame(categories),
        "events": events,
        "player_possession_actions": player_actions,
        "immediately_preceding_actions": preceding,
    }


def build_shot_sequence_descriptors(matches_root: str | Path) -> dict[str, pd.DataFrame]:
    """Create one multi-label, evidence-limited descriptor row per validated shot.

    A descriptor is not a mutually exclusive shot-creation classification:
    carry, quick-pass, high-pass, origin, and progression fields can overlap.
    The possession phase is the explicit Dynamic Events phase on the shot.
    """
    root = Path(matches_root)
    audit = audit_attacking_pre_shot_sequences(root)
    shots = audit["validated_shots"].copy().rename(columns={"event_id": "shot_event_id"})
    actions = audit["player_possession_actions"].copy()
    key = ["match_id", "shot_event_id"]
    action_summary = (
        actions.groupby(key, dropna=False)
        .agg(
            preceding_player_possession_action_count=("event_id", "size"),
            sequence_first_action_frame=("frame_start", "min"),
            any_carry=("carry", lambda values: bool(values.eq(True).any())),
            any_quick_pass=("quick_pass", lambda values: bool(values.eq(True).any())),
            any_high_pass=("high_pass", lambda values: bool(values.eq(True).any())),
            max_opponents_bypassed=("n_opponents_bypassed", "max"),
            total_opponents_bypassed=("n_opponents_bypassed", lambda values: values.sum(min_count=1)),
        )
        .reset_index()
    )
    origin_types = [
        "recovery", "pass_interception", "corner_reception", "free_kick_reception",
        "throw_in_reception", "pass_reception", "keep_possession",
    ]
    origin = actions.pivot_table(
        index=key, columns="start_type", values="event_id", aggfunc="size", fill_value=0
    ).reindex(columns=origin_types, fill_value=0).gt(0).reset_index()
    origin = origin.rename(columns={value: f"origin_{value}" for value in origin_types})
    origin["explicit_origin_start_types"] = origin.apply(
        lambda row: "|".join(value for value in origin_types if row[f"origin_{value}"]) or pd.NA,
        axis=1,
    )
    prior_columns = [
        "match_id", "shot_event_id", "end_type", "pass_range", "pass_direction",
        "frames_before_shot", "identifiable_preceding_action",
    ]
    prior = audit["immediately_preceding_actions"][prior_columns].rename(columns={
        "end_type": "immediately_preceding_action_end_type",
        "pass_range": "immediately_preceding_pass_range",
        "pass_direction": "immediately_preceding_pass_direction",
        "frames_before_shot": "immediately_preceding_action_frames_before_shot",
    })
    columns = [
        "match_id", "shot_event_id", "team_id", "team_shortname", "period", "shot_frame",
        "time_end", "team_in_possession_phase_type", "lead_to_goal",
    ]
    descriptors = shots[columns].merge(action_summary, on=key, how="left").merge(origin, on=key, how="left").merge(prior, on=key, how="left")
    descriptors["sequence_duration_seconds"] = (
        (descriptors.shot_frame - descriptors.sequence_first_action_frame).clip(upper=100) / 10
    )
    descriptors["preceding_player_possession_action_count"] = descriptors.preceding_player_possession_action_count.fillna(0).astype(int)
    for column in ["any_carry", "any_quick_pass", "any_high_pass", *[f"origin_{value}" for value in origin_types]]:
        descriptors[column] = descriptors[column].eq(True)
    descriptors["uncertain_no_identifiable_preceding_action"] = ~descriptors.identifiable_preceding_action.eq(True)
    descriptors = descriptors.rename(columns={"team_in_possession_phase_type": "shot_possession_phase"})

    counts = []
    for column in ["shot_possession_phase", "immediately_preceding_action_end_type", "explicit_origin_start_types"]:
        for value, count in descriptors[column].value_counts(dropna=False).items():
            counts.append({"descriptor": column, "value": value, "shot_count": int(count)})
    for column in ["any_carry", "any_quick_pass", "any_high_pass", "uncertain_no_identifiable_preceding_action", *[f"origin_{value}" for value in origin_types]]:
        counts.append({"descriptor": column, "value": True, "shot_count": int(descriptors[column].sum())})
    overlaps = (
        descriptors.groupby(["any_carry", "any_quick_pass", "any_high_pass"], dropna=False)
        .size().rename("shot_count").reset_index()
    )

    # Match against the existing phase-qualified 5-second trajectory sample.
    trajectory = build_pre_shot_trajectory_analysis(root)
    valid_pairs = (
        trajectory["window_features"]
        .loc[lambda rows: rows.segment.eq("open_play") & rows.metric.eq("total_outfield_length")]
        .groupby(["match_id", "event_id"])["outcome"].nunique().eq(2)
        .rename("has_matched_window").reset_index().rename(columns={"event_id": "shot_event_id"})
    )
    subset = descriptors.loc[descriptors.shot_possession_phase.isin(["transition", "quick_break"])].merge(
        valid_pairs, on=key, how="left"
    )
    subset["has_matched_window"] = subset.has_matched_window.eq(True)
    window_coverage = pd.DataFrame([{
        "subset": "transition_or_quick_break_open_play_shots",
        "shot_count": len(subset),
        "transition_shot_count": int(subset.shot_possession_phase.eq("transition").sum()),
        "quick_break_shot_count": int(subset.shot_possession_phase.eq("quick_break").sum()),
        "shots_with_existing_matched_window": int(subset.has_matched_window.sum()),
        "matched_shot_windows": int(subset.has_matched_window.sum()),
        "matched_control_windows": int(subset.has_matched_window.sum()),
    }])
    return {
        "descriptors": descriptors.sort_values(key).reset_index(drop=True),
        "descriptor_counts": pd.DataFrame(counts),
        "flag_overlaps": overlaps,
        "transition_quick_break_window_coverage": window_coverage,
        "open_play_matched_pairs": valid_pairs.loc[valid_pairs.has_matched_window, key].copy(),
        "trajectory_window_features": trajectory["window_features"],
    }


def summarize_descriptor_matched_pair_coverage(
    matches_root: str | Path, *, combination_min_pairs: int = 10
) -> pd.DataFrame:
    """Count descriptor subsets within the validated open-play matched-pair set.

    One descriptor row denotes the shot member of a pair. Every retained row
    therefore contributes one shot window, one matched control window, and one
    complete pair. Labels intentionally overlap.
    """
    if combination_min_pairs < 1:
        raise ValueError("combination_min_pairs must be at least 1.")
    result = build_shot_sequence_descriptors(matches_root)
    descriptors = result["descriptors"].merge(
        result["open_play_matched_pairs"], on=["match_id", "shot_event_id"], how="inner"
    )
    definitions = {
        "finish_phase": descriptors.shot_possession_phase.eq("finish"),
        "transition_phase": descriptors.shot_possession_phase.eq("transition"),
        "quick_break_phase": descriptors.shot_possession_phase.eq("quick_break"),
        "transition_or_quick_break": descriptors.shot_possession_phase.isin(["transition", "quick_break"]),
        "any_carry": descriptors.any_carry,
        "any_quick_pass": descriptors.any_quick_pass,
        "any_high_pass": descriptors.any_high_pass,
        "explicit_recovery_origin": descriptors.origin_recovery,
        "explicit_interception_origin": descriptors.origin_pass_interception,
        "recovery_or_interception_origin": descriptors.origin_recovery | descriptors.origin_pass_interception,
    }
    # Report phase+action intersections only when they meet the requested
    # minimum. They are still overlapping descriptors, not a partition.
    for phase in ("finish", "transition", "quick_break"):
        for flag in ("any_carry", "any_quick_pass", "any_high_pass"):
            label = f"{phase}_and_{flag.removeprefix('any_')}"
            mask = descriptors.shot_possession_phase.eq(phase) & descriptors[flag]
            if int(mask.sum()) >= combination_min_pairs:
                definitions[label] = mask
    rows = []
    for subset, mask in definitions.items():
        count = int(mask.sum())
        rows.append({
            "subset": subset,
            "shot_pair_count": count,
            "control_pair_count": count,
            "complete_matched_pair_count": count,
            "exploratory_sample_band": "N>=30" if count >= 30 else "N=15-29" if count >= 15 else "N<15",
        })
    return pd.DataFrame(rows).sort_values(
        ["complete_matched_pair_count", "subset"], ascending=[False, True]
    ).reset_index(drop=True)
