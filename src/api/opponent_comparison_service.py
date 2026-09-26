"""Product-facing service for deterministic pre-match opponent comparisons."""

from __future__ import annotations

from dataclasses import asdict
from threading import RLock
from typing import Callable

from src.analysis import (
    analyze_matchup_interactions,
    build_pre_match_review_priorities,
    build_moment_patterns,
    build_moment_sequence_grouping,
    build_pattern_context_summaries,
    build_pre_match_briefing,
    build_pre_match_evidence_pack,
    build_representative_moment_detail,
    build_representative_match_moments,
    compare_event_team_profiles,
    generate_event_profile_findings,
)

from .event_profile_service import EventProfileResolver
from .schemas import json_safe
from src.data import CanonicalMatchBundle


class OpponentComparisonService:
    def __init__(
        self,
        resolver: EventProfileResolver,
        event_bundle_resolver: Callable[[str, int], CanonicalMatchBundle] | None = None,
        *,
        minimum_360_pattern_sample: int = 3,
    ) -> None:
        if minimum_360_pattern_sample < 1:
            raise ValueError("minimum_360_pattern_sample must be at least 1.")
        self._resolver = resolver
        self._event_bundle_resolver = event_bundle_resolver
        self._minimum_360_pattern_sample = minimum_360_pattern_sample
        self._cache: dict[tuple[str, ...], object] = {}
        self._interaction_cache: dict[tuple[str, ...], object] = {}
        self._review_cache: dict[tuple[str, ...], object] = {}
        self._moment_cache: dict[tuple[str, ...], object] = {}
        self._moment_detail_cache: dict[tuple[str, ...], object] = {}
        self._moment_pattern_cache: dict[tuple[str, ...], object] = {}
        self._moment_context_cache: dict[tuple[str, ...], object] = {}
        self._pattern_context_cache: dict[tuple[str, ...], object] = {}
        self._moment_sequence_detail_cache: dict[tuple[str, ...], object] = {}
        self._moment_sequence_group_cache: dict[tuple[str, ...], object] = {}
        self._evidence_pack_cache: dict[tuple[str, ...], object] = {}
        self._briefing_cache: dict[tuple[str, ...], object] = {}
        self._lock = RLock()

    def _get(
        self, target_provider, target_team_id, target_competition_id, target_season_id,
        opponent_provider, opponent_team_id, opponent_competition_id, opponent_season_id,
    ):
        key = tuple(map(str, (
            target_provider, target_team_id, target_competition_id, target_season_id,
            opponent_provider, opponent_team_id, opponent_competition_id, opponent_season_id,
        )))
        with self._lock:
            if key not in self._cache:
                target = self._resolver(target_provider, target_team_id, target_competition_id, target_season_id)
                opponent = self._resolver(opponent_provider, opponent_team_id, opponent_competition_id, opponent_season_id)
                self._cache[key] = compare_event_team_profiles(target, opponent)
            return self._cache[key]

    def _get_interactions(self, *identity):
        key = tuple(map(str, identity))
        with self._lock:
            if key not in self._interaction_cache:
                target = self._resolver(*identity[:4])
                opponent = self._resolver(*identity[4:])
                self._interaction_cache[key] = analyze_matchup_interactions(target, opponent)
            return self._interaction_cache[key]

    def _get_review_priorities(self, *identity):
        key = tuple(map(str, identity))
        with self._lock:
            if key not in self._review_cache:
                target = self._resolver(*identity[:4])
                opponent = self._resolver(*identity[4:])
                comparison = self._get(*identity)
                interactions = self._get_interactions(*identity)
                target_tendencies = generate_event_profile_findings(target).recurring_tendencies
                opponent_tendencies = generate_event_profile_findings(opponent).recurring_tendencies
                self._review_cache[key] = build_pre_match_review_priorities(
                    comparison,
                    interactions,
                    target_recurring_tendencies=target_tendencies,
                    opponent_recurring_tendencies=opponent_tendencies,
                )
            return self._review_cache[key]

    def summary(self, *identity):
        result = self._get(*identity)
        return json_safe({
            "schema_version": "v1", "comparison_type": "event_team_season",
            "target": result.target, "opponent": result.opponent,
            "compatibility": result.compatibility, "configuration": result.configuration,
            "compared_metric_count": len(result.metric_comparisons),
            "excluded_metric_count": len(result.excluded_metrics),
            "finding_count": len(result.findings),
        })

    def metrics(self, *identity):
        result = self._get(*identity)
        return json_safe({
            "schema_version": "v1",
            "metric_comparisons": result.metric_comparisons.to_dict("records"),
            "excluded_metrics": result.excluded_metrics.to_dict("records"),
        })

    def findings(self, *identity):
        result = self._get(*identity)
        return json_safe({
            "schema_version": "v1",
            "ranked_comparison_findings": [asdict(item) for item in result.findings],
        })

    def interactions(self, *identity):
        result = self._get_interactions(*identity)
        return json_safe({
            "schema_version": "v1", "team_a": result.team_a, "team_b": result.team_b,
            "compatibility": result.compatibility, "configuration": result.configuration,
            "directional_interactions": result.interactions.to_dict("records"),
            "excluded_interactions": result.excluded_interactions.to_dict("records"),
        })

    def interaction_findings(self, *identity):
        result = self._get_interactions(*identity)
        return json_safe({
            "schema_version": "v1",
            "ranked_interaction_findings": [asdict(item) for item in result.findings],
        })

    def review_priorities(self, *identity):
        result = self._get_review_priorities(*identity)
        return json_safe({
            "schema_version": "v1",
            "target": result.target,
            "opponent": result.opponent,
            "review_priorities": [asdict(item) for item in result.priorities],
            "candidate_audit": result.candidate_audit.to_dict("records"),
            "configuration": result.configuration,
        })

    def pre_match_briefing(self, *identity):
        """Return the compact deterministic briefing over the selected shortlist."""
        key = tuple(map(str, identity))
        with self._lock:
            if key not in self._briefing_cache:
                review = self._get_review_priorities(*identity)
                comparison = self._get(*identity)
                self._briefing_cache[key] = build_pre_match_briefing(
                    review, comparison, identity=tuple(identity),
                )
            briefing = self._briefing_cache[key]
        return json_safe({
            "schema_version": "v1",
            "briefing": asdict(briefing),
        })

    def _get_review_priority_moments(self, *identity, priority_id: str, limit: int = 8):
        key = (*tuple(map(str, identity)), str(priority_id), str(limit))
        with self._lock:
            if key not in self._moment_cache:
                review = self._get_review_priorities(*identity)
                priority = next((item for item in review.priorities if item.priority_id == priority_id), None)
                if priority is None:
                    raise KeyError(f"Unknown pre-match review priority {priority_id!r}.")
                if self._event_bundle_resolver is None:
                    return None
                target = self._resolver(*identity[:4])
                opponent = self._resolver(*identity[4:])
                self._moment_cache[key] = build_representative_match_moments(
                    priority, target, opponent, self._event_bundle_resolver, limit=limit,
                )
            return self._moment_cache[key]

    def review_priority_moments(self, *identity, priority_id: str, limit: int = 8):
        result = self._get_review_priority_moments(*identity, priority_id=priority_id, limit=limit)
        if result is None:
            return json_safe({
                "schema_version": "v1", "priority_id": priority_id,
                "supported": False, "representative_moments": [], "query_mappings": [],
                "moment_patterns": [], "moment_pattern_assignments": [], "pattern_context_summaries": [],
                "moment_sequence_features": [], "moment_sequence_patterns": [], "moment_sequence_similarities": [],
                "moment_sequence_limitations": [],
                "pattern_limitations": [],
                "limitations": ["No canonical event-bundle resolver is configured for representative moments."],
            })
        pattern_key = (*tuple(map(str, identity)), str(priority_id), str(limit))
        with self._lock:
            if pattern_key not in self._moment_sequence_detail_cache:
                all_details = {}
                if self._event_bundle_resolver is not None:
                    for moment in result.moments:
                        bundle = self._event_bundle_resolver(
                            str(moment.source_provenance["provider"]), int(moment.match_id),
                        )
                        detail = build_representative_moment_detail(moment, bundle)
                        all_details[moment.event_id] = detail
                        detail_key = (*tuple(map(str, identity)), str(priority_id), str(moment.event_id), str(limit))
                        self._moment_detail_cache[detail_key] = detail
                self._moment_sequence_detail_cache[pattern_key] = all_details
            all_details = self._moment_sequence_detail_cache[pattern_key]
            if pattern_key not in self._moment_pattern_cache:
                self._moment_pattern_cache[pattern_key] = build_moment_patterns(
                    result.priority_id, result.moments, details=all_details,
                )
            pattern_result = self._moment_pattern_cache[pattern_key]
            if pattern_key not in self._moment_context_cache:
                contexts = {
                    event_id: detail.moment_360_context for event_id, detail in all_details.items()
                }
                self._moment_context_cache[pattern_key] = contexts
            contexts = self._moment_context_cache[pattern_key]
            context_key = (*pattern_key, str(self._minimum_360_pattern_sample))
            if context_key not in self._pattern_context_cache:
                self._pattern_context_cache[context_key] = build_pattern_context_summaries(
                    pattern_result, result.moments, contexts,
                    minimum_360_sample=self._minimum_360_pattern_sample,
                )
            context_summaries = self._pattern_context_cache[context_key]
            if pattern_key not in self._moment_sequence_group_cache:
                self._moment_sequence_group_cache[pattern_key] = build_moment_sequence_grouping(
                    result.priority_id, result.moments, all_details,
                )
            sequence_result = self._moment_sequence_group_cache[pattern_key]
        context_by_pattern = {item.pattern_id: item for item in context_summaries}
        return json_safe({
            "schema_version": "v1", "priority_id": result.priority_id,
            "supported": result.supported,
            "representative_moments": [asdict(item) for item in result.moments],
            "moment_patterns": [
                {**asdict(item), "context_summary": asdict(context_by_pattern[item.pattern_id])}
                for item in pattern_result.patterns
            ],
            "moment_pattern_assignments": [asdict(item) for item in pattern_result.assignments],
            "pattern_context_summaries": [asdict(item) for item in context_summaries],
            "moment_sequence_features": [asdict(item) for item in sequence_result.features],
            "moment_sequence_patterns": [asdict(item) for item in sequence_result.patterns],
            "moment_sequence_similarities": [asdict(item) for item in sequence_result.similarities],
            "moment_sequence_limitations": sequence_result.limitations,
            "pattern_limitations": pattern_result.limitations,
            "query_mappings": result.query_mappings,
            "limitations": result.limitations,
        })

    def review_priority_moment_detail(self, *identity, priority_id: str, event_id: str, limit: int = 8):
        key = (*tuple(map(str, identity)), str(priority_id), str(event_id), str(limit))
        with self._lock:
            if key not in self._moment_detail_cache:
                moments = self._get_review_priority_moments(*identity, priority_id=priority_id, limit=limit)
                if moments is None or self._event_bundle_resolver is None:
                    return json_safe({
                        "schema_version": "v1", "priority_id": priority_id, "event_id": event_id,
                        "supported": False, "detail": None,
                        "limitations": ["No canonical event-bundle resolver is configured for representative moment detail."],
                    })
                matches = [moment for moment in moments.moments if moment.event_id == str(event_id)]
                if len(matches) != 1:
                    raise KeyError(f"Representative event {event_id!r} is absent or ambiguous for this priority.")
                moment = matches[0]
                bundle = self._event_bundle_resolver(str(moment.source_provenance["provider"]), int(moment.match_id))
                self._moment_detail_cache[key] = build_representative_moment_detail(moment, bundle)
            detail = self._moment_detail_cache[key]
        return json_safe({
            "schema_version": "v1", "priority_id": priority_id, "event_id": event_id,
            "supported": detail.sequence_supported, "detail": asdict(detail),
            "limitations": detail.limitations,
        })

    def review_priority_evidence_pack(self, *identity, priority_id: str, limit: int = 8):
        """Return one cached product pack without rerunning priority selection."""
        key = (*tuple(map(str, identity)), str(priority_id), str(limit))
        with self._lock:
            if key not in self._evidence_pack_cache:
                review = self._get_review_priorities(*identity)
                priority = next((item for item in review.priorities if item.priority_id == priority_id), None)
                if priority is None:
                    raise KeyError(f"Unknown pre-match review priority {priority_id!r}.")
                comparison = self._get(*identity)
                moments = self._get_review_priority_moments(*identity, priority_id=priority_id, limit=limit)
                pattern_result = sequence_result = None
                details = {}
                context_summaries = ()
                if moments is not None:
                    # Populate and reuse the existing moment, pattern, detail,
                    # sequence, and 360 caches. No priority is reselected here.
                    self.review_priority_moments(*identity, priority_id=priority_id, limit=limit)
                    pattern_key = key
                    pattern_result = self._moment_pattern_cache.get(pattern_key)
                    sequence_result = self._moment_sequence_group_cache.get(pattern_key)
                    details = self._moment_sequence_detail_cache.get(pattern_key, {})
                    context_key = (*pattern_key, str(self._minimum_360_pattern_sample))
                    context_summaries = self._pattern_context_cache.get(context_key, ())
                self._evidence_pack_cache[key] = build_pre_match_evidence_pack(
                    priority,
                    target_identity=review.target,
                    opponent_identity=review.opponent,
                    comparison_compatibility=comparison.compatibility,
                    moments=moments,
                    moment_patterns=pattern_result,
                    moment_sequences=sequence_result,
                    moment_details=details,
                    pattern_context_summaries=context_summaries,
                )
            pack = self._evidence_pack_cache[key]
        return json_safe({
            "schema_version": "v1",
            "priority_id": priority_id,
            "evidence_pack": asdict(pack),
        })
