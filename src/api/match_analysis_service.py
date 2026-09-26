"""Cached local service for product-facing deterministic match analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Callable, Mapping

from src.ai import TacticalExplanationService
from src.analysis import build_match_tactical_profile, prioritize_findings, run_match_analysis
from src.analysis.finding_prioritization import FindingPrioritizationResult
from src.analysis.tactical_findings import MatchAnalysisResult
from src.data import CanonicalMatchBundle

from .schemas import (
    json_safe,
    serialize_analysis_coverage,
    serialize_finding_detail,
    serialize_finding_explanation,
    serialize_match_summary,
    serialize_pitch_frame,
    serialize_pitch_clip,
    serialize_ranked_findings,
)


BundleResolver = Callable[[str | int], CanonicalMatchBundle] | Mapping[str | int, CanonicalMatchBundle]
TrackingProfileResolver = Callable[[str | int], object]


@dataclass
class _CachedAnalysis:
    bundle: CanonicalMatchBundle
    result: MatchAnalysisResult
    ranked: FindingPrioritizationResult


class MatchAnalysisService:
    """In-process deterministic analysis cache with stable JSON responses."""

    def __init__(
        self,
        bundle_resolver: BundleResolver | None = None,
        *,
        explanation_service: TacticalExplanationService | None = None,
        tracking_profile_resolver: TrackingProfileResolver | None = None,
    ) -> None:
        self._bundle_resolver = bundle_resolver
        self._explanations = explanation_service or TacticalExplanationService()
        self._tracking_profile_resolver = tracking_profile_resolver
        self._cache: dict[str, _CachedAnalysis] = {}
        # Identifier aliases avoid reloading a large provider bundle for every
        # detail/frame request after its first analysis.
        self._identifier_cache: dict[tuple[str, bool], _CachedAnalysis] = {}
        self._bundle_cache: dict[str, CanonicalMatchBundle] = {}
        self._cache_lock = RLock()

    @staticmethod
    def _cache_key(bundle: CanonicalMatchBundle, allow_assumed_roles: bool) -> str:
        return f"{bundle.provider}:{bundle.matches.match_id.iloc[0]}:assumed_roles={allow_assumed_roles}"

    def _resolve(self, bundle_or_match: CanonicalMatchBundle | str | int) -> CanonicalMatchBundle:
        if isinstance(bundle_or_match, CanonicalMatchBundle):
            return bundle_or_match
        if self._bundle_resolver is None:
            raise KeyError("A match identifier requires a configured bundle_resolver.")
        if isinstance(self._bundle_resolver, Mapping):
            return self._bundle_resolver[bundle_or_match]
        return self._bundle_resolver(bundle_or_match)

    def _resolve_cached(self, bundle_or_match: CanonicalMatchBundle | str | int) -> CanonicalMatchBundle:
        """Resolve and retain a bundle without running the analytical pipeline."""
        if isinstance(bundle_or_match, CanonicalMatchBundle):
            return bundle_or_match
        identifier = str(bundle_or_match)
        with self._cache_lock:
            analysed = self._identifier_cache.get((identifier, False))
            if analysed is not None:
                return analysed.bundle
            cached = self._bundle_cache.get(identifier)
            if cached is not None:
                return cached
            # Resolver calls load large tracking files. Keep this inside the
            # lock so concurrent frame cards cannot load the same match many times.
            bundle = self._resolve(bundle_or_match)
            self._bundle_cache[identifier] = bundle
            return bundle

    def _get(self, bundle_or_match: CanonicalMatchBundle | str | int, *, allow_assumed_roles: bool = False) -> _CachedAnalysis:
        if not isinstance(bundle_or_match, CanonicalMatchBundle):
            identifier_key = (str(bundle_or_match), allow_assumed_roles)
            with self._cache_lock:
                cached = self._identifier_cache.get(identifier_key)
                if cached is not None:
                    return cached

        bundle = self._resolve_cached(bundle_or_match)
        key = self._cache_key(bundle, allow_assumed_roles)
        # A detail/summary burst from the UI must not duplicate the expensive
        # first analysis before the cache is populated.
        with self._cache_lock:
            if key not in self._cache:
                result = run_match_analysis(bundle, allow_assumed_roles=allow_assumed_roles)
                # The product endpoint exposes up to ten deterministically ordered
                # findings; shorter lists remain valid when suppression/coverage
                # leaves fewer distinct observations.
                self._cache[key] = _CachedAnalysis(bundle, result, prioritize_findings(result, shortlist_size=10))
            cached = self._cache[key]
            if not isinstance(bundle_or_match, CanonicalMatchBundle):
                self._identifier_cache[(str(bundle_or_match), allow_assumed_roles)] = cached
            return cached

    def get_match_summary(self, bundle_or_match: CanonicalMatchBundle | str | int, *, allow_assumed_roles: bool = False) -> dict:
        cached = self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles)
        return serialize_match_summary(cached.bundle, cached.result, cached.ranked)

    def get_ranked_findings(self, bundle_or_match: CanonicalMatchBundle | str | int, *, allow_assumed_roles: bool = False) -> dict:
        cached = self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles)
        return serialize_ranked_findings(cached.result, cached.ranked)

    def get_analysis_coverage(self, bundle_or_match: CanonicalMatchBundle | str | int, *, allow_assumed_roles: bool = False) -> dict:
        return serialize_analysis_coverage(self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles).result)

    def get_finding_detail(self, bundle_or_match: CanonicalMatchBundle | str | int, finding_id: str, *, allow_assumed_roles: bool = False) -> dict:
        cached = self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles)
        finding = next((item for item in cached.ranked.shortlist if item.finding_id == finding_id), None)
        pack = next((item for item in cached.ranked.evidence_packs if item.finding_id == finding_id), None)
        if finding is None or pack is None:
            raise KeyError(f"Finding {finding_id!r} is not in the ranked shortlist.")
        return serialize_finding_detail(finding, pack, cached.ranked.shortlist.index(finding) + 1, cached.ranked.selection_reasons.get(finding_id))

    def get_finding_explanation(self, bundle_or_match: CanonicalMatchBundle | str | int, finding_id: str, *, allow_assumed_roles: bool = False) -> dict:
        """Explain one shortlisted finding from its EvidencePack only."""
        cached = self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles)
        finding = next((item for item in cached.ranked.shortlist if item.finding_id == finding_id), None)
        pack = next((item for item in cached.ranked.evidence_packs if item.finding_id == finding_id), None)
        if finding is None or pack is None:
            raise KeyError(f"Finding {finding_id!r} is not in the ranked shortlist.")
        return serialize_finding_explanation(self._explanations.explain(finding, pack))

    def get_representative_pitch_frame(self, bundle_or_match: CanonicalMatchBundle | str | int, finding_id: str, *, moment_index: int = 0, allow_assumed_roles: bool = False) -> dict:
        detail = self.get_finding_detail(bundle_or_match, finding_id, allow_assumed_roles=allow_assumed_roles)
        moments = detail["evidence"]["representative_moments"]
        if moment_index < 0 or moment_index >= len(moments):
            raise KeyError("Requested representative moment is unavailable.")
        moment = moments[moment_index]
        if "frame" not in moment or "period" not in moment:
            raise KeyError("Representative evidence has no frame/period reference.")
        cached = self._get(bundle_or_match, allow_assumed_roles=allow_assumed_roles)
        return serialize_pitch_frame(cached.bundle, frame=int(moment["frame"]), period=int(moment["period"]))

    def get_pitch_frame(self, bundle_or_match: CanonicalMatchBundle | str | int, frame: int, period: int, *, allow_assumed_roles: bool = False) -> dict:
        """Return one observed canonical frame without inventing a finding."""
        bundle = self._resolve_cached(bundle_or_match)
        return serialize_pitch_frame(bundle, frame=int(frame), period=int(period))

    def get_pitch_clip(
        self,
        bundle_or_match: CanonicalMatchBundle | str | int,
        centre_frame: int,
        period: int,
        *,
        before_frames: int = 25,
        after_frames: int = 25,
        step: int = 1,
        before_seconds: float | None = None,
        after_seconds: float | None = None,
    ) -> dict:
        """Return real canonical tracking around one representative frame."""
        bundle = self._resolve_cached(bundle_or_match)
        return serialize_pitch_clip(
            bundle,
            centre_frame=int(centre_frame),
            period=int(period),
            before_frames=int(before_frames),
            after_frames=int(after_frames),
            step=int(step),
            before_seconds=before_seconds,
            after_seconds=after_seconds,
        )

    def get_tactical_analysis(self, bundle_or_match: CanonicalMatchBundle | str | int) -> dict:
        """Assess both teams using only capabilities present in this match bundle."""
        bundle = self._resolve_cached(bundle_or_match)
        profiles = {}
        if self._tracking_profile_resolver is not None:
            for team_id in bundle.teams.team_id:
                try:
                    profiles[team_id] = self._tracking_profile_resolver(team_id)
                except (KeyError, ValueError):
                    continue
        return json_safe(asdict(build_match_tactical_profile(bundle, tracking_team_profiles=profiles)))

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()
            self._identifier_cache.clear()
            self._bundle_cache.clear()
