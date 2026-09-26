"""Deterministic historical event moments for pre-match review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.data.canonical import CanonicalMatchBundle, validate_canonical_bundle

from .event_team_profile import (
    FAILED_INTERCEPTION_OUTCOMES,
    FINAL_THIRD_X,
    HIGH_REGAIN_X,
    PENALTY_AREA_X,
    PENALTY_AREA_Y,
    SET_PLAY_PATTERNS,
    SET_PLAY_SHOT_TYPES,
    _progressive,
    _turnover_shot_links,
    EventTeamSeasonProfile,
)
from .pre_match_review import PreMatchReviewPriority


EventBundleResolver = Callable[[str, int], CanonicalMatchBundle]

SUPPORTED_EVENT_METRICS = {
    "passes_into_penalty_area_per90": "penalty_area_entries",
    "passes_into_penalty_area_conceded_per90": "penalty_area_entries",
    "passes_into_final_third_per90": "final_third_entries",
    "shots_per90": "shots",
    "shots_conceded_per90": "shots",
    "xg_per90": "xg",
    "xg_conceded_per90": "xg",
    "xg_per_shot": "xg_per_shot",
    "xg_per_shot_conceded": "xg_per_shot",
    "interceptions_per90": "interceptions",
    "high_regains_per90": "high_regains",
    "counter_attack_shots_per90": "counter_attacks",
    "counter_attack_shots_conceded_per90": "counter_attacks",
    "set_play_shots_per90": "set_play_shots",
    "set_play_shots_conceded_per90": "set_play_shots",
    "progressive_passes_per90": "progressive_passes",
    "progressive_carries_per90": "progressive_carries",
    "pass_completion_rate": "pass_completion",
    "turnovers_leading_to_shot_per90": "turnover_to_shot",
}


@dataclass(frozen=True)
class RepresentativeMoment:
    match_id: int
    team_id: int | str
    team_name: str
    opponent_id: int | str
    opponent_name: str
    match_date: str
    minute: int
    second: int
    period: int
    event_id: str
    event_type: str
    metric: str
    family: str
    description: str
    relevant_values: dict[str, Any]
    score_state: str | None
    score_state_verified: bool
    score_state_team_id: int | str
    score_state_team_name: str
    source_provenance: dict[str, Any]
    video_availability_status: str
    reason_selected: str
    evidence_side: str


@dataclass(frozen=True)
class RepresentativeMomentResult:
    priority_id: str
    supported: bool
    moments: tuple[RepresentativeMoment, ...]
    requested_limit: int
    query_mappings: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    suppressed_duplicates: tuple[dict[str, Any], ...] = ()


def _metric_query(metric: str) -> str | None:
    return SUPPORTED_EVENT_METRICS.get(metric)


def _score_states(bundle: CanonicalMatchBundle, perspective_team_id: Any) -> tuple[dict[str, str], bool]:
    events = bundle.events.loc[bundle.events.period.le(4)].sort_values(["period", "event_index"], kind="stable")
    match = bundle.matches.iloc[0]
    is_home = perspective_team_id == match.home_team_id
    expected_for = int(match.home_score if is_home else match.away_score)
    expected_against = int(match.away_score if is_home else match.home_score)
    goals_for = goals_against = 0
    states: dict[str, str] = {}
    for event in events.itertuples(index=False):
        states[str(event.event_id)] = "leading" if goals_for > goals_against else "trailing" if goals_for < goals_against else "drawing"
        scoring_team = None
        if event.event_type == "Shot" and event.shot_outcome == "Goal":
            scoring_team = event.team_id
        elif event.event_type == "Own Goal Against":
            scoring_team = next((team for team in bundle.teams.team_id if team != event.team_id), None)
        elif event.event_type == "Own Goal For":
            scoring_team = event.team_id
        if scoring_team == perspective_team_id:
            goals_for += 1
        elif scoring_team is not None:
            goals_against += 1
    return states, goals_for == expected_for and goals_against == expected_against


def _event_mask(events: pd.DataFrame, query: str, acting_team_id: Any) -> pd.Series:
    team = events.team_id.eq(acting_team_id)
    actions = events.event_type.isin({"Pass", "Carry"})
    if query == "penalty_area_entries":
        starts_inside = events.location_x.ge(PENALTY_AREA_X) & events.location_y.between(*PENALTY_AREA_Y)
        ends_inside = events.end_location_x.ge(PENALTY_AREA_X) & events.end_location_y.between(*PENALTY_AREA_Y)
        completed_or_carry = events.event_type.eq("Carry") | (events.event_type.eq("Pass") & events.pass_outcome.isna())
        return team & actions & completed_or_carry & ~starts_inside & ends_inside
    if query == "final_third_entries":
        completed_or_carry = events.event_type.eq("Carry") | (events.event_type.eq("Pass") & events.pass_outcome.isna())
        return team & actions & completed_or_carry & events.location_x.lt(FINAL_THIRD_X) & events.end_location_x.ge(FINAL_THIRD_X)
    if query == "progressive_passes":
        passes = team & events.event_type.eq("Pass") & events.pass_outcome.isna()
        return passes & _progressive(events)
    if query == "progressive_carries":
        return team & events.event_type.eq("Carry") & _progressive(events)
    if query == "pass_completion":
        return team & events.event_type.eq("Pass")
    if query in {"shots", "xg", "xg_per_shot"}:
        return team & events.event_type.eq("Shot")
    if query == "interceptions":
        return team & events.event_type.eq("Interception") & ~events.outcome.isin(FAILED_INTERCEPTION_OUTCOMES)
    if query == "high_regains":
        recovery = events.event_type.eq("Ball Recovery") & ~events.ball_recovery_failure.fillna(False).astype(bool)
        interception = events.event_type.eq("Interception") & ~events.outcome.isin(FAILED_INTERCEPTION_OUTCOMES)
        return team & (recovery | interception) & events.location_x.ge(HIGH_REGAIN_X)
    if query == "counter_attacks":
        return team & events.event_type.eq("Shot") & events.play_pattern.eq("From Counter")
    if query == "set_play_shots":
        return team & events.event_type.eq("Shot") & (
            events.play_pattern.isin(SET_PLAY_PATTERNS) | events.shot_type.isin(SET_PLAY_SHOT_TYPES)
        )
    # Turnover-to-shot candidates require two adjacent possessions and are
    # constructed by _turnover_shot_links rather than a single-row mask.
    if query == "turnover_to_shot":
        return pd.Series(False, index=events.index)
    return pd.Series(False, index=events.index)


def _description(team_name: str, event: pd.Series, query: str) -> str:
    action = str(event.event_type).lower()
    if query == "penalty_area_entries":
        return f"{team_name} completed a {action} into the defined penalty area."
    if query == "final_third_entries":
        return f"{team_name} completed a {action} across the final-third boundary."
    if query == "progressive_passes":
        return f"{team_name} completed a pass satisfying the existing progressive-pass definition."
    if query == "progressive_carries":
        return f"{team_name} completed a carry satisfying the existing progressive-carry definition."
    if query == "pass_completion":
        status = "completed" if pd.isna(event.pass_outcome) else "incomplete"
        return f"{team_name} recorded a {status} pass, selected as an illustrative component of the season completion rate."
    if query == "turnover_to_shot":
        return f"{team_name}'s possession-ending event was followed by an opposition shot under the existing 15-second and first-10-events definition."
    if query in {"xg", "xg_per_shot"} and pd.notna(event.shot_xg):
        return f"{team_name} recorded a shot valued at {float(event.shot_xg):.2f} xG."
    if query == "shots":
        return f"{team_name} recorded a shot."
    if query == "interceptions":
        return f"{team_name} recorded a successful interception."
    if query == "high_regains":
        return f"{team_name} regained the ball in the defined high-regain zone."
    if query == "counter_attacks":
        return f"{team_name} recorded a shot explicitly tagged From Counter."
    return f"{team_name} recorded a set-play shot under the existing classification."


def _relevant_values(event: pd.Series, shot_distribution: dict[str, float] | None = None) -> dict[str, Any]:
    values = {
        "xg": None if pd.isna(event.shot_xg) else float(event.shot_xg),
        "start_coordinates": None if pd.isna(event.location_x) or pd.isna(event.location_y) else [float(event.location_x), float(event.location_y)],
        "end_coordinates": None if pd.isna(event.end_location_x) or pd.isna(event.end_location_y) else [float(event.end_location_x), float(event.end_location_y)],
        "play_pattern": None if pd.isna(event.play_pattern) else str(event.play_pattern),
        "shot_type": None if pd.isna(event.shot_type) else str(event.shot_type),
        "shot_outcome": None if pd.isna(event.shot_outcome) else str(event.shot_outcome),
    }
    if shot_distribution:
        values["team_season_shot_xg_distribution"] = shot_distribution
    return values


def _select_balanced_pass_completion(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Select deterministic completed/incomplete examples without implying rate decomposition."""
    if not candidates or limit <= 0:
        return []
    frame = pd.DataFrame(candidates).sort_values(["match_date", "match_id", "event_index"], kind="stable")
    selected: list[dict[str, Any]] = []
    status_groups = {
        "completed_pass_example": frame.loc[frame.pass_completed.astype(bool)],
        "incomplete_pass_example": frame.loc[~frame.pass_completed.astype(bool)],
    }
    per_status_limit = (limit + 1) // 2
    for status, group in status_groups.items():
        for _, row in group.drop_duplicates("match_id", keep="first").head(per_status_limit).iterrows():
            item = row.to_dict()
            item["reason_selected"] = status
            selected.append(item)
    selected_ids = {item["event_id"] for item in selected}
    if len(selected) < limit:
        for _, row in frame.loc[~frame.event_id.isin(selected_ids)].iterrows():
            item = row.to_dict()
            item["reason_selected"] = (
                "completed_pass_example" if item["pass_completed"] else "incomplete_pass_example"
            )
            selected.append(item)
            selected_ids.add(item["event_id"])
            if len(selected) >= limit:
                break
    selected.sort(key=lambda row: (row["match_date"], row["match_id"], row["event_index"], row["reason_selected"]))
    return selected[:limit]


def _match_anchor_reason(value: float, distribution: pd.Series) -> str:
    anchors = {
        "lower_quartile_match_example": float(distribution.quantile(.25)),
        "typical_match_example": float(distribution.median()),
        "upper_quartile_match_example": float(distribution.quantile(.75)),
        "high_match_example": float(distribution.max()),
    }
    return min(anchors, key=lambda label: (abs(value - anchors[label]), label))


def _select_diverse(candidates: list[dict[str, Any]], limit: int, query: str) -> list[dict[str, Any]]:
    if not candidates or limit <= 0:
        return []
    frame = pd.DataFrame(candidates)
    if query == "pass_completion":
        return _select_balanced_pass_completion(candidates, limit)
    if query == "xg":
        frame = frame.sort_values(["selection_value", "match_id", "event_index"], ascending=[False, True, True], kind="stable")
        frame = frame.drop_duplicates("match_id", keep="first")
        frame["reason_selected"] = "highest_xg_shot_across_distinct_match"
        return frame.head(limit).to_dict("records")
    if query == "xg_per_shot":
        valid = frame.loc[frame.selection_value.notna()].copy()
        if valid.empty:
            return []
        anchors = [
            ("lower_quality_example", float(valid.selection_value.quantile(.25))),
            ("typical_quality_example", float(valid.selection_value.median())),
            ("higher_quality_example", float(valid.selection_value.quantile(.75))),
            ("highest_quality_example", float(valid.selection_value.max())),
        ]
        chosen, used_events, used_matches = [], set(), set()
        for reason, anchor in anchors:
            pool = valid.loc[~valid.event_id.isin(used_events)].copy()
            pool["distance"] = pool.selection_value.sub(anchor).abs()
            pool["match_repeat"] = pool.match_id.isin(used_matches)
            row = pool.sort_values(["match_repeat", "distance", "match_date", "event_index"], kind="stable").iloc[0].to_dict()
            row["reason_selected"] = reason
            chosen.append(row); used_events.add(row["event_id"]); used_matches.add(row["match_id"])
            if len(chosen) >= limit:
                break
        return chosen
    frame = frame.sort_values(["match_date", "match_id", "event_index"], kind="stable")
    per_match = []
    used_states: set[str] = set()
    for _, group in frame.groupby("match_id", sort=False):
        choices = group.assign(state_repeat=group.score_state.fillna("unavailable").isin(used_states))
        row = choices.sort_values(["state_repeat", "event_index"], kind="stable").iloc[0].to_dict()
        used_states.add(str(row.get("score_state") or "unavailable"))
        per_match.append(row)
    match_values = pd.Series([row["match_metric_value"] for row in per_match], dtype=float).dropna()
    for row in per_match:
        row["reason_selected"] = _match_anchor_reason(float(row["match_metric_value"]), match_values) if not match_values.empty else "distinct_match_example"
    anchors_order = {"lower_quartile_match_example": 0, "typical_match_example": 1, "upper_quartile_match_example": 2, "high_match_example": 3, "distinct_match_example": 4}
    per_match.sort(key=lambda row: (anchors_order[row["reason_selected"]], row["match_date"], row["match_id"]))
    selected, reasons = [], set()
    for row in per_match:
        if row["reason_selected"] not in reasons:
            selected.append(row); reasons.add(row["reason_selected"])
    for row in per_match:
        if len(selected) >= limit:
            break
        if row["event_id"] not in {item["event_id"] for item in selected}:
            selected.append(row)
    return selected[:limit]


def _query_profile(
    profile: EventTeamSeasonProfile,
    metric: str,
    *, evidence_side: str,
    resolver: EventBundleResolver,
    limit: int,
) -> tuple[list[RepresentativeMoment], dict[str, Any]]:
    query = _metric_query(metric)
    mapping = {"metric": metric, "query": query, "evidence_side": evidence_side, "team_id": profile.team_id}
    if query is None:
        return [], mapping
    conceded = "conceded" in metric or evidence_side == "defensive_exposure"
    candidates: list[dict[str, Any]] = []
    profile_values = pd.to_numeric(profile.match_metrics.get(metric), errors="coerce")
    for position, match_row in profile.match_metrics.reset_index(drop=True).iterrows():
        bundle = resolver(str(match_row.provider), int(match_row.match_id))
        validate_canonical_bundle(bundle)
        if bundle.events is None:
            continue
        perspective_team_id = profile.team_id
        acting_team_id = match_row.opponent_team_id if conceded else profile.team_id
        team_row = bundle.teams.loc[bundle.teams.team_id.eq(acting_team_id)]
        opponent_row = bundle.teams.loc[bundle.teams.team_id.ne(acting_team_id)]
        if team_row.empty or opponent_row.empty:
            continue
        team_name = str(team_row.iloc[0].team_name)
        states, verified = _score_states(bundle, perspective_team_id)
        eligible_events = bundle.events.loc[bundle.events.period.le(4)]
        if query == "turnover_to_shot":
            links = _turnover_shot_links(eligible_events, acting_team_id)
            link_by_event_id = {link["turnover_event_id"]: link for link in links}
            events = eligible_events.loc[
                eligible_events.event_id.astype(str).isin(link_by_event_id)
            ].copy()
        else:
            link_by_event_id = {}
            events = eligible_events.loc[_event_mask(eligible_events, query, acting_team_id)].copy()
        for _, event in events.iterrows():
            link = link_by_event_id.get(str(event.event_id))
            candidates.append({
                "bundle": bundle, "event": event, "event_id": str(event.event_id),
                "event_index": int(event.event_index), "match_id": int(match_row.match_id),
                "match_date": str(match_row.match_date), "team_id": acting_team_id,
                "team_name": team_name, "opponent_id": opponent_row.iloc[0].team_id,
                "opponent_name": str(opponent_row.iloc[0].team_name),
                "score_state": states.get(str(event.event_id)) if verified else None,
                "score_state_verified": verified,
                "selection_value": float(event.shot_xg) if query in {"xg", "xg_per_shot"} and pd.notna(event.shot_xg) else float(event.event_index),
                "shot_xg_value": float(event.shot_xg) if event.event_type == "Shot" and pd.notna(event.shot_xg) else np.nan,
                "match_metric_value": float(profile_values.iloc[position]) if position < len(profile_values) and pd.notna(profile_values.iloc[position]) else np.nan,
                "query": query, "metric": metric, "evidence_side": evidence_side,
                "pass_completed": bool(event.event_type == "Pass" and pd.isna(event.pass_outcome)),
                "turnover_shot_link": link,
            })
    selected = _select_diverse(candidates, limit, query)
    shot_distribution = None
    if query in {"shots", "xg", "xg_per_shot", "counter_attacks", "set_play_shots"}:
        shot_values = pd.Series([
            item["shot_xg_value"] for item in candidates
            if item.get("shot_xg_value") is not None and pd.notna(item["shot_xg_value"])
        ], dtype=float)
        if not shot_values.empty:
            shot_distribution = {
                "q25": float(shot_values.quantile(.25)), "median": float(shot_values.median()),
                "q75": float(shot_values.quantile(.75)), "shot_count": int(len(shot_values)),
            }
    moments = []
    for item in selected:
        event = item["event"]
        relevant_values = _relevant_values(event, shot_distribution)
        if query == "pass_completion":
            relevant_values.update({
                "pass_completed": bool(item["pass_completed"]),
                "illustrative_rate_component": True,
                "interpretation": "One pass does not represent the season percentage; balanced examples illustrate its completed and incomplete components.",
            })
        if query == "progressive_passes":
            relevant_values["progressive_pass_definition"] = (
                "Completed pass moving at least 10 native x units toward x=120 and reducing "
                "Euclidean distance to goal centre (120,40) by at least 25%."
            )
        if query == "progressive_carries":
            relevant_values["progressive_carry_definition"] = (
                "Carry moving at least 10 native x units toward x=120 and reducing "
                "Euclidean distance to goal centre (120,40) by at least 25%."
            )
        if query == "turnover_to_shot" and item.get("turnover_shot_link"):
            relevant_values.update(item["turnover_shot_link"])
        moments.append(RepresentativeMoment(
            match_id=item["match_id"], team_id=item["team_id"], team_name=item["team_name"],
            opponent_id=item["opponent_id"], opponent_name=item["opponent_name"], match_date=item["match_date"],
            minute=int(event.minute), second=int(event.second), period=int(event.period),
            event_id=str(event.event_id), event_type=str(event.event_type), metric=metric, family=query,
            description=_description(item["team_name"], event, query),
            relevant_values=relevant_values,
            score_state=item["score_state"], score_state_verified=bool(item["score_state_verified"]),
            score_state_team_id=profile.team_id, score_state_team_name=profile.team_name,
            source_provenance={
                "provider": item["bundle"].provider, "source_table": "canonical_events",
                "coordinate_system": str(event.coordinate_system), "query_definition": query,
                "historical_season_only": True,
            },
            video_availability_status="unavailable_in_statsbomb_open_data",
            reason_selected=str(item["reason_selected"]), evidence_side=evidence_side,
        ))
    return moments, mapping


def _deduplicate_moments(
    moments: list[RepresentativeMoment],
) -> tuple[list[RepresentativeMoment], tuple[dict[str, Any], ...]]:
    """Deduplicate by provider + stable event ID while preserving first-seen order."""
    unique: list[RepresentativeMoment] = []
    seen: dict[tuple[str, str], RepresentativeMoment] = {}
    suppressed: list[dict[str, Any]] = []
    for moment in moments:
        provider = str(moment.source_provenance.get("provider") or "").strip()
        event_id = str(moment.event_id).strip()
        if not provider or not event_id:
            raise ValueError("Representative-event uniqueness cannot be reconciled without provider and event ID.")
        key = provider, event_id
        if key not in seen:
            seen[key] = moment
            unique.append(moment)
            continue
        kept = seen[key]
        suppressed.append({
            "provider": provider,
            "event_id": event_id,
            "kept_metric": kept.metric,
            "kept_evidence_side": kept.evidence_side,
            "suppressed_metric": moment.metric,
            "suppressed_evidence_side": moment.evidence_side,
            "reason": "same_stable_provider_event_id",
        })
    return unique, tuple(suppressed)


def build_representative_match_moments(
    priority: PreMatchReviewPriority,
    target_profile: EventTeamSeasonProfile,
    opponent_profile: EventTeamSeasonProfile,
    resolver: EventBundleResolver,
    *,
    limit: int = 8,
) -> RepresentativeMomentResult:
    """Return 5–10 deterministic historical moments where evidence permits."""
    if not 5 <= limit <= 10:
        raise ValueError("Representative moment limit must be between 5 and 10.")
    profiles = {str(target_profile.team_id): target_profile, str(opponent_profile.team_id): opponent_profile}
    requests: list[tuple[EventTeamSeasonProfile, str, str]] = []
    primary = priority.primary_evidence
    if priority.primary_source_role == "directional_matchup_interaction":
        attacking_id = str(priority.target_baseline["team_id"] if priority.target_baseline["role"] == "attacking_production" else priority.opponent_baseline["team_id"])
        defending_id = str(priority.target_baseline["team_id"] if priority.target_baseline["role"] == "defensive_exposure" else priority.opponent_baseline["team_id"])
        requests.extend([
            (profiles[attacking_id], str(primary["production_metric"]), "attacking_production"),
            (profiles[defending_id], str(primary["exposure_metric"]), "defensive_exposure"),
        ])
    else:
        metric = str(primary["metric"])
        requests.extend([
            (target_profile, metric, "target_team_history"),
            (opponent_profile, metric, "opponent_team_history"),
        ])
    moment_groups: list[list[RepresentativeMoment]] = []
    mappings = []
    for profile, metric, side in requests:
        found, mapping = _query_profile(profile, metric, evidence_side=side, resolver=resolver, limit=limit)
        moment_groups.append(found); mappings.append(mapping)
    moments: list[RepresentativeMoment] = []
    for index in range(max((len(group) for group in moment_groups), default=0)):
        for group in moment_groups:
            if index < len(group):
                moments.append(group[index])
    moments, suppressed_duplicates = _deduplicate_moments(moments)
    supported = any(mapping["query"] is not None for mapping in mappings)
    limitations = [
        "Moments are historical examples of the measured event definition; they do not explain or prove the future matchup interaction.",
        "StatsBomb Open Data event IDs are preserved, but linked match video is not supplied.",
    ]
    if not supported:
        limitations.append("This priority's primary metric does not yet have a representative-event query mapping.")
    if any(not moment.score_state_verified for moment in moments):
        limitations.append("Score state is omitted where the event goal timeline does not reconcile with the recorded final score.")
    return RepresentativeMomentResult(
        priority_id=priority.priority_id, supported=supported, moments=tuple(moments[:limit]),
        requested_limit=limit, query_mappings=tuple(mappings), limitations=tuple(limitations),
        suppressed_duplicates=suppressed_duplicates,
    )


def build_team_style_concept_moments(
    concept_id: str,
    metrics: tuple[str, ...] | list[str],
    profile: EventTeamSeasonProfile,
    resolver: EventBundleResolver,
    *,
    limit: int = 6,
) -> RepresentativeMomentResult:
    """Return real historical examples supporting one football-style concept.

    This adapts the already-validated metric-to-event query definitions used by
    pre-match evidence packs.  It does not infer new patterns or convert event
    sequences into tracking-like player movement.
    """
    if not 1 <= limit <= 10:
        raise ValueError("Team-style representative moment limit must be between 1 and 10.")
    requested_metrics = tuple(dict.fromkeys(str(metric) for metric in metrics))
    groups: list[list[RepresentativeMoment]] = []
    mappings: list[dict[str, Any]] = []
    per_metric_limit = max(2, min(limit, 4))
    for metric in requested_metrics:
        if _metric_query(metric) is None:
            mappings.append({
                "metric": metric, "query": None, "evidence_side": "team_style_history",
                "team_id": profile.team_id,
            })
            continue
        evidence_side = "defensive_exposure" if "conceded" in metric else "team_style_history"
        found, mapping = _query_profile(
            profile, metric, evidence_side=evidence_side, resolver=resolver, limit=per_metric_limit,
        )
        groups.append(found)
        mappings.append(mapping)
    interleaved: list[RepresentativeMoment] = []
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position < len(group):
                interleaved.append(group[position])
    moments, suppressed = _deduplicate_moments(interleaved)
    supported = any(mapping.get("query") is not None for mapping in mappings)
    limitations = [
        "These are deterministic examples of the event definitions supporting this team-style concept, not proof of tactical intent or cause.",
        "The pitch playback reconstructs recorded on-ball events; it does not invent unobserved player movement or continuous team shape.",
        "StatsBomb Open Data does not include linked match video.",
    ]
    if not supported:
        limitations.append("None of this concept's supporting metrics has a faithful event-level example mapping.")
    return RepresentativeMomentResult(
        priority_id=f"team-style:{concept_id}", supported=supported,
        moments=tuple(moments[:limit]), requested_limit=limit,
        query_mappings=tuple(mappings), limitations=tuple(limitations),
        suppressed_duplicates=suppressed,
    )
