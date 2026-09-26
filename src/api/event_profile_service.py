"""Product-facing JSON service for event-based team-season profiles."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from threading import RLock
from typing import Callable

import pandas as pd

from src.analysis import (
    EventTeamSeasonProfile, assemble_match_story, build_match_archetypes,
    build_match_tactical_profile,
    build_football_style_profile, build_metric_relationship_deviations,
    build_representative_moment_detail, build_team_style_concept_moments,
    generate_event_profile_findings,
)
from src.analysis.event_profile_findings import FINDING_METRICS
from src.ai import MatchStoryExplanationService
from src.api.schemas import json_safe, serialize_match_story_explanation


EventProfileResolver = Callable[[str, str | int, str | int, str | int], EventTeamSeasonProfile]
EventBundleResolver = Callable[[str, int], object]


def load_event_profile_artifact(path: str | Path) -> EventTeamSeasonProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "tactiq.event-team-profile.v1":
        raise ValueError("Unsupported event team-profile artifact version.")
    return EventTeamSeasonProfile(
        team_id=payload["team"]["team_id"], team_name=payload["team"]["team_name"],
        competition_id=payload["competition"]["competition_id"],
        season_id=payload["season"]["season_id"],
        match_metrics=pd.DataFrame(payload["match_metrics"]),
        aggregate_metrics=pd.DataFrame(payload["aggregate_metrics"]),
        definitions=pd.DataFrame(payload["definitions"]),
        matches_excluded=pd.DataFrame(payload["matches_excluded"], columns=["match_id", "reason"]),
        competition_name=payload["competition"].get("competition_name"),
        season_name=payload["season"].get("season_name"),
    )


def _event_profile_artifact_index(directory: str | Path) -> dict[tuple[str, str, str, str], list[Path]]:
    root = Path(directory)
    index: dict[tuple[str, str, str, str], list[Path]] = {}
    for path in sorted(root.rglob("*event_profile_v1.json"), key=lambda item: item.as_posix()):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "tactiq.event-team-profile.v1":
            continue
        identity = (
            str(payload.get("provider")),
            str(payload.get("team", {}).get("team_id")),
            str(payload.get("competition", {}).get("competition_id")),
            str(payload.get("season", {}).get("season_id")),
        )
        index.setdefault(identity, []).append(path)
    return index


def _resolve_indexed_artifact(
    root: Path, identity: tuple[str, str, str, str], matches: list[Path],
) -> Path:
    provider, team_id, competition_id, season_id = identity
    if not matches:
        raise KeyError(f"Event profile not found for {provider}/{team_id}/{competition_id}/{season_id}.")
    if len(matches) > 1 and len({path.read_bytes() for path in matches}) > 1:
        relative = [str(path.relative_to(root)) for path in matches]
        raise ValueError(
            "Ambiguous event profile artifacts for "
            f"{provider}/{team_id}/{competition_id}/{season_id}: {relative}"
        )
    return matches[0]


def event_profile_artifact_catalog(directory: str | Path) -> dict:
    """Return deterministic human-readable identities for valid profiles."""
    root = Path(directory)
    index = _event_profile_artifact_index(root)
    profiles, excluded = [], []
    for identity, matches in sorted(index.items()):
        try:
            path = _resolve_indexed_artifact(root, identity, matches)
        except ValueError as error:
            excluded.append({"identity": list(identity), "reason": str(error)})
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        profiles.append({
            "provider": identity[0],
            "team_id": payload["team"]["team_id"],
            "team_name": payload["team"]["team_name"],
            "competition_id": payload["competition"]["competition_id"],
            "competition_name": payload["competition"].get("competition_name"),
            "season_id": payload["season"]["season_id"],
            "season_name": payload["season"].get("season_name"),
            "analysed_match_count": len(payload.get("match_metrics", [])),
        })
    profiles.sort(key=lambda item: (
        str(item["competition_name"] or item["competition_id"]),
        str(item["season_name"] or item["season_id"]),
        str(item["team_name"]), str(item["team_id"]),
    ))
    return {"schema_version": "v1", "profiles": profiles, "excluded": excluded}


def artifact_event_profile_resolver(directory: str | Path) -> EventProfileResolver:
    root = Path(directory)
    # Index once; EventProfileService's result cache behavior remains unchanged.
    index = _event_profile_artifact_index(root)

    def resolve(provider: str, team_id: str | int, competition_id: str | int, season_id: str | int) -> EventTeamSeasonProfile:
        requested = tuple(map(str, (provider, team_id, competition_id, season_id)))
        path = _resolve_indexed_artifact(root, requested, index.get(requested, []))
        return load_event_profile_artifact(path)

    return resolve


class EventProfileService:
    def __init__(
        self, resolver: EventProfileResolver,
        story_explanation_service: MatchStoryExplanationService | None = None,
        event_bundle_resolver: EventBundleResolver | None = None,
    ) -> None:
        self._resolver, self._cache, self._lock = resolver, {}, RLock()
        self._story_explanation_service = story_explanation_service or MatchStoryExplanationService()
        self._event_bundle_resolver = event_bundle_resolver
        self._tactical_cache: dict[tuple[str, ...], dict] = {}
        self._style_visual_cache: dict[tuple[str, ...], dict] = {}

    def _get(self, provider, team_id, competition_id, season_id):
        key = tuple(map(str, (provider, team_id, competition_id, season_id)))
        with self._lock:
            if key not in self._cache:
                profile = self._resolver(provider, team_id, competition_id, season_id)
                self._cache[key] = generate_event_profile_findings(profile)
            return self._cache[key]

    def summary(self, provider, team_id, competition_id, season_id):
        result = self._get(provider, team_id, competition_id, season_id)
        profile = result.profile
        return json_safe({
            "schema_version": "v1", "profile_type": "event_team_season",
            "team": {"team_id": profile.team_id, "name": profile.team_name},
            "provider": provider, "competition_id": profile.competition_id,
            "competition_name": profile.competition_name,
            "season_id": profile.season_id, "season_name": profile.season_name,
            "analysed_match_count": len(profile.match_metrics),
            "excluded_match_count": len(profile.matches_excluded),
            "coordinate_system": "statsbomb_120x80",
            "capabilities": {"has_events": True, "has_lineups": True, "has_continuous_tracking": False},
            "finding_count": len(result.findings),
        })

    def baselines(self, provider, team_id, competition_id, season_id):
        result = self._get(provider, team_id, competition_id, season_id)
        rows = result.profile.aggregate_metrics.loc[result.profile.aggregate_metrics.metric.isin(FINDING_METRICS)]
        return json_safe({"schema_version": "v1", "season_baselines": rows.to_dict("records")})

    def football_style(self, provider, team_id, competition_id, season_id, recent_window=5):
        """Return football-first language while preserving structured evidence."""
        profile = self._get(provider, team_id, competition_id, season_id).profile
        result = build_football_style_profile(profile, recent_window=int(recent_window))
        return json_safe(asdict(result))

    def style_concept_moments(
        self, provider, team_id, competition_id, season_id, concept_id, *, limit=6,
    ):
        """Return real event sequences illustrating one existing style concept."""
        key = tuple(map(str, (provider, team_id, competition_id, season_id, concept_id, limit)))
        with self._lock:
            if key in self._style_visual_cache:
                return self._style_visual_cache[key]
            if self._event_bundle_resolver is None:
                payload = {
                    "schema_version": "v1", "concept_id": concept_id, "supported": False,
                    "representative_moments": [], "representative_moment_details": [],
                    "query_mappings": [],
                    "limitations": ["Canonical event loading is not configured for visual examples."],
                }
                self._style_visual_cache[key] = payload
                return payload
            profile = self._get(provider, team_id, competition_id, season_id).profile
            style = build_football_style_profile(profile)
            concepts = (
                *style.in_possession, *style.out_of_possession, *style.transitions,
                *style.strengths, *style.potential_weaknesses, *style.recent_style,
            )
            matches = [concept for concept in concepts if concept.concept_id == str(concept_id)]
            if len(matches) != 1:
                raise KeyError(f"Unknown or ambiguous football-style concept {concept_id!r}.")
            concept = matches[0]
            metrics = tuple(item.metric for item in concept.supporting_evidence)
            result = build_team_style_concept_moments(
                concept.concept_id, metrics, profile, self._event_bundle_resolver, limit=int(limit),
            )
            details = []
            for moment in result.moments:
                bundle = self._event_bundle_resolver(
                    str(moment.source_provenance["provider"]), int(moment.match_id),
                )
                details.append(build_representative_moment_detail(moment, bundle))
            payload = json_safe({
                "schema_version": "v1", "concept_id": concept.concept_id,
                "concept_title": concept.title, "supported": result.supported,
                "representative_moments": [asdict(item) for item in result.moments],
                "representative_moment_details": [asdict(item) for item in details],
                "query_mappings": result.query_mappings,
                "limitations": result.limitations,
                "suppressed_duplicates": result.suppressed_duplicates,
            })
            self._style_visual_cache[key] = payload
            return payload

    def findings(self, provider, team_id, competition_id, season_id):
        result = self._get(provider, team_id, competition_id, season_id)
        return json_safe({
            "schema_version": "v1", "findings": [asdict(finding) for finding in result.findings],
            "suppressed_duplicate_count": len(result.suppressed_duplicates),
        })

    def tendencies(self, provider, team_id, competition_id, season_id):
        result = self._get(provider, team_id, competition_id, season_id)
        return json_safe({"schema_version": "v1", "recurring_event_profile_tendencies": result.recurring_tendencies.to_dict("records")})

    def unusual_matches(self, provider, team_id, competition_id, season_id):
        result = self._get(provider, team_id, competition_id, season_id)
        deviations = result.deviations.loc[result.deviations.metric.isin(FINDING_METRICS)].copy()
        deviations["absolute_robust_z"] = deviations.robust_z_score.abs()
        ranked = []
        for match_id, group in deviations.groupby("match_id", sort=False):
            valid = group.dropna(subset=["absolute_robust_z"])
            if valid.empty:
                continue
            strongest = valid.sort_values(["absolute_robust_z", "metric"], ascending=[False, True], kind="stable").iloc[0]
            ranked.append({
                "match_id": match_id, "match_date": strongest.get("match_date"),
                "strongest_metric": strongest.metric,
                "strongest_robust_z": strongest.robust_z_score,
                "absolute_robust_z": strongest.absolute_robust_z,
                "observed_value": strongest.observed_value,
                "season_baseline": strongest.season_baseline,
                "unit": strongest.unit,
                "meaningful_finding_count": sum(finding.source_match_id == match_id for finding in result.findings),
                "match_analysis_path": f"/?match={match_id}",
            })
        ranked.sort(key=lambda row: (-row["absolute_robust_z"], str(row["match_id"])))
        return json_safe({"schema_version": "v1", "unusual_matches": ranked})

    def archetypes(self, provider, team_id, competition_id, season_id):
        result = build_match_archetypes(self._get(provider, team_id, competition_id, season_id))
        return json_safe({
            "schema_version": "v1",
            "rule_definitions": result.rule_definitions.to_dict("records"),
            "season_summary": result.season_summary.to_dict("records"),
            "match_assignments": [asdict(item) for item in result.assignments],
            "total_matches": result.total_matches,
        })

    def relationships(self, provider, team_id, competition_id, season_id):
        finding_result = self._get(provider, team_id, competition_id, season_id)
        result = build_metric_relationship_deviations(finding_result.profile)
        return json_safe({
            "schema_version": "v1",
            "relationship_fits": result.relationship_fits.to_dict("records"),
            "match_deviations": result.match_deviations.to_dict("records"),
            "findings": [asdict(item) for item in result.findings],
            "total_matches": result.total_matches,
        })

    def matches(self, provider, team_id, competition_id, season_id):
        """Return the compact season match index used by the match-story picker."""
        profile = self._get(provider, team_id, competition_id, season_id).profile
        available = [
            "match_id", "match_date", "opponent_team_id", "opponent_team_name",
            "home_away", "team_score", "opponent_score", "match_minutes",
        ]
        columns = [column for column in available if column in profile.match_metrics.columns]
        matches = profile.match_metrics[columns].copy().sort_values(
            [column for column in ("match_date", "match_id") if column in columns],
            kind="stable",
        )
        for column in available:
            if column not in matches:
                matches[column] = None
        return json_safe({
            "schema_version": "v1",
            "matches": matches[available].to_dict("records"),
        })

    def match_story(self, provider, team_id, competition_id, season_id, match_id):
        result = self._assemble_story(provider, team_id, competition_id, season_id, match_id)
        return json_safe({
            "schema_version": "v1", "team_id": result.team_id,
            "team_name": result.team_name, "match_id": result.match_id,
            "maximum_story_points": result.maximum_story_points,
            "status": result.status, "message": result.message,
            "match_context": result.match_context,
            "presentation_mode": result.presentation_mode,
            "coherence_linkages": list(result.coherence_linkages),
            "story_points": [asdict(item) for item in result.story_points],
            "candidate_audit": result.candidate_audit.to_dict("records"),
        })

    def _assemble_story(self, provider, team_id, competition_id, season_id, match_id):
        return assemble_match_story(
            self._get(provider, team_id, competition_id, season_id),
            int(match_id) if str(match_id).isdigit() else match_id,
        )

    def match_story_explanation(self, provider, team_id, competition_id, season_id, match_id):
        story = self._assemble_story(provider, team_id, competition_id, season_id, match_id)
        return serialize_match_story_explanation(self._story_explanation_service.explain(story))

    def match_tactical_analysis(self, provider, team_id, competition_id, season_id, match_id):
        """Return both-team match context and goal investigations for one match."""
        key = tuple(map(str, (provider, team_id, competition_id, season_id, match_id)))
        with self._lock:
            if key in self._tactical_cache:
                return self._tactical_cache[key]
            if self._event_bundle_resolver is None:
                raise KeyError("Canonical event match loading is not configured.")
            target = self._get(provider, team_id, competition_id, season_id).profile
            match_rows = target.match_metrics.loc[target.match_metrics.match_id.astype(str).eq(str(match_id))]
            if len(match_rows) != 1:
                raise KeyError(f"Match {match_id!r} is absent from this team-season profile.")
            opponent_id = match_rows.iloc[0].opponent_team_id
            profiles = {target.team_id: target}
            try:
                opponent = self._resolver(provider, opponent_id, competition_id, season_id)
                profiles[opponent.team_id] = opponent
            except KeyError:
                pass
            bundle = self._event_bundle_resolver(provider, int(match_id))
            payload = json_safe(asdict(build_match_tactical_profile(bundle, event_team_profiles=profiles)))
            self._tactical_cache[key] = payload
            return payload
