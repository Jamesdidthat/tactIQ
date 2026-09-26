"""Deterministic prioritisation and traceable evidence packs for findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from numbers import Integral
from typing import Any, Mapping

import pandas as pd

from .tactical_findings import MatchAnalysisResult, TacticalFinding


@dataclass(frozen=True)
class FindingPriority:
    finding_id: str
    evidence_strength: float
    sample_adequacy: float
    effect_magnitude: float
    temporal_relevance: float
    data_quality_coverage: float
    redundancy_penalty: float
    priority_score: float
    comparator: Mapping[str, Any]
    redundancy_group: str
    suppressed_as_duplicate: bool


@dataclass(frozen=True)
class EvidencePack:
    finding_id: str
    match_id: str | int
    team_id: str | int
    title: str
    priority: FindingPriority
    exact_metrics: Mapping[str, float | int | str]
    comparator: Mapping[str, Any]
    supporting_references: tuple[Mapping[str, Any], ...]
    representative_moments: tuple[Mapping[str, Any], ...]
    capability_provenance: Mapping[str, Any]
    coverage: Mapping[str, Any]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.exact_metrics or not self.capability_provenance:
            raise ValueError("EvidencePack requires exact metrics and capability provenance.")
        if len(self.representative_moments) > 3:
            raise ValueError("EvidencePack supports at most three representative moments.")


@dataclass
class FindingPrioritizationResult:
    priorities: pd.DataFrame
    shortlist: list[TacticalFinding]
    evidence_packs: list[EvidencePack]
    selection_reasons: Mapping[str, str]


DEFAULT_FAMILY_CAPS: Mapping[str, int] = {
    "phase_shape": 4,
    "team_shape_extreme": 2,
    "shot_sequence_local_context": 2,
    "other": 2,
}


def _finding_family(finding_type: str) -> str:
    """Map stable finding types into product-facing diversification families."""
    if finding_type == "phase_shape_variability":
        return "phase_shape"
    if finding_type == "team_shape_extreme":
        return "team_shape_extreme"
    if finding_type in {"shot_sequence_density", "shot_local_context"}:
        return "shot_sequence_local_context"
    return "other"


def _top_selection_reason(family: str) -> str:
    return {
        "phase_shape": "top_phase_shape",
        "team_shape_extreme": "top_team_shape_extreme",
        "shot_sequence_local_context": "top_shot_sequence",
        "other": "top_other",
    }[family]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _baseline_and_effect(finding: TacticalFinding) -> tuple[dict[str, Any], float, bool]:
    """Return an explicit contextual comparator and normalised effect score."""
    metrics = finding.evidence_metrics
    if finding.finding_type == "team_shape_extreme":
        median = float(metrics["median_metres"])
        q95 = float(metrics["q95_metres"])
        deviation = q95 - median
        relative = deviation / max(abs(median), 1.0)
        return ({"type": "team_frame_median", "value_metres": median, "deviation_metres": deviation, "relative_deviation": relative}, _clamp(relative / 0.30), True)
    if finding.finding_type == "phase_shape_variability":
        if 'dimension' in metrics:
            median = float(metrics['median_metres'])
            dispersion = float(metrics['iqr_metres'])
            relative = dispersion / max(abs(median), 1.)
            return ({'type': 'within_team_phase_dimension', 'dimension': metrics['dimension'],
                     'median_metres': median, 'q25_metres': metrics['q25_metres'], 'q75_metres': metrics['q75_metres'],
                     'dispersion_metres': dispersion, 'relative_dispersion': relative}, _clamp(relative / .35), True)
        width = float(metrics["width_iqr_metres"])
        length = float(metrics["length_iqr_metres"])
        median_dimension = max(float(metrics["median_width_metres"]), float(metrics["median_length_metres"]), 1.0)
        dispersion = max(width, length)
        relative = dispersion / median_dimension
        return ({"type": "within_team_phase_median_dimension", "value_metres": median_dimension, "dispersion_metres": dispersion, "relative_dispersion": relative}, _clamp(relative / 0.35), True)
    # Event density and one-off shot snapshots currently lack an independent
    # team/phase comparator. Keep that limitation explicit and cap their score.
    return ({"type": "no_independent_contextual_baseline", "value": None}, 0.0, False)


def _temporal_relevance(finding_type: str) -> float:
    return {
        "shot_local_context": 1.0,
        "shot_sequence_density": 0.9,
        "phase_shape_variability": 0.65,
        "team_shape_extreme": 0.45,
    }.get(finding_type, 0.25)


def _redundancy_group(finding: TacticalFinding) -> str:
    if finding.finding_type == "team_shape_extreme":
        return f"{finding.team_id}:team_shape_extreme"
    if finding.finding_type == "phase_shape_variability":
        metrics = finding.evidence_metrics
        if 'dimension' in metrics:
            dimension = metrics['dimension'] if metrics.get('dimensions_materially_distinct') == 1 else 'shared_dimensions'
            return f"{finding.match_id}:{finding.team_id}:phase_shape:{metrics['possession_status']}:{metrics['tactical_phase']}:{dimension}"
        # Possession status is embedded in the deterministic ID after the type.
        parts = finding.finding_id.split(":")
        status = parts[-2] if len(parts) >= 2 else "unknown"
        return f"{finding.team_id}:phase_shape:{status}"
    return f"{finding.team_id}:{finding.finding_type}"


def _coverage_score(result: MatchAnalysisResult, finding: TacticalFinding) -> float:
    mapping = {
        "team_shape_extreme": "team_shape",
        "phase_shape_variability": "phase_shape_analysis",
        "shot_local_context": "local_defensive_context",
        "shot_sequence_density": "temporal_shot_analysis",
    }
    analysis = mapping.get(finding.finding_type)
    if analysis is None:
        return 0.0
    covered = result.analysis_coverage.loc[result.analysis_coverage.analysis.eq(analysis)]
    if covered.empty or covered.status.iloc[0] != "run":
        return 0.0
    # Analysis ran plus an auditable set of references. This deliberately does
    # not invent an unavailable denominator such as possession time.
    return 1.0 if finding.supporting_references else 0.8


def prioritize_findings(
    result: MatchAnalysisResult,
    *,
    shortlist_size: int = 8,
    family_caps: Mapping[str, int] | None = None,
    minimum_priority: float = 0.35,
    minimum_evidence_strength: float = 0.55,
) -> FindingPrioritizationResult:
    """Score, de-duplicate, and order deterministic findings stably.

    Findings with no independent contextual baseline cannot exceed 0.50 even
    when their raw value is large. Near duplicates share a deterministic group;
    only the best member enters the shortlist and the rest retain their visible
    suppression metadata in ``priorities``.
    """
    if shortlist_size < 1:
        raise ValueError("shortlist_size must be at least one.")
    if not 0 <= minimum_priority <= 1 or not 0 <= minimum_evidence_strength <= 1:
        raise ValueError("Minimum shortlist quality thresholds must be within [0, 1].")
    caps = {**DEFAULT_FAMILY_CAPS, **dict(family_caps or {})}
    if any(not isinstance(cap, Integral) or isinstance(cap, bool) or cap < 1 for cap in caps.values()):
        raise ValueError("Every family cap must be a positive integer.")
    provisional = []
    for finding in result.findings:
        comparator, effect, has_baseline = _baseline_and_effect(finding)
        evidence = 0.85 if finding.confidence_level == "descriptive_moderate" else 0.55
        sample = _clamp(finding.sample_size / (20 if finding.evidence_metrics.get('sample_unit') == 'phase intervals' else 300))
        coverage = _coverage_score(result, finding)
        temporal = _temporal_relevance(finding.finding_type)
        raw = 0.25 * evidence + 0.22 * sample + 0.25 * effect + 0.13 * temporal + 0.15 * coverage
        raw *= 1.0 if has_baseline else 0.55
        raw = min(raw, 0.50) if not has_baseline else raw
        provisional.append({"finding": finding, "comparator": comparator, "evidence_strength": evidence, "sample_adequacy": sample, "effect_magnitude": effect, "temporal_relevance": temporal, "data_quality_coverage": coverage, "raw_score": raw, "redundancy_group": _redundancy_group(finding)})
    provisional.sort(key=lambda item: (-item["raw_score"], item["finding"].finding_id))
    leaders: set[str] = set()
    priority_rows = []
    priority_by_id: dict[str, FindingPriority] = {}
    for item in provisional:
        suppressed = item["redundancy_group"] in leaders
        if not suppressed:
            leaders.add(item["redundancy_group"])
        penalty = 0.35 if suppressed else 0.0
        score = item["raw_score"] * (1 - penalty)
        priority = FindingPriority(item["finding"].finding_id, item["evidence_strength"], item["sample_adequacy"], item["effect_magnitude"], item["temporal_relevance"], item["data_quality_coverage"], penalty, score, item["comparator"], item["redundancy_group"], suppressed)
        priority_by_id[priority.finding_id] = priority
        priority_rows.append({**asdict(priority), "match_id": item["finding"].match_id, "team_id": item["finding"].team_id, "finding_type": item["finding"].finding_type, "finding_family": _finding_family(item["finding"].finding_type)})
    priorities = pd.DataFrame(priority_rows).sort_values(["suppressed_as_duplicate", "priority_score", "finding_id"], ascending=[True, False, True], kind="stable").reset_index(drop=True) if priority_rows else pd.DataFrame()
    selection_reasons: dict[str, str] = {}
    selected_ids: list[str] = []
    if not priorities.empty:
        eligible = priorities.loc[
            ~priorities.suppressed_as_duplicate
            & priorities.priority_score.ge(minimum_priority)
            & priorities.evidence_strength.ge(minimum_evidence_strength)
        ].copy()
        # The full priorities table remains unchanged: quality gating only
        # affects the product shortlist.
        eligible_families = eligible.finding_family.drop_duplicates().tolist()
        family_counts = {family: 0 for family in eligible_families}

        # Seed the best observation from each qualifying family. Families are
        # visited by the score and ID of their leader, never dictionary order.
        leaders = eligible.groupby("finding_family", sort=False).head(1)
        for row in leaders.itertuples(index=False):
            if len(selected_ids) >= shortlist_size:
                break
            selected_ids.append(row.finding_id)
            family_counts[row.finding_family] += 1
            selection_reasons[row.finding_id] = _top_selection_reason(row.finding_family)

        # Fill by the original score order while respecting each family cap.
        for row in eligible.itertuples(index=False):
            if len(selected_ids) >= shortlist_size:
                break
            if row.finding_id in selection_reasons:
                continue
            cap = caps.get(row.finding_family, caps["other"])
            if family_counts[row.finding_family] >= cap:
                continue
            selected_ids.append(row.finding_id)
            family_counts[row.finding_family] += 1
            selection_reasons[row.finding_id] = "priority_fill"

        # With only one qualifying family, a hard cap would merely truncate an
        # otherwise useful match. Fill remaining slots explicitly and visibly.
        if len(eligible_families) == 1:
            for row in eligible.itertuples(index=False):
                if len(selected_ids) >= shortlist_size:
                    break
                if row.finding_id in selection_reasons:
                    continue
                selected_ids.append(row.finding_id)
                selection_reasons[row.finding_id] = "single_family_fallback"
    shortlist = [finding for finding in result.findings if finding.finding_id in selected_ids]
    shortlist.sort(key=lambda finding: (-priority_by_id[finding.finding_id].priority_score, finding.finding_id))
    packs = [build_evidence_pack(finding, priority_by_id[finding.finding_id], result) for finding in shortlist]
    return FindingPrioritizationResult(priorities=priorities, shortlist=shortlist, evidence_packs=packs, selection_reasons=selection_reasons)


def build_evidence_pack(finding: TacticalFinding, priority: FindingPriority, result: MatchAnalysisResult) -> EvidencePack:
    """Package exact evidence and provenance without creating new claims."""
    capabilities = result.metadata.get("capabilities")
    capability_values = asdict(capabilities) if hasattr(capabilities, "__dataclass_fields__") else dict(capabilities or {})
    references = tuple(finding.supporting_references)
    moments = tuple(reference for reference in references if "frame" in reference)[:3]
    coverage = result.analysis_coverage.loc[result.analysis_coverage.status.eq("run"), ["analysis", "status", "finding_count"]].to_dict("records")
    return EvidencePack(
        finding_id=finding.finding_id, match_id=finding.match_id, team_id=finding.team_id, title=finding.title,
        priority=priority, exact_metrics=finding.evidence_metrics, comparator=priority.comparator,
        supporting_references=references, representative_moments=moments,
        capability_provenance={"provider": result.metadata.get("provider"), "capabilities": capability_values, "required_capabilities": finding.required_capabilities, "allow_assumed_roles": result.metadata.get("allow_assumed_roles", False)},
        coverage={"analysis_coverage": coverage, "finding_sample_size": finding.sample_size, "reference_count": len(references)}, limitations=finding.limitations,
    )
