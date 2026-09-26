"""Subset-safe comparison of event patterns and event-linked 360 context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from .moment_360_context import Moment360Context
from .moment_patterns import MomentPatternResult
from .representative_moments import RepresentativeMoment


DEFAULT_MINIMUM_360_SAMPLE = 3


@dataclass(frozen=True)
class PatternContextMetricSummary:
    metric: str
    metric_label: str
    unit: str
    median: float | None
    q25: float | None
    q75: float | None
    sample_count: int
    coverage: float


@dataclass(frozen=True)
class PatternContextSummary:
    pattern_id: str
    pattern_key: str
    pattern_name: str
    full_event_sample_count: int
    full_eligible_event_sample_count: int
    event_sample_share: float
    snapshot_360_subset_count: int
    snapshot_360_coverage: float
    minimum_360_sample: int
    spatial_summary_available: bool
    scope_statement: str
    metric_summaries: tuple[PatternContextMetricSummary, ...]
    capability_provenance: dict[str, Any]
    limitations: tuple[str, ...]


_METRICS: tuple[tuple[str, str, str], ...] = (
    ("visible_opponent_count", "Visible opponents", "visible_players"),
    ("nearest_opponent_distance", "Nearest opponent distance", "native_statsbomb_units"),
    ("opponents_within_5", "Opponents within 5 units", "visible_players"),
    ("opponents_within_10", "Opponents within 10 units", "visible_players"),
    ("opponents_within_15", "Opponents within 15 units", "visible_players"),
    ("visible_teammates_in_penalty_area", "Visible teammates in penalty area", "visible_players"),
    ("visible_opponents_in_penalty_area", "Visible opponents in penalty area", "visible_players"),
    ("visible_player_width_range", "Visible-player width range", "native_statsbomb_units"),
    ("visible_player_depth_range", "Visible-player depth range", "native_statsbomb_units"),
)


def _value(context: Moment360Context, metric: str) -> Any:
    if metric.startswith("opponents_within_"):
        radius = f"{float(metric.rsplit('_', 1)[1]):.1f}"
        return context.opponents_within_radius.get(radius)
    return getattr(context, metric)


def _summary(
    contexts: Sequence[Moment360Context], metric: str, label: str, unit: str,
) -> PatternContextMetricSummary:
    values = pd.Series([_value(context, metric) for context in contexts], dtype="Float64").dropna().astype(float)
    denominator = len(contexts)
    return PatternContextMetricSummary(
        metric=metric, metric_label=label, unit=unit,
        median=float(values.median()) if not values.empty else None,
        q25=float(values.quantile(.25)) if not values.empty else None,
        q75=float(values.quantile(.75)) if not values.empty else None,
        sample_count=int(len(values)), coverage=float(len(values) / denominator) if denominator else 0.0,
    )


def build_pattern_context_summaries(
    pattern_result: MomentPatternResult,
    moments: Sequence[RepresentativeMoment],
    contexts: Mapping[str, Moment360Context],
    *,
    minimum_360_sample: int = DEFAULT_MINIMUM_360_SAMPLE,
) -> tuple[PatternContextSummary, ...]:
    """Summarize spatial context without changing event-pattern denominators."""
    if minimum_360_sample < 1:
        raise ValueError("minimum_360_sample must be at least 1.")
    moments_by_event = {moment.event_id: moment for moment in moments}
    assignment_by_pattern: dict[str, list[str]] = {}
    for assignment in pattern_result.assignments:
        if assignment.event_id not in moments_by_event:
            raise ValueError("Pattern assignment references a moment outside the supplied event sample.")
        for pattern_id in assignment.pattern_ids:
            assignment_by_pattern.setdefault(pattern_id, []).append(assignment.event_id)

    output = []
    for pattern in pattern_result.patterns:
        event_ids = assignment_by_pattern.get(pattern.pattern_id, [])
        if len(event_ids) != pattern.moment_count:
            raise ValueError("Pattern count and event assignment count disagree.")
        snapshot_contexts = [
            contexts[event_id] for event_id in event_ids
            if event_id in contexts
            and contexts[event_id].available
            and contexts[event_id].spatial_context_mode == "event_plus_360_snapshot"
        ]
        subset_count = len(snapshot_contexts)
        coverage = subset_count / pattern.moment_count if pattern.moment_count else 0.0
        available = subset_count >= minimum_360_sample
        if available:
            scope_statement = (
                f"Among {subset_count} 360-observed examples of this retrieved pattern, "
                "the spatial values below describe only the available 360 subset."
            )
            metrics = tuple(_summary(snapshot_contexts, *definition) for definition in _METRICS)
        else:
            scope_statement = (
                f"360 coverage is {subset_count}/{pattern.moment_count} retrieved pattern examples; "
                f"below the minimum sample of {minimum_360_sample}, so no spatial summary is generated."
            )
            metrics = ()
        output.append(PatternContextSummary(
            pattern_id=pattern.pattern_id, pattern_key=pattern.pattern_key,
            pattern_name=pattern.pattern_name, full_event_sample_count=pattern.moment_count,
            full_eligible_event_sample_count=pattern.eligible_moment_count,
            event_sample_share=pattern.share_of_eligible_moments,
            snapshot_360_subset_count=subset_count, snapshot_360_coverage=float(coverage),
            minimum_360_sample=minimum_360_sample, spatial_summary_available=available,
            scope_statement=scope_statement, metric_summaries=metrics,
            capability_provenance={
                "event_pattern_capability": "has_events",
                "spatial_context_capability": "has_360_snapshots",
                "spatial_context_mode_required": "event_plus_360_snapshot",
                "coordinate_system": "statsbomb_120x80",
                "continuous_tracking_used": False,
            },
            limitations=(
                "The event-derived pattern count uses the full retrieved eligible event sample and is not reduced by missing 360 data.",
                "Spatial summaries apply only to exactly event-linked 360 snapshots and must not be extrapolated to the season or full event sample.",
                "360 freeze frames are partial visible-area snapshots, not full-team or continuous tracking.",
                "No team shape, compactness, passing lanes, overloads, pressure structure, marking, or off-ball movement is inferred.",
            ),
        ))
    return tuple(output)
