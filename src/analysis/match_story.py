"""Deterministic, diverse match stories from event-profile evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .event_profile_findings import EventProfileFinding, EventProfileFindingResult, FINDING_METRICS, generate_event_profile_findings
from .event_team_profile import EventTeamSeasonProfile
from .match_archetypes import MatchArchetype, build_match_archetypes
from .metric_relationships import MetricRelationshipFinding, build_metric_relationship_deviations


MIN_STORY_SCORE = 0.45
EVIDENCE_SCORES = {"strong": 1.0, "moderate": .75, "limited": .55, "exploratory": .45}
STORY_TYPE_ORDER = {
    "metric_relationship_residual": 0,
    "match_archetype": 1,
    "single_metric_deviation": 2,
}

EVIDENCE_BASIS = {"strong": "High", "moderate": "Moderate", "limited": "Limited", "exploratory": "Limited"}
TOPIC_ORDER = {
    "possession_circulation": 0,
    "defensive_activity": 0,
    "progression": 1,
    "transition_counter_attack": 2,
    "territorial_access": 2,
    "shot_quantity": 3,
    "chance_creation": 3,
    "shot_quality": 3,
    "shot_location": 4,
    "turnover_exposure": 5,
    "other": 6,
}
ATTACKING_TOPICS = {"possession_circulation", "progression", "territorial_access", "shot_quantity", "chance_creation", "shot_quality", "shot_location"}
TRANSITION_TOPICS = {"transition_counter_attack", "shot_quantity", "chance_creation", "shot_quality", "shot_location"}
DEFENSIVE_TOPICS = {"defensive_activity", "turnover_exposure"}
METRIC_TOPICS = {
    "possession_share_estimate": "possession_circulation", "passes_attempted_per90": "possession_circulation",
    "pass_completion_rate": "possession_circulation", "progressive_passes_per90": "progression",
    "progressive_carries_per90": "progression", "passes_into_final_third_per90": "territorial_access",
    "passes_into_penalty_area_per90": "territorial_access", "shots_per90": "shot_quantity",
    "shots_on_target_per90": "shot_quality", "goals_per90": "chance_creation", "xg_per90": "chance_creation",
    "xg_per_shot": "shot_quality", "average_shot_distance": "shot_location",
    "open_play_shots_per90": "shot_quantity", "set_play_shots_per90": "shot_quantity",
    "counter_attack_shots_per90": "transition_counter_attack", "high_regains_per90": "transition_counter_attack",
    "pressures_per90": "defensive_activity", "tackles_per90": "defensive_activity",
    "interceptions_per90": "defensive_activity", "recoveries_per90": "defensive_activity",
    "turnovers_leading_to_shot_per90": "turnover_exposure",
}
ARCHETYPE_TOPICS = {
    "high_possession_low_progression": "progression",
    "high_progression_high_chance_creation": "chance_creation",
    "low_possession_direct_attack": "transition_counter_attack",
    "high_regain_transition_pressure": "transition_counter_attack",
    "high_penalty_area_access_low_shot_output": "territorial_access",
    "high_shot_volume_low_xg_per_shot": "shot_quality",
}

# Exact event subsets used by the existing deterministic metric definitions.
# Only identical labels count as shared evidence; broad chronology overlap does not.
METRIC_EVENT_SUBSETS = {
    "possession_share_estimate": "team_possession_timeline",
    "passes_attempted_per90": "all_team_passes", "pass_completion_rate": "all_team_passes",
    "progressive_passes_per90": "completed_progressive_passes",
    "progressive_carries_per90": "progressive_carries",
    "passes_into_final_third_per90": "completed_final_third_entries",
    "passes_into_penalty_area_per90": "completed_penalty_area_entries",
    "shots_per90": "all_team_shots", "xg_per90": "all_team_shots",
    "xg_per_shot": "all_team_shots", "average_shot_distance": "all_team_shots",
    "shots_on_target_per90": "shots_on_target", "goals_per90": "goals",
    "open_play_shots_per90": "open_play_shots", "set_play_shots_per90": "set_play_shots",
    "counter_attack_shots_per90": "explicit_counter_attack_shots",
    "high_regains_per90": "high_regains", "pressures_per90": "pressures",
    "tackles_per90": "tackles", "interceptions_per90": "interceptions",
    "recoveries_per90": "recoveries",
    "turnovers_leading_to_shot_per90": "turnover_to_shot_windows",
}

METRIC_LABELS = {
    "possession_share_estimate": "Event-derived possession share",
    "progressive_passes_per90": "Progressive passes per 90",
    "passes_into_final_third_per90": "Final-third pass entries per 90",
    "passes_into_penalty_area_per90": "Penalty-area pass entries per 90",
    "shots_per90": "Shots per 90", "xg_per90": "xG per 90",
    "high_regains_per90": "High regains per 90",
    "counter_attack_shots_per90": "Explicit counter-attack shots per 90",
}


@dataclass(frozen=True)
class MatchStoryPoint:
    story_id: str
    story_type: str
    title: str
    observation: str
    supporting_metrics: tuple[dict, ...]
    comparator: dict
    deviation: dict
    evidence_level: str
    source_match_id: str | int
    contributing_season_match_count: int
    coverage: float
    limitations: tuple[str, ...]
    redundancy_group: str
    priority_score: float
    priority_components: dict
    selection_reason: str
    semantic_topic: str
    chronology: dict
    evidence_basis: str
    primary_evidence_basis: str
    supporting_evidence_bases: tuple[dict, ...]
    merged_candidate_ids: tuple[str, ...]


@dataclass
class MatchStoryResult:
    team_id: str | int
    team_name: str
    match_id: str | int
    story_points: list[MatchStoryPoint]
    candidate_audit: pd.DataFrame
    maximum_story_points: int
    match_context: dict
    status: str
    message: str | None
    presentation_mode: str
    coherence_linkages: tuple[dict, ...]

    def __post_init__(self) -> None:
        if not 2 <= self.maximum_story_points <= 4:
            raise ValueError("maximum_story_points must be between 2 and 4.")
        if len(self.story_points) > self.maximum_story_points:
            raise ValueError("Match story exceeds its configured maximum.")
        if any(point.source_match_id != self.match_id for point in self.story_points):
            raise ValueError("Every story point must reference the selected match.")


def _priority(evidence: str, effect: float, coverage: float, sample: int) -> tuple[float, dict]:
    components = {
        "evidence_strength": EVIDENCE_SCORES[evidence],
        "robust_effect_magnitude": min(abs(effect) / 3.0, 1.0),
        "coverage": min(max(coverage, 0.0), 1.0),
        "sample_adequacy": min(sample / 20.0, 1.0),
    }
    score = (
        .30 * components["evidence_strength"]
        + .30 * components["robust_effect_magnitude"]
        + .20 * components["coverage"]
        + .20 * components["sample_adequacy"]
    )
    return score, components


def _metric_value(metric: str, value: float) -> str:
    if metric == "possession_share_estimate":
        return f"{value * 100:.1f}%"
    return f"{value:.2f}" if "xg" in metric else f"{value:.1f}"


def _single_story_title(finding: EventProfileFinding) -> str:
    high = finding.signed_deviation > 0
    if finding.metric == "passes_into_penalty_area_per90":
        return f"Penalty-area access was unusually {'high' if high else 'low'}"
    if finding.metric == "passes_into_final_third_per90":
        return f"Final-third access was unusually {'high' if high else 'low'}"
    return finding.title


def _candidate_from_metric(finding: EventProfileFinding) -> dict[str, Any]:
    score, components = _priority(finding.evidence_level, finding.robust_z_score, finding.coverage, finding.contributing_match_count)
    label = METRIC_LABELS.get(finding.metric, finding.metric.replace("_", " ").title())
    return {
        "candidate_id": finding.finding_id, "story_type": "single_metric_deviation",
        "title": _single_story_title(finding),
        "observation": f"{label}: {_metric_value(finding.metric, finding.observed_value)} vs season median {_metric_value(finding.metric, finding.season_baseline)}.",
        "supporting_metrics": ({
            "metric": finding.metric, "observed_value": finding.observed_value,
            "season_baseline": finding.season_baseline, "robust_z_score": finding.robust_z_score,
            "unit": finding.unit, "definition": finding.definition,
        },),
        "comparator": {"type": "team_season_median", "value": finding.season_baseline, "metric": finding.metric},
        "deviation": {"signed": finding.signed_deviation, "absolute": finding.absolute_deviation, "relative": finding.relative_deviation, "robust_z_score": finding.robust_z_score},
        "evidence_level": finding.evidence_level, "source_match_id": finding.source_match_id,
        "sample": finding.contributing_match_count, "coverage": finding.coverage,
        "limitations": ("Season-relative univariate deviation; it does not control for opponent or match state.", "Descriptive evidence only; direction is not a quality judgment."),
        "redundancy_group": f"family:{finding.finding_family}",
        "semantic_family": finding.finding_family, "semantic_topic": METRIC_TOPICS.get(finding.metric, "other"),
        "metric_set": frozenset({finding.metric}),
        "priority_score": score, "priority_components": components,
    }


def _candidate_from_archetype(item: MatchArchetype) -> dict[str, Any]:
    sample = min(metric["contributing_match_count"] for metric in item.contributing_metrics)
    coverage = min(metric["coverage"] for metric in item.contributing_metrics)
    score, components = _priority(item.evidence_level, item.rule_strength, coverage, sample)
    metric_set = frozenset(metric["metric"] for metric in item.contributing_metrics)
    evidence = "; ".join(
        f"{METRIC_LABELS.get(metric['metric'], metric['metric'].replace('_', ' ').title())}: "
        f"{_metric_value(metric['metric'], metric['observed_value'])} vs {_metric_value(metric['metric'], metric['season_baseline'])} season median"
        for metric in item.contributing_metrics
    )
    return {
        "candidate_id": item.archetype_id, "story_type": "match_archetype",
        "title": item.title, "observation": evidence + ".",
        "supporting_metrics": item.contributing_metrics,
        "comparator": {"type": "team_season_robust_z_threshold", "value": item.rule_threshold},
        "deviation": {"rule_strength": item.rule_strength, "component_count": len(item.contributing_metrics)},
        "evidence_level": item.evidence_level, "source_match_id": item.match_id,
        "sample": sample, "coverage": coverage,
        "limitations": ("Transparent threshold-based multi-label archetype; it is not a learned cluster.", "The combination is descriptive and does not establish a tactical mechanism."),
        "redundancy_group": f"archetype:{item.archetype}",
        "semantic_family": "multi_metric_archetype", "semantic_topic": ARCHETYPE_TOPICS.get(item.archetype, "other"),
        "metric_set": metric_set,
        "priority_score": score, "priority_components": components,
    }


def _candidate_from_relationship(item: MetricRelationshipFinding) -> dict[str, Any]:
    score, components = _priority(item.evidence_level, item.residual_robust_z, item.coverage, item.contributing_match_count)
    downstream_label = METRIC_LABELS.get(item.downstream_metric, item.downstream_metric.replace("_", " ").title())
    title = item.title
    relationship_topics = {
        ("possession_share_estimate", "progressive_passes_per90"): "progression",
        ("progressive_passes_per90", "passes_into_final_third_per90"): "territorial_access",
        ("passes_into_final_third_per90", "passes_into_penalty_area_per90"): "territorial_access",
        ("passes_into_penalty_area_per90", "shots_per90"): "shot_quantity",
        ("shots_per90", "xg_per90"): "chance_creation",
        ("high_regains_per90", "counter_attack_shots_per90"): "transition_counter_attack",
    }
    if item.upstream_metric == "shots_per90" and item.downstream_metric == "xg_per90":
        title = f"Chance creation was {'higher' if item.residual > 0 else 'lower'} than shot volume would normally suggest"
    observation = (
        f"{downstream_label}: {_metric_value(item.downstream_metric, item.observed_downstream_value)} vs "
        f"{_metric_value(item.downstream_metric, item.expected_downstream_value)} expected from the team's usual "
        f"{METRIC_LABELS.get(item.upstream_metric, item.upstream_metric.replace('_', ' ').title())} → {downstream_label} relationship."
    )
    return {
        "candidate_id": item.finding_id, "story_type": "metric_relationship_residual",
        "title": title, "observation": observation,
        "supporting_metrics": (
            {"metric": item.upstream_metric, "observed_value": item.upstream_value},
            {"metric": item.downstream_metric, "observed_value": item.observed_downstream_value},
        ),
        "comparator": {"type": "theil_sen_expected_downstream", "expected_value": item.expected_downstream_value, "prediction_low": item.residual_prediction_low, "prediction_high": item.residual_prediction_high, "slope": item.slope, "intercept": item.intercept},
        "deviation": {"residual": item.residual, "absolute_residual": item.absolute_residual, "residual_robust_z": item.residual_robust_z},
        "evidence_level": item.evidence_level, "source_match_id": item.match_id,
        "sample": item.contributing_match_count, "coverage": item.coverage,
        "limitations": ("The fitted relationship is descriptive and does not imply that the upstream metric caused the downstream value.", "Prediction bands use robust residual dispersion and are not model confidence intervals."),
        "redundancy_group": f"relationship:{item.upstream_metric}->{item.downstream_metric}",
        "semantic_family": FINDING_METRICS.get(item.downstream_metric, "metric_relationship"),
        "semantic_topic": relationship_topics.get((item.upstream_metric, item.downstream_metric), METRIC_TOPICS.get(item.downstream_metric, "other")),
        "metric_set": frozenset({item.upstream_metric, item.downstream_metric}),
        "priority_score": score, "priority_components": components,
    }


def _overlaps(candidate: dict, selected: list[dict]) -> bool:
    for prior in selected:
        if candidate["redundancy_group"] == prior["redundancy_group"]:
            return True
        intersection = len(candidate["metric_set"] & prior["metric_set"])
        union = len(candidate["metric_set"] | prior["metric_set"])
        if union and intersection / union >= .50:
            return True
        if candidate["story_type"] != "match_archetype" and prior["story_type"] != "match_archetype" and candidate["semantic_family"] == prior["semantic_family"]:
            return True
    return False


def _context_value(row: pd.Series, key: str) -> Any:
    value = row.get(key)
    if value is None or value is pd.NA or (not isinstance(value, (dict, list, tuple)) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def _match_context(profile: EventTeamSeasonProfile, match_id: str | int) -> dict:
    row = profile.match_metrics.loc[profile.match_metrics.match_id.eq(match_id)].iloc[0]
    team_score, opponent_score = _context_value(row, "team_score"), _context_value(row, "opponent_score")
    return {
        "opponent_team_id": _context_value(row, "opponent_team_id"),
        "opponent_team_name": _context_value(row, "opponent_team_name"),
        "home_away": _context_value(row, "home_away"),
        "home_score": _context_value(row, "home_score"),
        "away_score": _context_value(row, "away_score"),
        "team_score": team_score, "opponent_score": opponent_score,
        "team_relative_score": f"{team_score}–{opponent_score}" if team_score is not None and opponent_score is not None else None,
        "match_date": _context_value(row, "match_date"),
        "score_state_exposure": {
            state: {"seconds": _context_value(row, f"{state}_seconds"), "share": _context_value(row, f"{state}_share")}
            for state in ("leading", "drawing", "trailing")
        },
        "score_state_source": _context_value(row, "score_state_source"),
    }


def _candidate_chronology(candidate: dict, metric_chronology: dict) -> dict:
    summaries = [metric_chronology.get(metric) for metric in candidate["metric_set"]]
    summaries = [summary for summary in summaries if isinstance(summary, dict)]
    if not summaries:
        return {"available": False, "basis": "No contributing event-time summary is available."}
    first = min(summary["first_seconds"] for summary in summaries)
    last = max(summary["last_seconds"] for summary in summaries)
    median = float(pd.Series([summary["median_seconds"] for summary in summaries]).median())
    match_fraction = median / max(last, 1.0)
    phase = "early" if match_fraction < .34 else "middle" if match_fraction < .67 else "late"
    return {
        "available": True, "first_seconds": first, "median_seconds": median,
        "last_seconds": last, "event_count": sum(int(summary["event_count"]) for summary in summaries),
        "approximate_match_phase": phase,
        "basis": "First, median and last event times across the contributing metrics; descriptive chronology only.",
    }


def _merge_semantic_topics(candidates: list[dict], metric_chronology: dict) -> list[dict]:
    """Merge exact football topics even when their metric sets differ."""
    merged = []
    evidence_order = {"strong": 3, "moderate": 2, "limited": 1, "exploratory": 0}
    for topic in sorted({candidate["semantic_topic"] for candidate in candidates}, key=lambda value: (TOPIC_ORDER.get(value, 99), value)):
        group = [candidate for candidate in candidates if candidate["semantic_topic"] == topic]
        group.sort(key=lambda row: (STORY_TYPE_ORDER[row["story_type"]], -row["priority_score"], row["candidate_id"]))
        primary = dict(group[0])
        primary["primary_metric_set"] = frozenset(primary["metric_set"])
        primary["primary_event_subsets"] = frozenset(
            METRIC_EVENT_SUBSETS[metric] for metric in primary["metric_set"] if metric in METRIC_EVENT_SUBSETS
        )
        primary["primary_evidence_basis"] = EVIDENCE_BASIS[primary["evidence_level"]]
        primary["supporting_evidence_bases"] = tuple({
            "candidate_id": candidate["candidate_id"],
            "story_type": candidate["story_type"],
            "evidence_level": candidate["evidence_level"],
            "evidence_basis": EVIDENCE_BASIS[candidate["evidence_level"]],
            "is_primary": candidate is group[0],
        } for candidate in group)
        metrics, seen = [], set()
        for candidate in group:
            for metric in candidate["supporting_metrics"]:
                if metric["metric"] not in seen:
                    metrics.append(metric)
                    seen.add(metric["metric"])
        primary["supporting_metrics"] = tuple(metrics)
        primary["metric_set"] = frozenset(seen)
        primary["merged_candidate_ids"] = tuple(candidate["candidate_id"] for candidate in group)
        primary["merged_source_types"] = tuple(dict.fromkeys(candidate["story_type"] for candidate in group))
        if len(group) > 1:
            primary["observation"] = " ".join(dict.fromkeys(candidate["observation"] for candidate in group))
            primary["limitations"] = tuple(dict.fromkeys(limit for candidate in group for limit in candidate["limitations"]))
            strongest = max(group, key=lambda candidate: evidence_order[candidate["evidence_level"]])
            primary["priority_score"] = max(candidate["priority_score"] for candidate in group)
            primary["priority_components"] = strongest["priority_components"]
        primary["chronology"] = _candidate_chronology(primary, metric_chronology)
        merged.append(primary)
    return merged


def _coherent_components(candidates: list[dict]) -> list[list[dict]]:
    components: list[list[dict]] = []
    for track in (ATTACKING_TOPICS, TRANSITION_TOPICS, DEFENSIVE_TOPICS):
        ordered = sorted(
            [candidate for candidate in candidates if candidate["semantic_topic"] in track],
            key=lambda candidate: (TOPIC_ORDER[candidate["semantic_topic"]], candidate["chronology"].get("median_seconds", float("inf")), candidate["candidate_id"]),
        )
        current: list[dict] = []
        for candidate in ordered:
            if current and TOPIC_ORDER[candidate["semantic_topic"]] - TOPIC_ORDER[current[-1]["semantic_topic"]] > 1:
                components.append(current)
                current = []
            current.append(candidate)
        if current:
            components.append(current)
    represented = {candidate["candidate_id"] for component in components for candidate in component}
    components.extend([[candidate] for candidate in candidates if candidate["candidate_id"] not in represented])
    components.extend([[candidate] for candidate in candidates])
    unique, seen = [], set()
    for component in components:
        key = tuple(candidate["candidate_id"] for candidate in component)
        if key not in seen:
            unique.append(component)
            seen.add(key)
    return unique


def _component_score(component: list[dict]) -> float:
    source_bonus = sum(.08 if item["story_type"] == "metric_relationship_residual" else .04 if item["story_type"] == "match_archetype" else 0.0 for item in component) / len(component)
    return sum(item["priority_score"] for item in component) / len(component) + .10 * (len(component) - 1) + source_bonus


def _narrative_candidate_score(candidate: dict) -> float:
    """Tie-break evidence by explanatory role, never by source diversity."""
    explanatory_bonus = {
        "metric_relationship_residual": .08,
        "match_archetype": .18,
        "single_metric_deviation": 0.0,
    }
    return candidate["priority_score"] + explanatory_bonus[candidate["story_type"]]


def _relationship_path(
    left_metrics: frozenset[str], right_metrics: frozenset[str],
    supported_relationships: set[tuple[str, str]], *, maximum_edges: int = 2,
) -> tuple[str, ...] | None:
    adjacency: dict[str, set[str]] = {}
    for upstream, downstream in supported_relationships:
        adjacency.setdefault(upstream, set()).add(downstream)
        adjacency.setdefault(downstream, set()).add(upstream)
    queue = [(metric, (metric,)) for metric in sorted(left_metrics)]
    visited = set(left_metrics)
    while queue:
        metric, path = queue.pop(0)
        if len(path) - 1 >= maximum_edges:
            continue
        for neighbour in sorted(adjacency.get(metric, set())):
            next_path = (*path, neighbour)
            if neighbour in right_metrics:
                return next_path
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append((neighbour, next_path))
    return None


def _coherence_gate(
    selected: list[dict], supported_relationships: set[tuple[str, str]],
) -> tuple[str, tuple[dict, ...]]:
    """Require an evidence graph; topic order and time-span overlap never link points."""
    if len(selected) <= 1:
        return "connected_story", tuple()
    linkages: list[dict] = []
    connected_edges: set[tuple[int, int]] = set()
    for left_index, left in enumerate(selected):
        for right_index in range(left_index + 1, len(selected)):
            right = selected[right_index]
            shared_metrics = sorted(left["primary_metric_set"] & right["primary_metric_set"])
            shared_archetypes = sorted(
                {item for item in left["merged_candidate_ids"] if item.startswith("archetype:")}
                & {item for item in right["merged_candidate_ids"] if item.startswith("archetype:")}
            )
            shared_subsets = sorted(left["primary_event_subsets"] & right["primary_event_subsets"])
            relationship_path = _relationship_path(
                left["primary_metric_set"], right["primary_metric_set"], supported_relationships,
            )
            if shared_metrics:
                linkage_type, evidence = "shared_metric", {"metrics": shared_metrics}
            elif shared_archetypes:
                linkage_type, evidence = "shared_archetype", {"archetype_candidate_ids": shared_archetypes}
            elif relationship_path:
                linkage_type, evidence = "explicit_metric_relationship", {"metric_path": relationship_path}
            elif shared_subsets:
                linkage_type, evidence = "shared_event_subset", {"event_subsets": shared_subsets}
            else:
                continue
            connected_edges.add((left_index, right_index))
            linkages.append({
                "from_story_candidate_id": left["candidate_id"],
                "to_story_candidate_id": right["candidate_id"],
                "linkage_type": linkage_type, **evidence,
            })
    reached = {0}
    changed = True
    while changed:
        changed = False
        for left_index, right_index in connected_edges:
            if left_index in reached and right_index not in reached:
                reached.add(right_index)
                changed = True
            elif right_index in reached and left_index not in reached:
                reached.add(left_index)
                changed = True
    mode = "connected_story" if len(reached) == len(selected) else "parallel_observations"
    return mode, tuple(linkages)


def assemble_match_story(
    profile_or_findings: EventTeamSeasonProfile | EventProfileFindingResult,
    match_id: str | int, *, maximum_story_points: int = 4,
) -> MatchStoryResult:
    """Return up to ``maximum_story_points`` qualified, diverse story points.

    The result is intentionally allowed to contain fewer than three points when
    the evidence gate or redundancy rules leave only one or two useful items.
    """
    if not 2 <= maximum_story_points <= 4:
        raise ValueError("maximum_story_points must be between 2 and 4.")
    finding_result = profile_or_findings if isinstance(profile_or_findings, EventProfileFindingResult) else generate_event_profile_findings(profile_or_findings)
    profile = finding_result.profile
    if match_id not in set(profile.match_metrics.match_id):
        raise KeyError(f"Match {match_id!r} is absent from this team-season profile.")
    relationship_result = build_metric_relationship_deviations(profile)
    candidates = [
        *(_candidate_from_metric(item) for item in finding_result.findings if item.source_match_id == match_id),
        *(_candidate_from_archetype(item) for item in build_match_archetypes(finding_result).assignments if item.match_id == match_id),
        *(_candidate_from_relationship(item) for item in relationship_result.findings if item.match_id == match_id),
    ]
    candidates.sort(key=lambda row: (-row["priority_score"], STORY_TYPE_ORDER[row["story_type"]], row["candidate_id"]))
    eligible = [row for row in candidates if row["priority_score"] >= MIN_STORY_SCORE]
    match_row = profile.match_metrics.loc[profile.match_metrics.match_id.eq(match_id)].iloc[0]
    metric_chronology = _context_value(match_row, "metric_chronology") or {}
    topic_candidates = _merge_semantic_topics(eligible, metric_chronology) if eligible else []
    components = _coherent_components(topic_candidates)
    selected = max(components, key=lambda component: (_component_score(component), len(component), tuple(item["candidate_id"] for item in component))) if components else []
    if len(selected) > 3:
        strongest = sorted(selected, key=lambda row: (-_narrative_candidate_score(row), TOPIC_ORDER[row["semantic_topic"]], row["candidate_id"]))
        keep = 4 if _narrative_candidate_score(strongest[3]) >= .90 else 3
        selected = strongest[:min(keep, maximum_story_points)]
    else:
        selected = selected[:maximum_story_points]
    selected.sort(key=lambda row: (TOPIC_ORDER[row["semantic_topic"]], row["chronology"].get("median_seconds", float("inf")), row["candidate_id"]))
    supported_relationships = set(zip(
        relationship_result.relationship_fits.upstream_metric,
        relationship_result.relationship_fits.downstream_metric,
    )) if not relationship_result.relationship_fits.empty else set()
    presentation_mode, coherence_linkages = _coherence_gate(selected, supported_relationships)
    selection_reason = (
        "strong_standalone" if len(selected) == 1
        else "connected_narrative" if presentation_mode == "connected_story"
        else "qualified_parallel_observation"
    )
    selection_reasons = {row["candidate_id"]: selection_reason for row in selected}
    points = [MatchStoryPoint(
        story_id=f"story:{profile.team_id}:{match_id}:{row['candidate_id']}",
        story_type=row["story_type"], title=row["title"], observation=row["observation"],
        supporting_metrics=tuple(row["supporting_metrics"]), comparator=row["comparator"],
        deviation=row["deviation"], evidence_level=row["evidence_level"],
        source_match_id=row["source_match_id"], contributing_season_match_count=row["sample"],
        coverage=row["coverage"], limitations=tuple(row["limitations"]),
        redundancy_group=row["redundancy_group"], priority_score=row["priority_score"],
        priority_components=row["priority_components"], selection_reason=selection_reasons[row["candidate_id"]],
        semantic_topic=row["semantic_topic"], chronology=row["chronology"],
        evidence_basis=row["primary_evidence_basis"],
        primary_evidence_basis=row["primary_evidence_basis"],
        supporting_evidence_bases=row["supporting_evidence_bases"],
        merged_candidate_ids=row["merged_candidate_ids"],
    ) for row in selected]
    selected_ids = {candidate_id for row in selected for candidate_id in row["merged_candidate_ids"]}
    audit = pd.DataFrame([{
        "candidate_id": row["candidate_id"], "story_type": row["story_type"],
        "source_match_id": row["source_match_id"], "priority_score": row["priority_score"],
        "redundancy_group": row["redundancy_group"], "selected": row["candidate_id"] in selected_ids,
        "semantic_topic": row["semantic_topic"],
        "selection_reason": next((selection_reasons[item["candidate_id"]] for item in selected if row["candidate_id"] in item["merged_candidate_ids"]), None),
    } for row in candidates])
    message = None if points else "No unusual season-relative patterns qualified. This does not mean the match lacked important events."
    return MatchStoryResult(
        profile.team_id, profile.team_name, match_id, points, audit,
        maximum_story_points, _match_context(profile, match_id),
        "story_available" if points else "no_qualifying_patterns", message,
        presentation_mode if points else "no_qualifying_patterns", coherence_linkages,
    )
