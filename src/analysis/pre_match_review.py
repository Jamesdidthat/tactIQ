"""Deterministic, non-prescriptive pre-match review priorities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .matchup_interactions import MatchupInteractionResult
from .opponent_comparison import OpponentComparisonResult


DEFAULT_MAX_PRIORITIES = 5
MIN_PRIORITY_SCORE = 0.58
MAX_PER_FOOTBALL_FAMILY = 2
DEFAULT_SLOT_ADMISSION_THRESHOLDS = (0.58, 0.58, 0.58, 0.66, 0.72)
REVIEW_EVIDENCE_COMPATIBILITY_CATEGORIES = (
    "same_metric",
    "direct_attack_vs_defence_counterpart",
    "validated_relationship",
    "unsupported_cross_metric",
)
PRIMARY_EVIDENCE_COMPATIBILITY = frozenset(REVIEW_EVIDENCE_COMPATIBILITY_CATEGORIES[:3])
SOURCE_ROLES = (
    "directional_matchup_interaction",
    "general_team_comparison",
    "supporting_tendency",
)

METRIC_CONCEPT_LABELS = {
    "possession_share_estimate": "Event-derived possession share",
    "passes_attempted_per90": "Passes attempted per 90",
    "pass_completion_rate": "Pass completion rate",
    "progressive_passes_per90": "Progressive passes per 90",
    "progressive_carries_per90": "Progressive carries per 90",
    "passes_into_final_third_per90": "Final-third entries by pass per 90",
    "passes_into_penalty_area_per90": "Penalty-area entries by pass per 90",
    "shots_per90": "Shots per 90",
    "xg_per90": "xG per 90",
    "xg_per_shot": "xG per shot",
    "shots_on_target_per90": "Shots on target per 90",
    "average_shot_distance": "Average shot distance",
    "pressures_per90": "Pressures per 90",
    "tackles_per90": "Tackles per 90",
    "interceptions_per90": "Interceptions per 90",
    "recoveries_per90": "Recoveries per 90",
    "high_regains_per90": "High regains per 90",
    "turnovers_leading_to_shot_per90": "Turnovers followed by an opposition shot per 90",
    "counter_attack_shots_per90": "Explicit counter-attack shots per 90",
}

METRIC_QUESTION_SUBJECTS = {
    "possession_share_estimate": ("event-derived possession share", "differs"),
    "passes_attempted_per90": ("passes attempted per 90", "differ"),
    "pass_completion_rate": ("pass completion rate", "differs"),
    "progressive_passes_per90": ("progressive passes per 90", "differ"),
    "progressive_carries_per90": ("progressive carries per 90", "differ"),
    "passes_into_final_third_per90": ("final-third entries by pass per 90", "differ"),
    "passes_into_penalty_area_per90": ("penalty-area entries by pass per 90", "differ"),
    "shots_per90": ("shots per 90", "differ"),
    "xg_per90": ("xG per 90", "differs"),
    "xg_per_shot": ("xG per shot", "differs"),
    "shots_on_target_per90": ("shots on target per 90", "differ"),
    "average_shot_distance": ("average shot distance", "differs"),
    "pressures_per90": ("pressures per 90", "differ"),
    "tackles_per90": ("tackles per 90", "differ"),
    "interceptions_per90": ("interceptions per 90", "differ"),
    "recoveries_per90": ("recoveries per 90", "differ"),
    "high_regains_per90": ("high regains per 90", "differ"),
    "turnovers_leading_to_shot_per90": ("turnover-to-shot exposures per 90", "differ"),
    "counter_attack_shots_per90": ("explicit counter-attack shots per 90", "differ"),
}

FAMILY_TOPICS = {
    "possession_circulation": "possession_circulation",
    "progression": "progression",
    "final_third_access": "territorial_access",
    "penalty_area_access": "penalty_area_access",
    "shot_volume_xg": "chance_creation",
    "shot_volume": "chance_creation",
    "xg_production": "chance_creation",
    "shot_quality": "shot_quality",
    "chance_creation": "chance_creation",
    "defensive_activity": "defensive_activity",
    "high_regains": "transition_activity",
    "high_regain_turnover_exposure": "transition_activity",
    "turnover_to_shot_exposure": "turnover_exposure",
    "explicit_counter_attack_shots": "counter_attack",
    "explicit_fast_attacks": "counter_attack",
    "set_play_shots": "set_play",
}

SEMANTIC_PREPARATION_GROUPS = {
    "chance_creation": "attacking_output",
    "shot_quality": "attacking_output",
    "territorial_access": "territorial_access",
    "penalty_area_access": "territorial_access",
}


@dataclass(frozen=True)
class PreMatchReviewPriority:
    priority_id: str
    rank: int
    title: str
    review_question: str
    direction: str
    football_family: str
    primary_source_role: str
    primary_evidence: dict[str, Any]
    supporting_evidence: tuple[dict[str, Any], ...]
    target_baseline: dict[str, Any]
    opponent_baseline: dict[str, Any]
    interaction_strength: float
    evidence_basis: str
    match_counts: dict[str, int]
    coverage: dict[str, float]
    limitations: tuple[str, ...]
    source_finding_ids: tuple[str, ...]
    priority_score: float
    selection_reason: str


@dataclass(frozen=True)
class ReviewPriorityEvidenceCompatibility:
    category: str
    primary_candidate_eligible: bool
    rationale: str
    validation_reference: str | None = None

    def __post_init__(self) -> None:
        if self.category not in REVIEW_EVIDENCE_COMPATIBILITY_CATEGORIES:
            raise ValueError(f"Unknown review evidence compatibility category: {self.category}")
        if self.primary_candidate_eligible != (self.category in PRIMARY_EVIDENCE_COMPATIBILITY):
            raise ValueError("Compatibility eligibility must follow the review evidence contract.")
        if self.category == "validated_relationship" and not self.validation_reference:
            raise ValueError("Validated relationship evidence requires an explicit validation reference.")


def _compatibility(category: str, rationale: str, validation_reference: str | None = None) -> ReviewPriorityEvidenceCompatibility:
    return ReviewPriorityEvidenceCompatibility(
        category=category,
        primary_candidate_eligible=category in PRIMARY_EVIDENCE_COMPATIBILITY,
        rationale=rationale,
        validation_reference=validation_reference,
    )


@dataclass
class PreMatchReviewResult:
    target: dict[str, Any]
    opponent: dict[str, Any]
    priorities: list[PreMatchReviewPriority]
    candidate_audit: pd.DataFrame
    configuration: dict[str, Any]

    def __post_init__(self) -> None:
        if len(self.priorities) > int(self.configuration["maximum_priorities"]):
            raise ValueError("Pre-match priority shortlist exceeds its configured cap.")
        if [item.rank for item in self.priorities] != list(range(1, len(self.priorities) + 1)):
            raise ValueError("Pre-match priority ranks must be contiguous.")
        ids = [item.priority_id for item in self.priorities]
        if len(ids) != len(set(ids)):
            raise ValueError("Pre-match priority IDs must be unique.")


def _topic(family: str) -> str:
    return FAMILY_TOPICS.get(family, family)


def _semantic_group(topic: str) -> str:
    return SEMANTIC_PREPARATION_GROUPS.get(topic, topic)


def _polarity(value: Any) -> int:
    number = float(value or 0.0)
    return 1 if number > 0 else -1 if number < 0 else 0


def _tendency_lookup(tendencies: pd.DataFrame | None, analysed_matches: int) -> dict[str, list[dict[str, Any]]]:
    if tendencies is None or tendencies.empty or analysed_matches <= 0:
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for row in tendencies.to_dict("records"):
        family = str(row.get("finding_family", "other"))
        unusual = int(row.get("unusual_matches", 0))
        result.setdefault(_topic(family), []).append({
            "finding_family": family,
            "unusual_matches": unusual,
            "finding_count": int(row.get("finding_count", 0)),
            "above_baseline": int(row.get("above_baseline", 0)),
            "below_baseline": int(row.get("below_baseline", 0)),
            "recurrence_rate": min(unusual / analysed_matches, 1.0),
            "interpretation": "Count of adequately covered season-relative unusual matches; not a causal tendency.",
        })
    return result


def _recurrence_support(
    topic: str,
    target_tendencies: dict[str, list[dict[str, Any]]],
    opponent_tendencies: dict[str, list[dict[str, Any]]],
) -> tuple[float, tuple[dict[str, Any], ...]]:
    support = []
    for role, lookup in (("target_team", target_tendencies), ("opponent_team", opponent_tendencies)):
        for tendency in lookup.get(topic, []):
            support.append({
                "source_type": "recurring_event_profile_tendency",
                "source_role": "supporting_tendency",
                "team_role": role,
                **tendency,
            })
    recurrence = max((float(item["recurrence_rate"]) for item in support), default=0.0)
    return recurrence, tuple(support)


def _score(adequacy: float, magnitude: float, separation: float, recurrence: float, source_strength: float) -> float:
    return float(
        .27 * adequacy
        + .27 * min(abs(magnitude) / 3.0, 1.0)
        + .18 * separation
        + .10 * recurrence
        + .18 * source_strength
    )


def _interaction_question(family: str, attack: str, defence: str) -> str:
    if family == "high_regain_turnover_exposure":
        return f"Review {attack}'s high-regain activity alongside {defence}'s turnover-to-shot exposure."
    phrases = {
        "penalty_area_access": "penalty-area entries",
        "shot_volume": "shots",
        "xg_production": "xG",
        "shot_quality": "xG per shot",
        "explicit_counter_attack_shots": "explicit counter-attack shots",
        "set_play_shots": "set-play shots",
    }
    subject = phrases.get(family, family.replace("_", " "))
    return f"Review {attack}'s {subject} against {defence}'s usual defensive exposure."


def _interaction_title(family: str, attack: str, defence: str) -> str:
    subject = {
        "penalty_area_access": "Penalty-area entries",
        "shot_volume": "Shots",
        "xg_production": "xG",
        "shot_quality": "xG per shot",
        "high_regain_turnover_exposure": "High regains and turnover exposure",
        "explicit_counter_attack_shots": "Explicit counter-attack shots",
        "set_play_shots": "Set-play shots",
    }.get(family, family.replace("_", " ").title())
    return f"{attack} attack vs {defence} defence: {subject}"


def _possessive(team_name: str) -> str:
    return f"{team_name}'" if team_name.rstrip().lower().endswith("s") else f"{team_name}'s"


def build_metric_review_question(metric: str, target: str, opponent: str) -> str:
    """Return a deterministic metric question with explicit grammatical number."""
    subject, verb = METRIC_QUESTION_SUBJECTS.get(
        metric, (metric.replace("_", " "), "differs"),
    )
    return f"Review how {_possessive(opponent)} {subject} {verb} from {_possessive(target)}."


def _comparison_question(metric: str, target: str, opponent: str) -> str:
    return build_metric_review_question(metric, target, opponent)


def _comparison_title(metric: str, target: str, opponent: str) -> str:
    subject = METRIC_CONCEPT_LABELS.get(metric, metric.replace("_", " ").title())
    return f"{opponent} vs {target}: {subject}"


def _interaction_candidates(
    comparison: OpponentComparisonResult,
    interaction: MatchupInteractionResult,
    target_tendencies: dict[str, list[dict[str, Any]]],
    opponent_tendencies: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = interaction.interactions.set_index(["direction_id", "interaction_family"])
    candidates = []
    target_id = str(comparison.target["team_id"])
    for finding in interaction.findings:
        row = rows.loc[(finding.direction_id, finding.interaction_family)]
        topic = _topic(finding.interaction_family)
        recurrence, supporting = _recurrence_support(topic, target_tendencies, opponent_tendencies)
        adequacy = min(finding.attacking_coverage, finding.defending_coverage) * min(
            min(finding.attacking_contributing_matches, finding.defending_contributing_matches) / 20.0, 1.0
        )
        separation = 1.0 - min(float(row.iqr_overlap_ratio), 1.0)
        compatibility = _compatibility(
            str(row.review_priority_compatibility),
            str(row.comparability_basis),
        )
        score = (
            _score(adequacy, finding.combined_standardized_mismatch, separation, recurrence, finding.interaction_strength_score)
            if compatibility.primary_candidate_eligible else 0.0
        )
        attack_is_target = str(finding.attacking_team_id) == target_id
        direction = "target_attack_vs_opponent_defence" if attack_is_target else "opponent_attack_vs_target_defence"
        attacking_baseline = {
            "team_id": finding.attacking_team_id, "team_name": finding.attacking_team_name,
            "role": "attacking_production", "metric": finding.production_metric,
            "median": finding.attacking_median, "q25": float(row.attacking_q25), "q75": float(row.attacking_q75), "unit": finding.unit,
        }
        defending_baseline = {
            "team_id": finding.defending_team_id, "team_name": finding.defending_team_name,
            "role": "defensive_exposure", "metric": finding.exposure_metric,
            "median": finding.defending_exposure_median, "q25": float(row.defending_exposure_q25), "q75": float(row.defending_exposure_q75), "unit": finding.unit,
        }
        candidates.append({
            "source_type": "matchup_interaction",
            "source_role": "directional_matchup_interaction",
            "source_rank": finding.rank_within_direction,
            "source_id": finding.finding_id,
            "direction": direction,
            "football_family": topic,
            "semantic_group": _semantic_group(topic),
            "story_polarity": _polarity(finding.combined_standardized_mismatch),
            "priority_concept": finding.interaction_family,
            "dedupe_key": f"{direction}:{topic}",
            "title": _interaction_title(finding.interaction_family, finding.attacking_team_name, finding.defending_team_name),
            "review_question": _interaction_question(finding.interaction_family, finding.attacking_team_name, finding.defending_team_name),
            "primary_evidence": {
                "source_type": "matchup_interaction", "source_role": "directional_matchup_interaction",
                "finding_id": finding.finding_id,
                "production_metric": finding.production_metric, "exposure_metric": finding.exposure_metric,
                "signed_mismatch": finding.signed_mismatch,
                "combined_standardized_mismatch": finding.combined_standardized_mismatch,
                "iqr_overlap_ratio": float(row.iqr_overlap_ratio),
                "distributions_materially_overlap": bool(row.distributions_materially_overlap),
                "unit": finding.unit,
                "compatibility": asdict(compatibility),
            },
            "supporting_evidence": supporting,
            "target_baseline": attacking_baseline if attack_is_target else defending_baseline,
            "opponent_baseline": defending_baseline if attack_is_target else attacking_baseline,
            "interaction_strength": finding.interaction_strength_score,
            "evidence_basis": finding.evidence_basis,
            "match_counts": {"attacking_team": finding.attacking_contributing_matches, "defending_team": finding.defending_contributing_matches},
            "coverage": {"attacking_team": finding.attacking_coverage, "defending_team": finding.defending_coverage},
            "limitations": finding.limitations,
            "source_finding_ids": (finding.finding_id,),
            "priority_score": score,
            "recurrence": recurrence,
            "compatibility": compatibility,
        })
    return candidates


def _comparison_candidates(
    comparison: OpponentComparisonResult,
    target_tendencies: dict[str, list[dict[str, Any]]],
    opponent_tendencies: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = comparison.metric_comparisons.set_index("metric")
    candidates = []
    for finding in comparison.findings:
        row = rows.loc[finding.metric]
        topic = _topic(finding.finding_family)
        recurrence, supporting = _recurrence_support(topic, target_tendencies, opponent_tendencies)
        adequacy = min(finding.coverage_target, finding.coverage_opponent) * min(
            min(finding.contributing_matches_target, finding.contributing_matches_opponent) / 20.0, 1.0
        )
        separation = 1.0 - min(float(row.iqr_overlap_ratio), 1.0)
        score = _score(adequacy, finding.combined_standardized_difference, separation, recurrence, finding.priority_score)
        compatibility = _compatibility(
            "same_metric",
            "Both team-season distributions use the same metric, unit, definition, and provider coordinate context.",
        )
        direction = "opponent_vs_target_season_tendency"
        question = _comparison_question(finding.metric, comparison.target["team_name"], comparison.opponent["team_name"])
        candidates.append({
            "source_type": "opponent_comparison", "source_role": "general_team_comparison",
            "source_rank": finding.rank,
            "source_id": finding.finding_id, "direction": direction,
            "football_family": topic,
            "semantic_group": _semantic_group(topic),
            "story_polarity": _polarity(finding.combined_standardized_difference),
            "priority_concept": finding.metric,
            "dedupe_key": f"{direction}:opponent_comparison:{finding.metric}",
            "title": _comparison_title(finding.metric, comparison.target["team_name"], comparison.opponent["team_name"]),
            "review_question": question,
            "primary_evidence": {
                "source_type": "opponent_comparison", "source_role": "general_team_comparison",
                "finding_id": finding.finding_id,
                "metric": finding.metric, "signed_difference": finding.signed_difference,
                "combined_standardized_difference": finding.combined_standardized_difference,
                "iqr_overlap_ratio": float(row.iqr_overlap_ratio),
                "distributions_materially_overlap": finding.distributions_materially_overlap,
                "unit": finding.unit,
                "compatibility": asdict(compatibility),
            },
            "supporting_evidence": supporting,
            "target_baseline": {
                "team_id": comparison.target["team_id"], "team_name": comparison.target["team_name"],
                "role": "target_season", "metric": finding.metric, "median": finding.target_value,
                "q25": float(row.target_q25), "q75": float(row.target_q75), "unit": finding.unit,
            },
            "opponent_baseline": {
                "team_id": comparison.opponent["team_id"], "team_name": comparison.opponent["team_name"],
                "role": "opponent_season", "metric": finding.metric, "median": finding.opponent_value,
                "q25": float(row.opponent_q25), "q75": float(row.opponent_q75), "unit": finding.unit,
            },
            "interaction_strength": finding.priority_score,
            "evidence_basis": finding.evidence_basis,
            "match_counts": {"target_team": finding.contributing_matches_target, "opponent_team": finding.contributing_matches_opponent},
            "coverage": {"target_team": finding.coverage_target, "opponent_team": finding.coverage_opponent},
            "limitations": finding.limitations,
            "source_finding_ids": (finding.finding_id,),
            "priority_score": score, "recurrence": recurrence,
            "compatibility": compatibility,
        })
    return candidates


def _unsupported_interaction_audit_candidates(
    comparison: OpponentComparisonResult,
    interaction: MatchupInteractionResult,
) -> list[dict[str, Any]]:
    """Keep unsupported cross-metric evidence auditable but outside ranking."""
    target_id = str(comparison.target["team_id"])
    rows = interaction.interactions.loc[
        interaction.interactions.review_priority_compatibility.eq("unsupported_cross_metric")
    ]
    candidates = []
    for row in rows.itertuples(index=False):
        direction = "target_attack_vs_opponent_defence" if str(row.attacking_team_id) == target_id else "opponent_attack_vs_target_defence"
        compatibility = _compatibility("unsupported_cross_metric", str(row.comparability_basis))
        source_id = f"matchup-interaction:{row.direction_id}:{row.interaction_family}"
        candidates.append({
            "source_type": "matchup_interaction", "source_role": "directional_matchup_interaction",
            "source_rank": 0,
            "source_id": source_id, "direction": direction,
            "football_family": _topic(str(row.interaction_family)),
            "semantic_group": _semantic_group(_topic(str(row.interaction_family))),
            "story_polarity": 0,
            "priority_concept": str(row.interaction_family),
            "dedupe_key": f"{direction}:{_topic(str(row.interaction_family))}",
            "priority_score": 0.0, "compatibility": compatibility,
        })
    return candidates


def _same_preparation_story(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["semantic_group"] != right["semantic_group"]:
        return False
    if left["story_polarity"] == 0 or right["story_polarity"] == 0:
        return False
    if left["story_polarity"] != right["story_polarity"]:
        return False
    # Distinct validated directional interactions remain independent evidence.
    if (
        left["source_role"] == "directional_matchup_interaction"
        and right["source_role"] == "directional_matchup_interaction"
    ):
        return False
    return left["direction"] == right["direction"] or {
        left["source_role"], right["source_role"]
    } == {"directional_matchup_interaction", "general_team_comparison"}


def _demote_overlapping_general_comparisons(
    candidates: list[dict[str, Any]], *, semantic_grouping: bool,
) -> None:
    """Attach general comparisons to the best qualified directional theme.

    This runs before shortlist scoring. A season-to-season comparison can therefore
    never displace matchup-specific evidence for the same football topic merely
    because its numerical priority score is higher.
    """
    directional = [candidate for candidate in candidates if (
        candidate.get("source_role") == "directional_matchup_interaction"
        and candidate["compatibility"].primary_candidate_eligible
    )]

    for candidate in candidates:
        if candidate.get("source_role") != "general_team_comparison":
            continue
        matches = [row for row in directional if (
            row["football_family"] == candidate["football_family"]
            or (semantic_grouping and _same_preparation_story(row, candidate))
        )]
        if not matches:
            continue
        matches.sort(key=lambda row: (-row["priority_score"], row["direction"], row["source_id"]))
        primary = matches[0]
        exact_topic = primary["football_family"] == candidate["football_family"]
        primary["supporting_evidence"] = (*primary["supporting_evidence"], {
            "source_type": candidate["source_type"],
            "source_role": candidate["source_role"],
            "finding_id": candidate["source_id"],
            "title": candidate["title"],
            "primary_evidence": candidate["primary_evidence"],
            "target_baseline": candidate["target_baseline"],
            "opponent_baseline": candidate["opponent_baseline"],
            "priority_score": candidate["priority_score"],
            "reason": "demoted_to_support_for_directional_theme" if exact_topic else "suppressed_semantic_group_support",
        })
        primary["source_finding_ids"] = (*primary["source_finding_ids"], candidate["source_id"])
        candidate["forced_status"] = "demoted_to_support" if exact_topic else "suppressed_semantic_group"
        candidate["supporting_priority_source_id"] = primary["source_id"]


def build_pre_match_review_priorities(
    comparison: OpponentComparisonResult,
    interaction: MatchupInteractionResult,
    *,
    target_recurring_tendencies: pd.DataFrame | None = None,
    opponent_recurring_tendencies: pd.DataFrame | None = None,
    maximum_priorities: int = DEFAULT_MAX_PRIORITIES,
    minimum_priority_score: float = MIN_PRIORITY_SCORE,
    slot_admission_thresholds: tuple[float, ...] | None = None,
    enable_semantic_group_suppression: bool = True,
) -> PreMatchReviewResult:
    """Create a small deterministic review shortlist from qualified evidence."""
    if not 3 <= maximum_priorities <= 5:
        raise ValueError("maximum_priorities must be between 3 and 5.")
    configured_thresholds = tuple(slot_admission_thresholds or DEFAULT_SLOT_ADMISSION_THRESHOLDS)
    if len(configured_thresholds) < maximum_priorities:
        raise ValueError("slot_admission_thresholds must cover every possible shortlist slot.")
    if any(value < 0 or value > 1 for value in configured_thresholds):
        raise ValueError("slot admission thresholds must be between zero and one.")
    if any(right < left for left, right in zip(configured_thresholds, configured_thresholds[1:])):
        raise ValueError("slot admission thresholds must be non-decreasing.")
    effective_thresholds = tuple(max(float(value), minimum_priority_score) for value in configured_thresholds)
    target_lookup = _tendency_lookup(target_recurring_tendencies, int(comparison.target["analysed_match_count"]))
    opponent_lookup = _tendency_lookup(opponent_recurring_tendencies, int(comparison.opponent["analysed_match_count"]))
    candidates = [
        *_interaction_candidates(comparison, interaction, target_lookup, opponent_lookup),
        *_comparison_candidates(comparison, target_lookup, opponent_lookup),
        *_unsupported_interaction_audit_candidates(comparison, interaction),
    ]
    _demote_overlapping_general_comparisons(
        candidates, semantic_grouping=enable_semantic_group_suppression,
    )
    candidates.sort(key=lambda row: (-row["priority_score"], row["source_type"], row["direction"], row["football_family"], row["source_id"]))

    selected: list[dict[str, Any]] = []
    duplicate_of: dict[str, str] = {}
    seen_keys: dict[str, dict[str, Any]] = {}
    family_counts: dict[str, int] = {}
    audit = []
    for candidate in candidates:
        status, reason = "eligible", ""
        existing = seen_keys.get(candidate["dedupe_key"])
        semantic_existing = next((
            item for item in selected if enable_semantic_group_suppression
            and _same_preparation_story(item, candidate)
        ), None)
        slot_index = min(len(selected), maximum_priorities - 1)
        required_admission_score = effective_thresholds[slot_index]
        if not candidate["compatibility"].primary_candidate_eligible:
            status, reason = "unsupported_cross_metric", "evidence remains visible in interaction analysis but cannot generate or upgrade a review priority"
        elif candidate.get("forced_status") in {"demoted_to_support", "suppressed_semantic_group"}:
            status = candidate["forced_status"]
            reason = f"supports qualified directional theme {candidate['supporting_priority_source_id']}"
        elif existing is not None:
            duplicate_of[candidate["source_id"]] = existing["source_id"]
            existing["supporting_evidence"] = (*existing["supporting_evidence"], {
                "source_type": candidate["source_type"], "finding_id": candidate["source_id"],
                "priority_score": candidate["priority_score"], "reason": "semantically_duplicate_support",
            })
            existing["source_finding_ids"] = (*existing["source_finding_ids"], candidate["source_id"])
            status, reason = "suppressed_duplicate", f"supports {existing['source_id']}"
        elif semantic_existing is not None:
            semantic_existing["supporting_evidence"] = (*semantic_existing["supporting_evidence"], {
                "source_type": candidate["source_type"], "source_role": candidate["source_role"],
                "finding_id": candidate["source_id"], "title": candidate["title"],
                "priority_score": candidate["priority_score"], "reason": "suppressed_semantic_group_support",
            })
            semantic_existing["source_finding_ids"] = (*semantic_existing["source_finding_ids"], candidate["source_id"])
            candidate["supporting_priority_source_id"] = semantic_existing["source_id"]
            status, reason = "suppressed_semantic_group", f"supports {semantic_existing['source_id']}"
        elif candidate["priority_score"] < required_admission_score:
            status = "below_quality_gate" if len(selected) < 3 else "below_slot_threshold"
            reason = f"priority score below slot {len(selected) + 1} threshold {required_admission_score:.2f}"
        elif family_counts.get(candidate["football_family"], 0) >= MAX_PER_FOOTBALL_FAMILY:
            status, reason = "family_cap", f"maximum {MAX_PER_FOOTBALL_FAMILY} priorities for this football family"
        elif len(selected) >= maximum_priorities:
            status, reason = "shortlist_cap", f"maximum {maximum_priorities} priorities reached"
        else:
            seen_keys[candidate["dedupe_key"]] = candidate
            family_counts[candidate["football_family"]] = family_counts.get(candidate["football_family"], 0) + 1
            selected.append(candidate)
            status = "selected"
        audit.append({
            "source_finding_id": candidate["source_id"], "source_type": candidate["source_type"],
            "source_role": candidate["source_role"],
            "direction": candidate["direction"], "football_family": candidate["football_family"],
            "semantic_group": candidate["semantic_group"],
            "priority_score": candidate["priority_score"], "status": status, "reason": reason,
            "required_admission_score": required_admission_score,
            "duplicate_of": duplicate_of.get(candidate["source_id"]),
            "supporting_priority_source_id": candidate.get("supporting_priority_source_id"),
            "compatibility_category": candidate["compatibility"].category,
            "primary_candidate_eligible": candidate["compatibility"].primary_candidate_eligible,
        })

    priorities = []
    for rank, candidate in enumerate(selected, start=1):
        if candidate["source_role"] == "directional_matchup_interaction":
            selection_reason = "directional_matchup_interaction_primary"
        elif candidate["source_role"] == "general_team_comparison":
            selection_reason = "general_comparison_no_directional_theme"
        elif candidate["recurrence"] > 0:
            selection_reason = "season_comparison_with_recurring_support"
        else:
            selection_reason = "priority_fill"
        priorities.append(PreMatchReviewPriority(
            priority_id=f"pre-match-review:{comparison.target['team_id']}:{comparison.opponent['team_id']}:{candidate['direction']}:{candidate['priority_concept']}",
            rank=rank, title=candidate["title"], review_question=candidate["review_question"],
            direction=candidate["direction"], football_family=candidate["football_family"],
            primary_source_role=candidate["source_role"],
            primary_evidence=candidate["primary_evidence"], supporting_evidence=tuple(candidate["supporting_evidence"]),
            target_baseline=candidate["target_baseline"], opponent_baseline=candidate["opponent_baseline"],
            interaction_strength=candidate["interaction_strength"], evidence_basis=candidate["evidence_basis"],
            match_counts=candidate["match_counts"], coverage=candidate["coverage"],
            limitations=tuple(candidate["limitations"]), source_finding_ids=tuple(candidate["source_finding_ids"]),
            priority_score=candidate["priority_score"], selection_reason=selection_reason,
        ))
    return PreMatchReviewResult(
        target=comparison.target, opponent=comparison.opponent, priorities=priorities,
        candidate_audit=pd.DataFrame(audit, columns=[
            "source_finding_id", "source_type", "source_role", "direction", "football_family",
            "semantic_group", "priority_score", "required_admission_score", "status", "reason", "duplicate_of",
            "supporting_priority_source_id",
            "compatibility_category", "primary_candidate_eligible",
        ]),
        configuration={
            "maximum_priorities": maximum_priorities, "minimum_priority_score": minimum_priority_score,
            "slot_admission_thresholds": effective_thresholds[:maximum_priorities],
            "semantic_group_suppression_enabled": enable_semantic_group_suppression,
            "semantic_preparation_groups": SEMANTIC_PREPARATION_GROUPS,
            "maximum_per_football_family": MAX_PER_FOOTBALL_FAMILY,
            "ranking_components": ("evidence_adequacy", "interaction_magnitude", "distribution_separation", "recurrence", "source_strength"),
            "recurrence_interpretation": "Supporting count of adequately covered season-relative unusual matches; not causal evidence.",
            "evidence_compatibility_categories": REVIEW_EVIDENCE_COMPATIBILITY_CATEGORIES,
            "primary_candidate_compatibility": tuple(sorted(PRIMARY_EVIDENCE_COMPATIBILITY)),
            "source_roles": SOURCE_ROLES,
            "source_preference_rule": "qualified directional matchup interactions precede overlapping general team comparisons",
        },
    )
