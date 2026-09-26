"""Cached product service and JSON views for multi-match Team Profiles."""
from __future__ import annotations

from dataclasses import asdict
import json
from threading import RLock
from typing import Callable, Iterable

import pandas as pd

from src.analysis import (
    TeamProfileIdentity, TeamProfileResult, build_football_shape_profile,
    build_team_profile,
)
from src.analysis.team_profile_cache import TeamProfileArtifactStore
from src.analysis.team_profile import profile_baseline_label, profile_evidence_band
from src.api.schemas import json_safe
from src.data import CanonicalMatchBundle

TeamResolver = Callable[[str | int], tuple]


def _metric_unit(metric_family: str) -> str:
    return "count" if metric_family == "shot_counts" else "metres"


def _provider_label(provider: str) -> str:
    return {"skillcorner_open_data": "SkillCorner", "metrica": "Metrica Sports"}.get(provider, provider.replace("_", " ").title())


def _profile_rows(frame: pd.DataFrame) -> list[dict]:
    records = frame.to_dict("records")
    for row in records:
        row["unit"] = _metric_unit(row["metric_family"])
        row["provider_label"] = _provider_label(row["provider"])
        required = str(row.get("required_capabilities") or "")
        row["provenance_label"] = (
            "Full tactical context"
            if "has_tactical_phases" in required or "has_attacking_direction" in required
            else "Tracking context" if "has_continuous_tracking" in required
            else "Event context" if "has_events" in required
            else "Provider data"
        )
    return records


class TeamProfileService:
    def __init__(
        self,
        resolver: TeamResolver,
        *,
        artifact_store: TeamProfileArtifactStore | None = None,
        provider: str | None = None,
    ) -> None:
        self._resolver, self._cache, self._lock = resolver, {}, RLock()
        self._artifact_store, self._provider = artifact_store, provider

    def _get(self, team_id: str | int) -> TeamProfileResult:
        key = str(team_id)
        with self._lock:
            if key not in self._cache:
                if self._artifact_store is not None and self._provider is not None:
                    precomputed = self._artifact_store.load(self._provider, team_id)
                    if precomputed is not None:
                        self._cache[key] = precomputed
                        return precomputed
                resolved = self._resolver(team_id)
                identity, bundles = resolved[:2]
                preexcluded = resolved[2] if len(resolved) > 2 else ()
                self._cache[key] = build_team_profile(
                    bundles, identity, preexcluded_matches=preexcluded
                )
            return self._cache[key]

    def summary(self, team_id):
        result = self._get(team_id)
        match_count = len(result.matches_included)
        return json_safe({"schema_version": "v1", "team": {"team_id": result.team_identity.team_id, "name": result.team_identity.team_name, "provider_team_ids": result.team_identity.provider_team_ids}, "analysed_match_count": match_count, "excluded_match_count": len(result.matches_excluded), "profile_evidence_band": profile_evidence_band(match_count), "profile_baseline_label": profile_baseline_label(match_count), "providers": sorted(result.matches_included.provider.unique()), "capability_coverage": result.capability_coverage.to_dict("records"), "sample_periods": result.sample_periods.to_dict("records")})

    def get_result(self, team_id) -> TeamProfileResult:
        """Return the cached validated result for in-process analysis composition."""
        return self._get(team_id)

    def metrics(self, team_id):
        return json_safe({"schema_version": "v1", "metric_baselines": _profile_rows(self._get(team_id).aggregate_patterns)})

    def finding_families(self, team_id):
        return json_safe({"schema_version": "v1", "recurring_finding_families": self._get(team_id).recurring_finding_families.to_dict("records")})

    def matches(self, team_id):
        result = self._get(team_id)
        return json_safe({"schema_version": "v1", "included_matches": result.matches_included.to_dict("records"), "excluded_matches": result.matches_excluded.to_dict("records")})

    def deviations(self, team_id):
        rows = self._get(team_id).match_deviations.copy()
        rows["absolute_deviation"] = rows.deviation_from_baseline.abs()
        rows = rows.sort_values(["absolute_deviation", "match_id", "metric"], ascending=[False, True, True], kind="stable")
        records = rows.to_dict("records")
        for row in records:
            finding_id = row.get("evidence_finding_id")
            has_evidence = finding_id is not None and not pd.isna(finding_id) and str(finding_id).strip() != ""
            row["evidence_finding_id"] = finding_id if has_evidence else None
            row["match_analysis_path"] = f"/?match={row['match_id']}" + (f"&finding={finding_id}" if has_evidence else "")
            row["link_label"] = "View evidence" if has_evidence else "View match"
            row["unit"] = _metric_unit(row["metric_family"])
            row["provider_label"] = _provider_label(row["provider"])
            required = str(row.get("required_capabilities") or "")
            row["provenance_label"] = "Full tactical context" if "has_tactical_phases" in required or "has_attacking_direction" in required else "Tracking context"
        return json_safe({"schema_version": "v1", "match_deviations": records})

    def shape_style(self, team_id):
        """Return football-first concepts derived exclusively from tracking evidence."""
        return json_safe(asdict(build_football_shape_profile(self._get(team_id))))

    def catalog(self):
        """List valid precomputed tracking profiles for product navigation."""
        if self._artifact_store is None:
            return {"schema_version": "v1", "profiles": []}
        profiles = []
        for path in sorted(self._artifact_store.root.rglob("team_*.json")):
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
                if artifact.get("schema_version") != self._artifact_store.schema_version:
                    continue
                if artifact.get("profile_version") != self._artifact_store.profile_version:
                    continue
                team = artifact["team"]
                matches = artifact.get("matches", [])
                has_tracking = any(
                    item.get("capabilities", {}).get("has_continuous_tracking", False)
                    for item in matches
                )
                profiles.append({
                    "provider": artifact["provider"],
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "analysed_match_count": len(matches),
                    "excluded_match_count": len(artifact.get("exclusions", [])),
                    "has_continuous_tracking": has_tracking,
                })
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        profiles.sort(key=lambda item: (str(item["team_name"]), str(item["team_id"])))
        return json_safe({"schema_version": "v1", "profiles": profiles})
