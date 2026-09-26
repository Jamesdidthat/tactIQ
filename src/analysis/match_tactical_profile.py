"""Deterministic, capability-aware match and goal tactical descriptions.

This module compares what happened in one match with each team's match-weighted
season profile.  It describes evidence and supported contributors; it never
assigns a single cause, blame, intent, or a tactical recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.data import CanonicalMatchBundle, validate_canonical_bundle
from src.metrics import calculate_defensive_line_structure, calculate_team_shape

from .event_team_profile import (
    EventTeamSeasonProfile, PENALTY_AREA_X, PENALTY_AREA_Y, FINAL_THIRD_X,
    SET_PLAY_PATTERNS, SET_PLAY_SHOT_TYPES, _progressive,
    calculate_event_team_match_metrics,
)
from .team_profile import TeamProfileResult


MATCH_METRICS = {
    "possession_share_estimate": ("control", "share of the event possession timeline"),
    "progressive_passes_per90": ("progression", "forward-moving passes"),
    "progressive_carries_per90": ("progression", "forward ball carries"),
    "passes_into_final_third_per90": ("final_third", "entries into the final third by pass"),
    "passes_into_penalty_area_per90": ("penalty_area", "passes into the box"),
    "shots_per90": ("chance_creation", "shots"),
    "xg_per90": ("chance_creation", "quality of chances created"),
    "xg_per_shot": ("shot_selection", "average chance quality"),
    "pressures_per90": ("defensive_activity", "defensive pressures"),
    "interceptions_per90": ("defensive_activity", "interceptions"),
    "high_regains_per90": ("transitions", "high ball recoveries"),
    "counter_attack_shots_per90": ("transitions", "explicitly tagged counter-attack shots"),
    "turnovers_leading_to_shot_per90": ("transitions", "lost possessions followed quickly by an opposition shot"),
}


def _football_deviation_summary(metric: str, observed: float, median: float) -> str:
    higher = observed > median
    wording = {
        "possession_share_estimate": ("They controlled more of the ball than usual.", "They controlled less of the ball than usual."),
        "progressive_passes_per90": ("They moved forward by pass more often than usual.", "They moved forward by pass less often than usual."),
        "progressive_carries_per90": ("They carried the ball forward more often than usual.", "They carried the ball forward less often than usual."),
        "passes_into_final_third_per90": ("They reached the final third by pass more often than usual.", "They reached the final third by pass less often than usual."),
        "passes_into_penalty_area_per90": ("They found the box by pass more often than usual.", "They found the box by pass less often than usual."),
        "shots_per90": ("They shot more often than usual.", "They shot less often than usual."),
        "xg_per90": ("They created more dangerous chances overall than usual.", "They created less danger from their chances than usual."),
        "xg_per_shot": ("Their shots were more dangerous on average than usual.", "Their shots were less dangerous on average than usual."),
        "pressures_per90": ("They applied pressure more often than usual.", "They applied pressure less often than usual."),
        "interceptions_per90": ("They cut out more opposition passes than usual.", "They cut out fewer opposition passes than usual."),
        "high_regains_per90": ("They won the ball high up the pitch more often than usual.", "They won the ball high up the pitch less often than usual."),
        "counter_attack_shots_per90": ("They produced more shots from counter-attacks than usual.", "They produced fewer shots from counter-attacks than usual."),
        "turnovers_leading_to_shot_per90": ("Their lost possessions were followed by opposition shots more often than usual.", "Their lost possessions were followed by opposition shots less often than usual."),
    }
    if metric in wording:
        return wording[metric][0 if higher else 1]
    return f"This part of their game was {'more' if higher else 'less'} pronounced than usual."


@dataclass(frozen=True)
class MatchStyleDeviation:
    metric: str
    football_concept: str
    observed_value: float
    season_median: float
    q25: float
    q75: float
    signed_difference: float
    robust_standardized_difference: float | None
    contributing_matches: int
    coverage: float
    football_summary: str
    definition: str


@dataclass(frozen=True)
class MatchTimeSegment:
    segment_id: str
    start_minute: int
    end_minute: int
    team_id: str | int
    headline: str
    explanation: str
    evidence: Mapping[str, float | int | str | None]
    change_from_previous: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class TeamMatchTacticalProfile:
    team_id: str | int
    team_name: str
    opponent_team_id: str | int
    opponent_team_name: str
    headline: str
    overview: str
    style_deviations: tuple[MatchStyleDeviation, ...]
    segments: tuple[MatchTimeSegment, ...]
    tracking_shape: Mapping[str, Any] | None
    opponent_relative_observations: tuple[str, ...]
    capabilities_used: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class GoalSequenceAction:
    event_id: str
    order: int
    minute: int
    second: int
    event_type: str
    player_id: str | int | None
    start_coordinates: tuple[float, float] | None
    end_coordinates: tuple[float, float] | None
    outcome: str | None


@dataclass(frozen=True)
class GoalContributor:
    category: str
    observation: str
    evidence: Mapping[str, Any]
    scope: str


@dataclass(frozen=True)
class GoalAnalysis:
    goal_id: str
    event_id: str
    scoring_team_id: str | int
    scoring_team_name: str
    conceding_team_id: str | int
    conceding_team_name: str
    period: int
    minute: int
    second: int
    score_state_before_goal: str | None
    what_happened: str
    what_created_the_opportunity: str
    had_this_been_happening_earlier: str
    recurring_season_pattern: str
    structural_versus_execution: str
    sequence_origin: str
    sequence_duration_seconds: float
    progression_route: str
    passes: int
    carries: int
    shot_location: tuple[float, float] | None
    shot_xg: float | None
    preceding_actions: tuple[GoalSequenceAction, ...]
    contributors: tuple[GoalContributor, ...]
    tracking_context: Mapping[str, Any] | None
    comparable_historical_matches: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class MatchTacticalProfile:
    schema_version: str
    match_id: str | int
    provider: str
    match_identity: Mapping[str, Any]
    team_profiles: tuple[TeamMatchTacticalProfile, ...]
    goals: tuple[GoalAnalysis, ...]
    capabilities: Mapping[str, bool]
    analysis_coverage: Mapping[str, str]
    limitations: tuple[str, ...]


def _number(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def _point(row: pd.Series, start: bool = True) -> tuple[float, float] | None:
    x_name, y_name = ("location_x", "location_y") if start else ("end_location_x", "end_location_y")
    if x_name not in row or y_name not in row or pd.isna(row[x_name]) or pd.isna(row[y_name]):
        return None
    return float(row[x_name]), float(row[y_name])


def _robust_z(value: float, season_values: pd.Series) -> float | None:
    values = pd.to_numeric(season_values, errors="coerce").dropna()
    if len(values) < 3:
        return None
    centre = float(values.median())
    scale = float((values.quantile(.75) - values.quantile(.25)) / 1.349)
    if scale <= 1e-12:
        scale = float((values - centre).abs().median() * 1.4826)
    return None if scale <= 1e-12 else (float(value) - centre) / scale


def _style_deviations(match_row: pd.Series, profile: EventTeamSeasonProfile | None) -> tuple[MatchStyleDeviation, ...]:
    if profile is None:
        return ()
    aggregates = profile.aggregate_metrics.set_index("metric")
    definitions = profile.definitions.set_index("metric")
    output = []
    comparison_matches = profile.match_metrics
    if "match_id" in match_row and "match_id" in comparison_matches:
        comparison_matches = comparison_matches.loc[
            comparison_matches.match_id.astype(str).ne(str(match_row["match_id"]))
        ]
    for metric, (concept, label) in MATCH_METRICS.items():
        if metric not in match_row.index or metric not in aggregates.index or pd.isna(match_row[metric]):
            continue
        season_values = pd.to_numeric(comparison_matches[metric], errors="coerce") if metric in comparison_matches else pd.Series(dtype=float)
        valid_values = season_values.dropna()
        count = int(len(valid_values))
        coverage = float(count / len(comparison_matches)) if len(comparison_matches) else 0.0
        if count < 5 or coverage < .70:
            continue
        observed, median = float(match_row[metric]), float(valid_values.median())
        z = _robust_z(observed, valid_values)
        if z is None or abs(z) < 1.0:
            continue
        summary = _football_deviation_summary(metric, observed, median)
        output.append(MatchStyleDeviation(
            metric, concept, observed, median, float(valid_values.quantile(.25)),
            float(valid_values.quantile(.75)), observed - median, z, count, coverage,
            summary, str(definitions.loc[metric].definition) if metric in definitions.index else "Definition unavailable.",
        ))
    return tuple(sorted(output, key=lambda item: (-abs(item.robust_standardized_difference or 0), item.metric)))


def _tracking_style_deviations(current: Mapping[str, Any] | None, profile: TeamProfileResult | None, provider: str) -> tuple[MatchStyleDeviation, ...]:
    if current is None or profile is None:
        return ()
    definitions = {
        "outfield_width": ("outfield_width_median_metres", "shape", "team width"),
        "outfield_length": ("outfield_length_median_metres", "shape", "back-to-front spacing"),
        "defence_tactical_median_x": ("defensive_line_position_median_metres", "defensive_height", "defensive-line position"),
        "defence_to_midfield_gap": ("defence_to_midfield_gap_median_metres", "compactness", "distance between defence and midfield"),
    }
    output = []
    for metric, (current_key, concept, label) in definitions.items():
        value = current.get(current_key)
        family = "overall_team_shape" if metric in {"outfield_width", "outfield_length"} else "defensive_line_structure"
        baseline = profile.aggregate_patterns.loc[
            profile.aggregate_patterns.provider.eq(provider) & profile.aggregate_patterns.metric_family.eq(family)
            & profile.aggregate_patterns.metric.eq(metric)
        ]
        samples = profile.match_level_values.loc[
            profile.match_level_values.provider.eq(provider) & profile.match_level_values.metric_family.eq(family)
            & profile.match_level_values.metric.eq(metric), "value"
        ]
        if value is None or baseline.empty or int(baseline.iloc[0].contributing_matches) < 3:
            continue
        row = baseline.iloc[0]; z = _robust_z(float(value), samples)
        if z is None or abs(z) < 1.0 or abs(float(value) - float(row.median_across_matches)) < 3.0:
            continue
        direction = "more" if float(value) > float(row.median_across_matches) else "less"
        output.append(MatchStyleDeviation(
            metric, concept, float(value), float(row.median_across_matches), float(row.q25_across_matches),
            float(row.q75_across_matches), float(value) - float(row.median_across_matches), z,
            int(row.contributing_matches), 1.0, f"Their {label} was {direction} pronounced than in their typical tracked match.",
            "Match median from observed continuous-tracking frames compared with match-weighted team-profile values.",
        ))
    return tuple(sorted(output, key=lambda item: (-abs(item.robust_standardized_difference or 0), item.metric)))


def _segment_metrics(events: pd.DataFrame, team_id: Any, start: float, end: float) -> dict[str, float | int | None]:
    window = events.loc[events.elapsed_seconds.ge(start) & events.elapsed_seconds.lt(end)].sort_values("event_index", kind="stable")
    team = window.loc[window.team_id.eq(team_id)]
    passes = team.loc[team.event_type.eq("Pass")]
    completed = passes.loc[passes.pass_outcome.isna()]
    carries = team.loc[team.event_type.eq("Carry")]
    shots = team.loc[team.event_type.eq("Shot")]
    progressive = int(_progressive(completed).sum()) if not completed.empty else 0
    final_third = int((completed.location_x.lt(FINAL_THIRD_X) & completed.end_location_x.ge(FINAL_THIRD_X)).sum())
    box = int((~(completed.location_x.ge(PENALTY_AREA_X) & completed.location_y.between(*PENALTY_AREA_Y)) & completed.end_location_x.ge(PENALTY_AREA_X) & completed.end_location_y.between(*PENALTY_AREA_Y)).sum())
    timeline = window.loc[window.possession_team_id.notna() & window.elapsed_seconds.notna()].copy()
    possession = None
    if len(timeline) >= 2:
        weights = timeline.elapsed_seconds.shift(-1).fillna(end).clip(upper=end).sub(timeline.elapsed_seconds).clip(0, 30)
        possession = float(weights.loc[timeline.possession_team_id.eq(team_id)].sum() / weights.sum()) if weights.sum() else None
    return {
        "possession_share": possession, "progressive_passes": progressive,
        "final_third_entries": final_third, "penalty_area_entries": box,
        "shots": int(len(shots)), "xg": _number(shots.shot_xg.sum()) if shots.shot_xg.notna().any() else (0.0 if shots.empty else None),
        "pressures": int(team.event_type.eq("Pressure").sum()),
        "high_regains": int((team.event_type.isin(["Ball Recovery", "Interception"]) & team.location_x.ge(80)).sum()),
        "counter_attack_shots": int((shots.play_pattern.eq("From Counter")).sum()),
    }


def _segment_language(team_name: str, values: Mapping[str, Any]) -> tuple[str, str]:
    possession, shots, entries = values["possession_share"], int(values["shots"]), int(values["penalty_area_entries"])
    if possession is not None and possession >= .60 and shots <= 1:
        return f"{team_name} had control without many shots.", "They had more of the ball in the recorded events, but rarely turned that control into an attempt."
    if shots >= 3 or (values["xg"] is not None and values["xg"] >= .6):
        return f"{team_name} created a threatening spell.", "Their shooting activity or the danger of their chances made this period stand out."
    if entries >= 3:
        return f"{team_name} repeatedly reached the box.", "They turned their attacks into several passes ending inside the penalty area."
    if possession is not None and possession <= .40 and values["counter_attack_shots"]:
        return f"{team_name} threatened while spending less time on the ball.", "At least one attempt was explicitly tagged as coming from a counter attack."
    return f"No clear pattern dominated {team_name}'s spell.", "Neither control of the ball nor attacking threat clearly stood out in this period."


def _segments(events: pd.DataFrame, team_id: Any, team_name: str, window_minutes: int) -> tuple[MatchTimeSegment, ...]:
    maximum = int(np.ceil(float(events.elapsed_seconds.max()) / 60.0)) if not events.empty else 0
    segments, previous = [], None
    for start_minute in range(0, maximum, window_minutes):
        end_minute = min(start_minute + window_minutes, maximum)
        values = _segment_metrics(events, team_id, start_minute * 60.0, end_minute * 60.0)
        changes = []
        if previous is not None:
            if values["possession_share"] is not None and previous["possession_share"] is not None and abs(values["possession_share"] - previous["possession_share"]) >= .12:
                changes.append("their share of the ball changed noticeably")
            if abs(int(values["shots"]) - int(previous["shots"])) >= 2:
                changes.append("how often they shot changed noticeably")
            if abs(int(values["penalty_area_entries"]) - int(previous["penalty_area_entries"])) >= 2:
                changes.append("how often they reached the box changed noticeably")
        headline, explanation = _segment_language(team_name, values)
        segments.append(MatchTimeSegment(
            f"{team_id}:{start_minute}-{end_minute}", start_minute, end_minute, team_id,
            headline, explanation, values, tuple(changes),
            ("A fixed evidence window is not automatically a tactical phase.", "Event locations do not show complete off-ball structure."),
        ))
        previous = values
    return tuple(segments)


def _tracking_contexts(bundle: CanonicalMatchBundle, window_minutes: int) -> tuple[dict[Any, dict[str, Any]], dict[Any, tuple[MatchTimeSegment, ...]]]:
    if not bundle.capabilities.has_continuous_tracking or not bundle.capabilities.has_verified_roles:
        return {}, {}
    # A match overview does not need every 10/25 Hz frame. Use one observed
    # frame per elapsed second, retaining real positions and provider-neutral
    # timing while avoiding an expensive duplicate calculation over the full feed.
    frame_keys = bundle.player_positions[["frame", "period", "elapsed_seconds"]].drop_duplicates(["frame", "period"]).copy()
    frame_keys["elapsed_second_bin"] = np.floor(pd.to_numeric(frame_keys.elapsed_seconds, errors="coerce"))
    sampled_keys = frame_keys.sort_values(["period", "elapsed_seconds", "frame"], kind="stable").drop_duplicates(["period", "elapsed_second_bin"])[["frame", "period"]]
    sampled_positions = bundle.player_positions.merge(sampled_keys, on=["frame", "period"], how="inner", validate="many_to_one")
    shape = calculate_team_shape(sampled_positions).reset_index()
    lines = None
    if bundle.capabilities.has_attacking_direction:
        lines = calculate_defensive_line_structure(sampled_positions, bundle.match_info).reset_index()
    summaries, windows = {}, {}
    for team_id, team in shape.groupby("team_id", sort=False):
        result: dict[str, Any] = {
            "source": "continuous_tracking", "observed_frames": int(team.frame.nunique()),
            "sampling_method": "one observed tracking frame per elapsed second",
            "source_tracking_frames": int(bundle.player_positions[["frame", "period"]].drop_duplicates().shape[0]),
            "outfield_width_median_metres": _number(team.outfield_width.median()),
            "outfield_length_median_metres": _number(team.outfield_length.median()),
        }
        team_lines = lines.loc[lines.team_id.eq(team_id)] if lines is not None else pd.DataFrame()
        if not team_lines.empty:
            result.update({
                "defensive_line_position_median_metres": _number(team_lines.defence_tactical_median_x.median()),
                "midfield_line_position_median_metres": _number(team_lines.midfield_tactical_median_x.median()),
                "defence_to_midfield_gap_median_metres": _number(team_lines.defence_to_midfield_gap.median()),
                "total_outfield_length_median_metres": _number(team_lines.total_outfield_length.median()),
                "direction_normalized": True,
            })
        summaries[team_id] = result
        joined = team[["frame", "timestamp", "period", "elapsed_seconds", "player_count", "outfield_width", "outfield_length"]].copy()
        if not team_lines.empty:
            joined = joined.merge(team_lines[["frame", "period", "defence_tactical_median_x", "defence_to_midfield_gap"]], on=["frame", "period"], how="left", validate="one_to_one")
        joined["window"] = np.floor(joined.elapsed_seconds / (window_minutes * 60)).astype(int)
        segment_rows, previous = [], None
        team_name_row = bundle.teams.loc[bundle.teams.team_id.eq(team_id)].iloc[0]
        team_name = str(team_name_row.get("team_name", team_name_row.team_code))
        for number, group in joined.groupby("window", sort=True):
            representative_pool = group.loc[group.player_count.ge(10)].copy() if "player_count" in group else group.copy()
            if representative_pool.empty:
                representative_pool = group.copy()
            representative_metrics = [
                column for column in (
                    "outfield_width", "outfield_length", "defence_tactical_median_x",
                    "defence_to_midfield_gap",
                ) if column in representative_pool and representative_pool[column].notna().any()
            ]
            representative_score = pd.Series(0.0, index=representative_pool.index)
            for metric in representative_metrics:
                values = pd.to_numeric(representative_pool[metric], errors="coerce")
                centre = float(values.median())
                scale = float(values.quantile(.75) - values.quantile(.25))
                if scale <= 1e-9:
                    scale = 1.0
                representative_score = representative_score.add((values - centre).abs().fillna(scale * 10) / scale)
            representative = representative_pool.loc[representative_score.idxmin()]
            evidence = {
                "outfield_width_metres": _number(group.outfield_width.median()),
                "outfield_length_metres": _number(group.outfield_length.median()),
                "defensive_line_position_metres": _number(group.defence_tactical_median_x.median()) if "defence_tactical_median_x" in group else None,
                "defence_to_midfield_gap_metres": _number(group.defence_to_midfield_gap.median()) if "defence_to_midfield_gap" in group else None,
                "observed_frames": int(group.frame.nunique()),
                "representative_frame": int(representative.frame),
                "representative_period": int(representative.period),
                "representative_timestamp": str(representative.timestamp),
                "representative_elapsed_seconds": float(representative.elapsed_seconds),
            }
            changes = []
            if previous is not None:
                if evidence["outfield_width_metres"] is not None and previous["outfield_width_metres"] is not None and abs(evidence["outfield_width_metres"] - previous["outfield_width_metres"]) >= 5:
                    changes.append("the team became materially wider" if evidence["outfield_width_metres"] > previous["outfield_width_metres"] else "the team became materially narrower")
                if evidence["outfield_length_metres"] is not None and previous["outfield_length_metres"] is not None and abs(evidence["outfield_length_metres"] - previous["outfield_length_metres"]) >= 5:
                    changes.append("the team became materially more stretched" if evidence["outfield_length_metres"] > previous["outfield_length_metres"] else "the team became materially more compact")
                if evidence["defensive_line_position_metres"] is not None and previous["defensive_line_position_metres"] is not None and abs(evidence["defensive_line_position_metres"] - previous["defensive_line_position_metres"]) >= 5:
                    changes.append("the defensive line moved materially higher" if evidence["defensive_line_position_metres"] > previous["defensive_line_position_metres"] else "the defensive line moved materially deeper")
            start_minute, end_minute = int(number * window_minutes), int((number + 1) * window_minutes)
            headline = f"{team_name}'s tracked shape changed from the previous spell." if changes else f"{team_name}'s tracked shape was relatively stable in this spell."
            explanation = "; ".join(changes).capitalize() + "." if changes else "No width, length or defensive-line movement passed the five-metre change rule."
            segment_rows.append(MatchTimeSegment(
                f"{team_id}:tracking:{start_minute}-{end_minute}", start_minute, end_minute, team_id,
                headline, explanation, evidence, tuple(changes),
                ("One real observed frame per elapsed second is summarized.", "A fixed window is not automatically a tactical phase."),
            ))
            previous = evidence
        windows[team_id] = tuple(segment_rows)
    return summaries, windows


def _score_before(events: pd.DataFrame, event: pd.Series, team_id: Any, opponent_id: Any) -> str | None:
    prior = events.loc[
        events.event_index.lt(event.event_index)
        & ((events.event_type.eq("Shot") & events.shot_outcome.eq("Goal")) | events.event_type.isin(["Own Goal Against", "Own Goal For"]))
    ]
    team_goals = opponent_goals = 0
    for goal in prior.itertuples(index=False):
        scoring_team = goal.team_id
        if goal.event_type == "Own Goal Against":
            scoring_team = opponent_id if goal.team_id == team_id else team_id
        if scoring_team == team_id:
            team_goals += 1
        elif scoring_team == opponent_id:
            opponent_goals += 1
    return "leading" if team_goals > opponent_goals else "trailing" if team_goals < opponent_goals else "drawing"


def _goal_sequence(events: pd.DataFrame, goal: pd.Series) -> pd.DataFrame:
    if pd.notna(goal.get("possession_id")):
        sequence = events.loc[
            events.period.eq(goal.period) & events.possession_id.eq(goal.possession_id)
            & events.event_index.le(goal.event_index)
        ]
    else:
        sequence = events.loc[
            events.period.eq(goal.period) & events.elapsed_seconds.between(float(goal.elapsed_seconds) - 10, float(goal.elapsed_seconds))
            & events.team_id.eq(goal.team_id)
        ]
    return sequence.sort_values("event_index", kind="stable").tail(20)


def _action(row: pd.Series, order: int) -> GoalSequenceAction:
    return GoalSequenceAction(
        str(row.event_id), order, int(row.get("minute", 0)), int(row.get("second", 0)),
        str(row.event_type), None if pd.isna(row.get("player_id")) else row.get("player_id"),
        _point(row), _point(row, False), None if pd.isna(row.get("outcome")) else str(row.get("outcome")),
    )


def _historical_matches(profile: EventTeamSeasonProfile | None, metric: str) -> tuple[Mapping[str, Any], ...]:
    if profile is None or metric not in profile.match_metrics:
        return ()
    rows = profile.match_metrics.loc[pd.to_numeric(profile.match_metrics[metric], errors="coerce").fillna(0).gt(0)].copy()
    if rows.empty:
        return ()
    rows = rows.sort_values([metric, "match_id"], ascending=[False, True], kind="stable").head(3)
    return tuple({"match_id": row.match_id, "opponent": row.get("opponent_team_name"), "observed_count": float(row[metric]), "scope": "match-level comparable mechanism"} for _, row in rows.iterrows())


def _goal_tracking(bundle: CanonicalMatchBundle, goal: pd.Series, conceding_team_id: Any) -> dict[str, Any] | None:
    if not (bundle.capabilities.has_continuous_tracking and bundle.capabilities.has_verified_roles):
        return None
    frame_value = goal.get("frame_end")
    if frame_value is None or pd.isna(frame_value):
        return None
    frame, period = int(frame_value), int(goal.period)
    positions = bundle.player_positions.loc[bundle.player_positions.period.eq(period) & bundle.player_positions.frame.le(frame)]
    if positions.empty:
        return None
    actual = int(positions.frame.max())
    sample = positions.loc[positions.frame.eq(actual)]
    shape = calculate_team_shape(sample).reset_index()
    selected = shape.loc[shape.team_id.eq(conceding_team_id)]
    if selected.empty:
        return None
    row = selected.iloc[0]
    result = {"frame": actual, "period": period, "seconds_before_goal_frame": None, "outfield_width_metres": _number(row.outfield_width), "outfield_length_metres": _number(row.outfield_length)}
    if bundle.capabilities.has_attacking_direction:
        lines = calculate_defensive_line_structure(sample, bundle.match_info).reset_index()
        line = lines.loc[lines.team_id.eq(conceding_team_id)]
        if not line.empty:
            line = line.iloc[0]
            result.update({"defensive_line_position_metres": _number(line.defence_tactical_median_x), "defence_to_midfield_gap_metres": _number(line.defence_to_midfield_gap), "line_structure_complete": bool(line.line_structure_complete)})
    return result


def _phase_goal_analyses(bundle: CanonicalMatchBundle) -> tuple[GoalAnalysis, ...]:
    """Describe explicit SkillCorner goal-leading phase intervals without inventing xG."""
    phases = bundle.tactical_phases
    if phases is None or "leads_to_goal" not in phases:
        return ()
    goal_phases = phases.loc[phases.leads_to_goal.fillna(False).astype(bool)].sort_values(["period", "frame_start"], kind="stable")
    results = []
    events = bundle.events if bundle.events is not None else pd.DataFrame()
    frame_times = bundle.player_positions[["frame", "period", "elapsed_seconds", "timestamp"]].drop_duplicates(["frame", "period"])
    for sequence_number, (_, phase) in enumerate(goal_phases.iterrows(), 1):
        scoring_team_id = phase.possession_team_id
        scoring = bundle.teams.loc[bundle.teams.team_id.eq(scoring_team_id)]
        conceding = bundle.teams.loc[bundle.teams.team_id.ne(scoring_team_id)]
        if len(scoring) != 1 or len(conceding) != 1:
            continue
        scoring_row, conceding_row = scoring.iloc[0], conceding.iloc[0]
        scoring_name = str(scoring_row.get("team_name", scoring_row.team_code)); conceding_name = str(conceding_row.get("team_name", conceding_row.team_code))
        phase_events = events.loc[
            events.period.eq(phase.period) & events.team_id.eq(scoring_team_id)
            & events.frame_end.ge(phase.frame_start) & events.frame_start.lt(phase.frame_end_exclusive)
        ].sort_values(["frame_end", "event_index"], kind="stable") if not events.empty else pd.DataFrame()
        shots = phase_events.loc[phase_events.is_shot.fillna(False).astype(bool)] if not phase_events.empty else pd.DataFrame()
        focal = shots.iloc[-1] if not shots.empty else phase_events.iloc[-1] if not phase_events.empty else pd.Series({"frame_end": int(phase.frame_end_exclusive) - 1, "period": phase.period, "event_id": f"phase-{phase.frame_start}"})
        focal_frame = int(focal.frame_end)
        timing = frame_times.loc[frame_times.period.eq(phase.period) & frame_times.frame.le(focal_frame)].sort_values("frame").tail(1)
        elapsed = float(timing.elapsed_seconds.iloc[0]) if not timing.empty else 0.0
        start_timing = frame_times.loc[frame_times.period.eq(phase.period) & frame_times.frame.ge(phase.frame_start)].sort_values("frame").head(1)
        start_elapsed = float(start_timing.elapsed_seconds.iloc[0]) if not start_timing.empty else elapsed
        action_rows = phase_events.loc[phase_events.event_type.eq("player_possession")].tail(20)
        actions = []
        for order, (_, action) in enumerate(action_rows.iterrows(), 1):
            action_time = frame_times.loc[frame_times.period.eq(phase.period) & frame_times.frame.le(action.frame_end)].sort_values("frame").tail(1)
            action_elapsed = float(action_time.elapsed_seconds.iloc[0]) if not action_time.empty else elapsed
            actions.append(GoalSequenceAction(
                str(action.event_id), order, int(action_elapsed // 60), int(action_elapsed % 60),
                str(action.event_type), None if pd.isna(action.get("player_id")) else action.get("player_id"),
                _point(action), _point(action, False), None if pd.isna(action.get("end_type")) else str(action.get("end_type")),
            ))
        start_type = next((str(value) for value in action_rows.get("start_type", pd.Series(dtype=object)).dropna() if str(value) != "unknown"), "start type unavailable")
        transition = start_type in {"recovery", "interception"}
        contributors = []
        if transition:
            contributors.append(GoalContributor("transition_after_turnover", f"The goal-leading phase explicitly began with a {start_type}.", {"start_type": start_type, "phase_frame_start": int(phase.frame_start)}, "SkillCorner phase/event label"))
        if not contributors:
            contributors.append(GoalContributor("insufficient_evidence", "The source identifies the goal-leading phase, but no more specific contributor passed the current rule.", {}, "provider-labelled goal sequence"))
        route_values = pd.concat([phase_events.get("location_y", pd.Series(dtype=float)), phase_events.get("end_location_y", pd.Series(dtype=float))]).dropna()
        route = "central" if not route_values.empty and route_values.abs().le(12).mean() >= .60 else "wide or mixed" if not route_values.empty else "unavailable"
        tracking_goal = focal.copy(); tracking_goal["frame_end"] = focal_frame; tracking_goal["period"] = int(phase.period)
        results.append(GoalAnalysis(
            f"{bundle.matches.match_id.iloc[0]}:phase-goal-{sequence_number}", str(focal.get("event_id", f"phase-{phase.frame_start}")),
            scoring_team_id, scoring_name, conceding_row.team_id, conceding_name, int(phase.period), int(elapsed // 60), int(elapsed % 60),
            None, f"{scoring_name}'s provider-labelled goal-leading phase ended with a shot action at the available tracked frame.",
            f"The recorded phase contained {int(action_rows.end_type.eq('pass').sum())} pass-ending possessions and {int(action_rows.get('carry', pd.Series(False, index=action_rows.index)).fillna(False).astype(bool).sum()) if not action_rows.empty else 0} carries before the final action.",
            "The current canonical SkillCorner feed does not identify comparable earlier goal chances with an exact common event definition.",
            "A season recurrence judgement is unavailable until goal-leading tracking phases are stored across more compatible matches.",
            "Tracking describes the structure before the action, but the available feed does not separate structural contribution from execution.",
            start_type, max(elapsed - start_elapsed, 0.0), route, int(action_rows.end_type.eq("pass").sum()),
            int(action_rows.get("carry", pd.Series(False, index=action_rows.index)).fillna(False).astype(bool).sum()) if not action_rows.empty else 0,
            _point(focal), None, tuple(actions), tuple(contributors), _goal_tracking(bundle, tracking_goal, conceding_row.team_id), (),
            ("The phase is explicitly labelled as leading to a goal, but the feed does not provide shot xG or a standalone goal event.", "The final tracked shot action is used as the goal reference; this is not a claim about a single cause.", "Player error, intent and individual brilliance are not inferred."),
        ))
    return tuple(results)


def _goal_analysis(bundle: CanonicalMatchBundle, goal: pd.Series, profiles: Mapping[Any, EventTeamSeasonProfile]) -> GoalAnalysis:
    scoring = bundle.teams.loc[bundle.teams.team_id.eq(goal.team_id)].iloc[0]
    conceding = bundle.teams.loc[bundle.teams.team_id.ne(goal.team_id)].iloc[0]
    scoring_name = str(scoring.get("team_name", scoring.team_code)); conceding_name = str(conceding.get("team_name", conceding.team_code))
    sequence = _goal_sequence(bundle.events, goal)
    first_seconds = float(sequence.elapsed_seconds.dropna().min()) if sequence.elapsed_seconds.notna().any() else float(goal.elapsed_seconds)
    duration = max(float(goal.elapsed_seconds) - first_seconds, 0.0)
    passes = int(sequence.event_type.eq("Pass").sum()); carries = int(sequence.event_type.eq("Carry").sum())
    start = sequence.iloc[0] if not sequence.empty else goal
    route = "unavailable"
    if not sequence.empty and sequence[["location_y", "end_location_y"]].notna().any(axis=None):
        ys = pd.concat([sequence.location_y, sequence.end_location_y]).dropna()
        route = "central" if ys.between(24, 56).mean() >= .60 else "wide or mixed"
    own_goal = bool(goal.get("is_own_goal", False))
    set_play = str(goal.get("play_pattern")) in SET_PLAY_PATTERNS or str(goal.get("shot_type")) in SET_PLAY_SHOT_TYPES
    counter = str(goal.get("play_pattern")) == "From Counter"
    shot_xg = _number(goal.get("shot_xg"))
    mechanism_metric = "set_play_shots_per90" if set_play else "counter_attack_shots_per90" if counter else None
    exposure_metric = "set_play_shots_conceded_per90" if set_play else "counter_attack_shots_conceded_per90" if counter else None
    scoring_profile, conceding_profile = profiles.get(goal.team_id), profiles.get(conceding.team_id)
    contributors = []
    if own_goal:
        contributors.append(GoalContributor("unusual_event", "The source records this as an own goal.", {"event_type": goal.get("original_event_type")}, "explicit provider event; no blame or intent inferred"))
    if set_play:
        contributors.append(GoalContributor("set_piece_pattern", "The goal came from an explicitly identified set-play context.", {"play_pattern": goal.get("play_pattern"), "shot_type": goal.get("shot_type")}, "event-supported"))
    if counter:
        contributors.append(GoalContributor("transition_after_turnover", "The source explicitly labels the scoring attack as From Counter.", {"play_pattern": "From Counter", "sequence_duration_seconds": duration}, "provider-labelled"))
    prior_shots = bundle.events.loc[bundle.events.team_id.eq(goal.team_id) & bundle.events.event_type.eq("Shot") & bundle.events.event_index.lt(goal.event_index)]
    # "Regular Play" is too broad to constitute a comparable attacking
    # pattern. Earlier-match recurrence is therefore limited to explicitly
    # supported set-play/counter contexts.
    prior_same = prior_shots.loc[prior_shots.play_pattern.eq(goal.get("play_pattern"))] if (set_play or counter) else prior_shots.iloc[0:0]
    if (set_play or counter) and len(prior_same) >= 2:
        contributors.append(GoalContributor("match_specific_tactical_pattern", f"{scoring_name} had already produced {len(prior_same)} shots from the same recorded play context.", {"prior_matching_shots": len(prior_same), "play_pattern": goal.get("play_pattern")}, "earlier-in-match"))
    match_id = str(bundle.matches.match_id.iloc[0])
    scoring_history = scoring_profile.match_metrics.loc[scoring_profile.match_metrics.match_id.astype(str).ne(match_id)] if scoring_profile is not None and "match_id" in scoring_profile.match_metrics else (scoring_profile.match_metrics if scoring_profile is not None else pd.DataFrame())
    conceding_history = conceding_profile.match_metrics.loc[conceding_profile.match_metrics.match_id.astype(str).ne(match_id)] if conceding_profile is not None and "match_id" in conceding_profile.match_metrics else (conceding_profile.match_metrics if conceding_profile is not None else pd.DataFrame())
    if mechanism_metric and len(scoring_history) >= 5 and mechanism_metric in scoring_history:
        recurring = float(pd.to_numeric(scoring_history[mechanism_metric], errors="coerce").fillna(0).gt(0).mean())
        if recurring >= .30:
            contributors.append(GoalContributor("historical_mechanism_context", f"The scoring team recorded at least one related {('set-play' if set_play else 'counter-attack')} shot in {recurring:.0%} of its other season matches. This does not establish recurrence of this goal pattern.", {"metric": mechanism_metric, "match_share_with_occurrence": recurring, "contributing_matches": len(scoring_history)}, "broad historical context only; the current match is excluded"))
    if exposure_metric and len(conceding_history) >= 5 and exposure_metric in conceding_history:
        recurring = float(pd.to_numeric(conceding_history[exposure_metric], errors="coerce").fillna(0).gt(0).mean())
        if recurring >= .30:
            contributors.append(GoalContributor("historical_mechanism_context", f"The conceding team faced at least one related {('set-play' if set_play else 'counter-attack')} shot in {recurring:.0%} of its other season matches. This does not establish a recurring structural problem.", {"metric": exposure_metric, "match_share_with_occurrence": recurring, "contributing_matches": len(conceding_history)}, "broad historical context only; the current match is excluded"))
    if shot_xg is not None and shot_xg <= .08:
        contributors.append(GoalContributor("exceptional_individual_execution", "The finish came from a low-probability shot according to the supplied xG value.", {"shot_xg": shot_xg, "threshold": .08}, "finishing-outcome proxy; does not prove individual brilliance"))
    if not contributors:
        contributors.append(GoalContributor("insufficient_evidence", "No supported contributor passed the current deterministic rules.", {}, "available provider evidence"))
    happened = f"{len(prior_same)} earlier shot{'s' if len(prior_same) != 1 else ''} came from the same recorded set-play or counter-attack context." if len(prior_same) else "No earlier comparable set-play or counter-attack shot passed the current rule." if (set_play or counter) else "Broad open-play labels are not specific enough to establish that this pattern happened earlier."
    recurring_text = next((item.observation for item in contributors if item.category in {"recurring_structural_pattern", "opponent_recurring_attacking_strength"}), "No comparable recurring season pattern passed the current rule.")
    exceptional = any(item.category == "exceptional_individual_execution" for item in contributors)
    structural = any(item.category in {"recurring_structural_pattern", "match_specific_tactical_pattern", "opponent_recurring_attacking_strength"} for item in contributors)
    balance = "Both repeated-pattern evidence and a low-probability finish are present." if exceptional and structural else "The available evidence contains a repeated-pattern signal, but does not establish a single cause." if structural else "The supplied xG makes exceptional execution a plausible contributor; no repeated structural signal qualified." if exceptional else "The available evidence cannot separate structure from execution reliably."
    origin = str(start.get("play_pattern")) if pd.notna(start.get("play_pattern")) else "possession start type unavailable"
    created = "An explicitly tagged counter attack preceded the finish." if counter else "An explicitly identified set play preceded the finish." if set_play else f"The recorded possession contained {passes} passes and {carries} carries before the finish."
    historical = _historical_matches(scoring_profile, mechanism_metric) if mechanism_metric else ()
    actions = tuple(_action(row, index) for index, (_, row) in enumerate(sequence.iterrows(), 1))
    return GoalAnalysis(
        f"{bundle.matches.match_id.iloc[0]}:{goal.event_id}", str(goal.event_id), goal.team_id, scoring_name,
        conceding.team_id, conceding_name, int(goal.period), int(goal.get("minute", float(goal.elapsed_seconds) // 60)),
        int(goal.get("second", float(goal.elapsed_seconds) % 60)), _score_before(bundle.events, goal, goal.team_id, conceding.team_id),
        f"{scoring_name} were awarded an own goal after a {duration:.1f}-second recorded sequence." if own_goal else f"{scoring_name} completed a {duration:.1f}-second recorded possession with a goal from {f'{shot_xg:.2f} xG' if shot_xg is not None else 'a shot whose xG is unavailable'}.",
        created, happened, recurring_text, balance, origin, duration, route, passes, carries,
        _point(goal), shot_xg, actions, tuple(contributors), _goal_tracking(bundle, goal, conceding.team_id), historical,
        ("Contributors are multi-label observations, not a proven causal decomposition.", "Player intention and individual defensive error are not inferred.", "Low xG is only a proxy for difficult execution, not proof of brilliance."),
    )


def build_match_tactical_profile(
    bundle: CanonicalMatchBundle,
    *,
    event_team_profiles: Mapping[str | int, EventTeamSeasonProfile] | None = None,
    tracking_team_profiles: Mapping[str | int, TeamProfileResult] | None = None,
    window_minutes: int = 15,
) -> MatchTacticalProfile:
    """Build both-team match context and one evidence investigation per goal."""
    validate_canonical_bundle(bundle)
    if window_minutes < 5:
        raise ValueError("window_minutes must be at least five.")
    profiles = event_team_profiles or {}
    tracking_profiles = tracking_team_profiles or {}
    match = bundle.matches.iloc[0]
    team_results = []
    tracking_shapes, tracking_windows = _tracking_contexts(bundle, window_minutes)
    event_metrics = calculate_event_team_match_metrics(bundle) if bundle.capabilities.has_events and bundle.events is not None and "coordinate_system" in bundle.events and set(bundle.events.coordinate_system.dropna()) == {"statsbomb_120x80"} else pd.DataFrame()
    if bundle.events is not None:
        order_column = next((column for column in ("event_index", "frame_end", "elapsed_seconds") if column in bundle.events), None)
        order_columns = [column for column in ("period", order_column) if column is not None and column in bundle.events]
        events = bundle.events.sort_values(order_columns, kind="stable") if order_columns else bundle.events.copy()
    else:
        events = pd.DataFrame()
    for team in bundle.teams.itertuples(index=False):
        opponent = bundle.teams.loc[bundle.teams.team_id.ne(team.team_id)].iloc[0]
        team_name = str(getattr(team, "team_name", team.team_code)); opponent_name = str(opponent.get("team_name", opponent.team_code))
        row = event_metrics.loc[event_metrics.team_id.eq(team.team_id)].iloc[0] if not event_metrics.empty else pd.Series(dtype=object)
        event_deviations = _style_deviations(row, profiles.get(team.team_id)) if not row.empty else ()
        tracking_deviations = _tracking_style_deviations(tracking_shapes.get(team.team_id), tracking_profiles.get(team.team_id), bundle.provider)
        deviations = tuple(sorted((*event_deviations, *tracking_deviations), key=lambda item: (-abs(item.robust_standardized_difference or 0), item.metric)))
        event_coordinate_ok = not events.empty and "coordinate_system" in events and set(events.coordinate_system.dropna()) == {"statsbomb_120x80"}
        segments = _segments(events, team.team_id, team_name, window_minutes) if event_coordinate_ok and {"elapsed_seconds", "event_index", "pass_outcome", "shot_xg", "play_pattern"}.issubset(events) else tracking_windows.get(team.team_id, ())
        opponent_row = event_metrics.loc[event_metrics.team_id.eq(opponent.team_id)].iloc[0] if not event_metrics.empty else pd.Series(dtype=object)
        interactions = []
        if not row.empty and not opponent_row.empty:
            if row.possession_share_estimate > opponent_row.possession_share_estimate and row.shots < opponent_row.shots:
                interactions.append(f"{team_name} had more of the ball in the recorded events, while {opponent_name} took more shots.")
            if row.passes_into_penalty_area > opponent_row.passes_into_penalty_area:
                interactions.append(f"{team_name} completed more passes into the box than {opponent_name}.")
            if row.counter_attack_shots > 0:
                interactions.append(f"{team_name} recorded {int(row.counter_attack_shots)} explicitly tagged counter-attack shot{'s' if row.counter_attack_shots != 1 else ''}.")
        headline = deviations[0].football_summary if deviations else f"{team_name}'s strongest match-versus-usual difference did not pass the current evidence rule."
        overview = f"TactIQ found {len(deviations)} clear difference{'s' if len(deviations) != 1 else ''} from their usual game and {sum(bool(item.change_from_previous) for item in segments)} period-to-period change{'s' if sum(bool(item.change_from_previous) for item in segments) != 1 else ''}."
        used = []
        if not event_metrics.empty: used.append("events")
        if bundle.capabilities.has_continuous_tracking: used.append("continuous_tracking")
        team_results.append(TeamMatchTacticalProfile(
            team.team_id, team_name, opponent.team_id, opponent_name, headline, overview,
            deviations, segments, tracking_shapes.get(team.team_id), tuple(interactions), tuple(used),
            ("Season-relative comparisons require a compatible profile for the same provider context.", "Time windows describe event evidence and are not automatically tactical phases."),
        ))
    goals = ()
    if not events.empty and {"shot_outcome", "event_id", "elapsed_seconds", "event_index", "possession_id"}.issubset(events):
        goal_rows = events.loc[events.event_type.eq("Shot") & events.shot_outcome.eq("Goal")].copy()
        goal_rows["is_own_goal"] = False
        own_goals = events.loc[events.event_type.isin(["Own Goal Against", "Own Goal For"])].copy()
        if not own_goals.empty:
            own_goals["is_own_goal"] = True
            own_goals["original_event_type"] = own_goals.event_type
            for index, own in own_goals.iterrows():
                if own.event_type == "Own Goal Against":
                    other = bundle.teams.loc[bundle.teams.team_id.ne(own.team_id)]
                    if len(other) == 1:
                        own_goals.at[index, "team_id"] = other.team_id.iloc[0]
            # StatsBomb can record the same incident as both Own Goal For and
            # Own Goal Against. After resolving the beneficiary, retain one
            # canonical goal and prefer the explicit beneficiary-side event.
            own_goals["own_goal_preference"] = own_goals.original_event_type.eq("Own Goal For").astype(int)
            own_goals = own_goals.sort_values(
                ["period", "elapsed_seconds", "team_id", "own_goal_preference", "event_index"],
                ascending=[True, True, True, False, True], kind="stable",
            ).drop_duplicates(["period", "elapsed_seconds", "team_id"], keep="first")
            goal_rows = pd.concat([goal_rows, own_goals], ignore_index=True).sort_values(["period", "event_index"], kind="stable")
        goals = tuple(_goal_analysis(bundle, row, profiles) for _, row in goal_rows.iterrows())
    elif bundle.capabilities.has_tactical_phases:
        goals = _phase_goal_analyses(bundle)
    capabilities = {name: bool(getattr(bundle.capabilities, name)) for name in vars(bundle.capabilities)}
    coverage = {
        "match_vs_season": "available" if profiles or tracking_profiles else "unavailable: compatible team-season profiles were not supplied",
        "time_windows": "available" if team_results and team_results[0].segments else "unavailable: canonical temporal events are required",
        "tracking_shape": "available" if bundle.capabilities.has_continuous_tracking and bundle.capabilities.has_verified_roles else "unavailable: compatible continuous tracking and verified roles are required",
        "goal_analysis": "available" if goals else "no supported goal events were found",
    }
    identity = {
        "date": match.get("match_date"), "home_team_id": match.get("home_team_id", bundle.teams.iloc[0].team_id),
        "away_team_id": match.get("away_team_id", bundle.teams.iloc[1].team_id), "home_score": match.get("home_score"),
        "away_score": match.get("away_score"), "competition_id": match.get("competition_id"), "season_id": match.get("season_id"),
    }
    return MatchTacticalProfile(
        "tactiq.match-tactical-profile.v1", match.match_id, bundle.provider, identity,
        tuple(team_results), goals, capabilities, coverage,
        ("This is descriptive match evidence, not a causal account or tactical recommendation.", "A goal may have several contributors; absence of a label is not proof that a factor was absent."),
    )
