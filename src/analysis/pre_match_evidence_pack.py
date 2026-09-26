"""Deterministic assembly of analyst-facing pre-match evidence packs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .moment_360_context import Moment360Context
from .moment_patterns import MomentPatternResult
from .moment_sequence_similarity import MomentSequenceGroupingResult
from .pattern_context_comparison import PatternContextSummary
from .pre_match_review import PreMatchReviewPriority
from .representative_moment_detail import RepresentativeMomentDetail
from .representative_moments import RepresentativeMomentResult


@dataclass(frozen=True)
class PreMatchEvidencePack:
    priority: PreMatchReviewPriority
    why_selected: dict[str, Any]
    primary_source_role: str
    primary_interaction_or_comparison: dict[str, Any]
    supporting_tendencies: tuple[dict[str, Any], ...]
    season_baselines: dict[str, Any]
    distribution_summary: dict[str, Any]
    sequence_pattern_summaries: dict[str, Any]
    representative_moments: tuple[Any, ...]
    representative_moment_details: tuple[RepresentativeMomentDetail, ...]
    optional_360_context: dict[str, Any]
    capability_provenance: dict[str, Any]
    limitations: tuple[str, ...]
    video_status: dict[str, Any]
    technical_provenance: dict[str, Any]

    def __post_init__(self) -> None:
        primary = self.primary_interaction_or_comparison
        if primary.get("finding_id") not in self.priority.source_finding_ids:
            raise ValueError("Evidence-pack primary evidence must preserve a selected source finding ID.")
        compatibility = primary.get("compatibility", {})
        if compatibility.get("category") == "unsupported_cross_metric":
            raise ValueError("Unsupported cross-metric evidence cannot be primary evidence in a pack.")
        moment_ids = [str(moment.event_id) for moment in self.representative_moments]
        if len(moment_ids) != len(set(moment_ids)):
            raise ValueError("Representative moment IDs must be unique within an evidence pack.")
        if any(str(detail.event_id) not in moment_ids for detail in self.representative_moment_details):
            raise ValueError("Moment detail must reference a representative moment in the same pack.")


def _deduplicated(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _football_concept(priority: PreMatchReviewPriority) -> str:
    return priority.title.rsplit(":", 1)[-1].strip().lower()


def _why_selected_description(priority: PreMatchReviewPriority) -> str:
    """Describe the evidence contrast without exposing shortlist machinery."""
    concept = _football_concept(priority)
    if priority.primary_source_role == "directional_matchup_interaction":
        baselines = (priority.target_baseline, priority.opponent_baseline)
        attacking = next(item for item in baselines if item.get("role") == "attacking_production")
        defending = next(item for item in baselines if item.get("role") == "defensive_exposure")
        return (
            f"This was surfaced because {attacking['team_name']}'s attacking {concept} differs materially from "
            f"{defending['team_name']}'s usual defensive exposure across well-covered season samples."
        )
    return (
        f"This was surfaced because {priority.opponent_baseline['team_name']}'s {concept} differs materially from "
        f"{priority.target_baseline['team_name']}'s across well-covered season samples."
    )


def _analyst_limitations(*, moments: RepresentativeMomentResult | None) -> tuple[str, ...]:
    limitations = [
        "This evidence is descriptive: it does not establish cause, predict the matchup, or recommend a tactical response."
    ]
    if moments is None or not moments.supported:
        limitations.append("No faithful representative-event query is available for this measured concept.")
    else:
        limitations.append(
            "Sequence patterns describe only the retrieved representative examples, not full-season event frequencies."
        )
    return tuple(limitations[:3])


def build_pre_match_evidence_pack(
    priority: PreMatchReviewPriority,
    *,
    target_identity: Mapping[str, Any],
    opponent_identity: Mapping[str, Any],
    comparison_compatibility: Mapping[str, Any],
    moments: RepresentativeMomentResult | None = None,
    moment_patterns: MomentPatternResult | None = None,
    moment_sequences: MomentSequenceGroupingResult | None = None,
    moment_details: Mapping[str, RepresentativeMomentDetail] | None = None,
    pattern_context_summaries: Sequence[PatternContextSummary] = (),
) -> PreMatchEvidencePack:
    """Assemble existing evidence without selecting, scoring, or recomputing claims."""
    primary = dict(priority.primary_evidence)
    compatibility = dict(primary.get("compatibility") or {})
    if compatibility.get("primary_candidate_eligible") is False:
        raise ValueError("Primary evidence is not eligible under the review compatibility contract.")

    unsupported_support, supported = [], []
    for item in priority.supporting_evidence:
        evidence = dict(item)
        support_compatibility = evidence.get("compatibility") or evidence.get("primary_evidence", {}).get("compatibility", {})
        if support_compatibility.get("category") == "unsupported_cross_metric":
            unsupported_support.append(str(evidence.get("finding_id") or evidence.get("source_id") or "unidentified"))
        else:
            supported.append(evidence)

    representative_moments = tuple(moments.moments) if moments is not None else ()
    details_by_id = dict(moment_details or {})
    details = tuple(
        details_by_id[moment.event_id]
        for moment in representative_moments
        if moment.event_id in details_by_id
    )
    contexts: tuple[Moment360Context, ...] = tuple(
        detail.moment_360_context for detail in details
        if detail.moment_360_context.available
        and detail.moment_360_context.spatial_context_mode == "event_plus_360_snapshot"
    )
    moment_count = len(representative_moments)
    statuses = tuple(sorted({str(moment.video_availability_status) for moment in representative_moments}))
    video_available = any("unavailable" not in status.lower() for status in statuses)

    detailed_limitations = [
        *priority.limitations,
        *(moments.limitations if moments is not None else ("Representative-event evidence is unavailable for this pack.",)),
        *(moment_patterns.limitations if moment_patterns is not None else ()),
        *(moment_sequences.limitations if moment_sequences is not None else ()),
        "Sequence-pattern counts and shares describe only the retrieved representative sample, not full-season frequencies.",
        "Any 360 evidence applies only to exactly aligned partial snapshots and is not extrapolated to other moments or the season.",
        "This pack preserves deterministic evidence and does not provide tactical recommendations, causal interpretation, or match prediction.",
    ]
    if unsupported_support:
        detailed_limitations.append(
            "Unsupported or non-comparable supporting evidence was excluded from the evidence sections and retained only in provenance."
        )
    if not video_available:
        detailed_limitations.append("Linked match video is unavailable in the configured source data.")

    event_patterns = tuple(moment_patterns.patterns) if moment_patterns is not None else ()
    sequence_groups = tuple(moment_sequences.patterns) if moment_sequences is not None else ()
    return PreMatchEvidencePack(
        priority=priority,
        why_selected={
            "selection_reason": priority.selection_reason,
            "description": _why_selected_description(priority),
            "rank": priority.rank,
            "priority_score": priority.priority_score,
            "evidence_support": priority.evidence_basis,
            "source_finding_ids": priority.source_finding_ids,
        },
        primary_source_role=priority.primary_source_role,
        primary_interaction_or_comparison=primary,
        supporting_tendencies=tuple(supported),
        season_baselines={
            "target": dict(priority.target_baseline),
            "opponent": dict(priority.opponent_baseline),
            "unit_of_historical_evidence": "match",
        },
        distribution_summary={
            "target": {
                "median": priority.target_baseline.get("median"),
                "q25": priority.target_baseline.get("q25"),
                "q75": priority.target_baseline.get("q75"),
                "matches": priority.match_counts,
                "coverage": priority.coverage,
            },
            "opponent": {
                "median": priority.opponent_baseline.get("median"),
                "q25": priority.opponent_baseline.get("q25"),
                "q75": priority.opponent_baseline.get("q75"),
                "matches": priority.match_counts,
                "coverage": priority.coverage,
            },
            "iqr_overlap_ratio": primary.get("iqr_overlap_ratio"),
            "distributions_materially_overlap": primary.get("distributions_materially_overlap"),
            "direction": priority.direction,
        },
        sequence_pattern_summaries={
            "retrieved_sample_count": moment_count,
            "denominator_statement": "Counts and shares use retrieved representative moments, not all season events.",
            "event_patterns": event_patterns,
            "event_sequence_groups": sequence_groups,
        },
        representative_moments=representative_moments,
        representative_moment_details=details,
        optional_360_context={
            "available": bool(contexts),
            "observed_moment_count": len(contexts),
            "representative_moment_count": moment_count,
            "coverage": len(contexts) / moment_count if moment_count else 0.0,
            "scope": "Subset-only event-linked spatial context; never continuous tracking.",
            "contexts": contexts,
            "pattern_context_summaries": tuple(pattern_context_summaries),
        },
        capability_provenance={
            "target": dict(target_identity),
            "opponent": dict(opponent_identity),
            "comparison_compatibility": dict(comparison_compatibility),
            "primary_evidence_compatibility": compatibility,
            "direction": priority.direction,
            "primary_source_role": priority.primary_source_role,
            "source_finding_ids": priority.source_finding_ids,
            "unsupported_supporting_evidence_ids": tuple(unsupported_support),
            "representative_moment_providers": tuple(sorted({
                str(moment.source_provenance.get("provider", "unknown"))
                for moment in representative_moments
            })),
            "continuous_tracking_used": False,
        },
        limitations=_analyst_limitations(moments=moments),
        video_status={
            "available": video_available,
            "statuses": statuses,
            "message": (
                "Video availability is recorded on the representative moments."
                if video_available
                else "Video is unavailable for the retrieved representative moments."
            ),
        },
        technical_provenance={
            "internal_selection": {
                "selection_reason": priority.selection_reason,
                "rank": priority.rank,
                "priority_score": priority.priority_score,
            },
            "evidence_identities": {
                "source_finding_ids": priority.source_finding_ids,
                "primary": primary,
                "supporting": tuple(supported),
                "unsupported_supporting_evidence_ids": tuple(unsupported_support),
            },
            "representative_event_queries": (
                moments.query_mappings if moments is not None else ()
            ),
            "suppressed_representative_duplicates": (
                moments.suppressed_duplicates if moments is not None else ()
            ),
            "coordinate_systems": tuple(sorted({
                str(moment.source_provenance.get("coordinate_system"))
                for moment in representative_moments
                if moment.source_provenance.get("coordinate_system")
            })),
            "sequence_subgroup_ids": tuple(sorted({
                subgroup_id
                for group in sequence_groups
                for subgroup_id in group.original_subgroup_ids
            })),
            "capability_provenance": {
                "target": dict(target_identity),
                "opponent": dict(opponent_identity),
                "comparison_compatibility": dict(comparison_compatibility),
                "primary_evidence_compatibility": compatibility,
                "continuous_tracking_used": False,
            },
            "detailed_limitations": _deduplicated(detailed_limitations),
        },
    )
