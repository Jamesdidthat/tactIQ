"""Versioned, provider-neutral precomputation for compact Team Profiles."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import re
from typing import Callable, Iterable

import pandas as pd

from src.data import CanonicalMatchBundle, ProviderCapabilities

from .team_profile import TeamProfileIdentity, TeamProfileResult, build_team_profile


TEAM_PROFILE_CACHE_SCHEMA_VERSION = "tactiq.team-profile-cache.v1"
TEAM_PROFILE_VERSION = "team-profile.v4-football-shape-height"

_TABLE_FIELDS = (
    "matches_included", "matches_excluded", "capability_coverage", "sample_periods",
    "match_level_values", "aggregate_patterns", "match_deviations",
    "recurring_finding_families",
)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is pd.NA or value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _table_payload(frame: pd.DataFrame) -> dict:
    return {
        "columns": list(frame.columns),
        "records": _json_safe(frame.to_dict("records")),
    }


def _table_from_payload(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload.get("records", []), columns=payload.get("columns", []))


def profile_artifact(
    result: TeamProfileResult,
    *,
    provider: str,
    match_capabilities: dict[str, ProviderCapabilities] | None = None,
) -> dict:
    """Serialize compact match-level inputs and reconstructed profile outputs."""
    capabilities = match_capabilities or {}
    match_records = []
    for included in result.matches_included.to_dict("records"):
        match_id = included["match_id"]
        match_key = str(match_id)
        periods = result.sample_periods.loc[result.sample_periods.match_id.eq(match_id)]
        metrics = result.match_level_values.loc[result.match_level_values.match_id.eq(match_id)]
        family_rows = []
        for family in result.recurring_finding_families.to_dict("records"):
            if match_id in set(family.get("match_ids") or ()):
                family_rows.append(family["finding_family"])
        match_records.append({
            "provider": provider,
            "match_id": match_id,
            "team_id": included["provider_team_id"],
            "capabilities": asdict(capabilities[match_key]) if match_key in capabilities else {},
            "sample_duration": _json_safe(periods.to_dict("records")),
            "profile_metrics": _json_safe(metrics.to_dict("records")),
            "recurring_finding_families": sorted(family_rows),
        })
    return _json_safe({
        "schema_version": TEAM_PROFILE_CACHE_SCHEMA_VERSION,
        "profile_version": TEAM_PROFILE_VERSION,
        "provider": provider,
        "team": {
            "team_id": result.team_identity.team_id,
            "team_name": result.team_identity.team_name,
            "provider_team_ids": dict(result.team_identity.provider_team_ids),
        },
        "matches": match_records,
        "exclusions": result.matches_excluded.to_dict("records"),
        "tables": {name: _table_payload(getattr(result, name)) for name in _TABLE_FIELDS},
    })


def reconstruct_team_profile(artifact: dict) -> TeamProfileResult:
    """Reconstruct a TeamProfileResult without provider tracking data."""
    team = artifact["team"]
    identity = TeamProfileIdentity(
        team["team_id"], team["team_name"], team["provider_team_ids"]
    )
    tables = artifact["tables"]
    return TeamProfileResult(identity, *[_table_from_payload(tables[name]) for name in _TABLE_FIELDS])


class TeamProfileArtifactStore:
    """Read and atomically write deterministic, version-validated profile JSON."""

    def __init__(
        self,
        root: str | Path,
        *,
        schema_version: str = TEAM_PROFILE_CACHE_SCHEMA_VERSION,
        profile_version: str = TEAM_PROFILE_VERSION,
    ) -> None:
        self.root = Path(root)
        self.schema_version = schema_version
        self.profile_version = profile_version

    @staticmethod
    def _component(value: str | int) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))

    def path_for(self, provider: str, team_id: str | int) -> Path:
        return self.root / self._component(provider) / f"team_{self._component(team_id)}.json"

    def load(self, provider: str, team_id: str | int) -> TeamProfileResult | None:
        path = self.path_for(provider, team_id)
        if not path.is_file():
            return None
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
            if artifact.get("schema_version") != self.schema_version:
                return None
            if artifact.get("profile_version") != self.profile_version:
                return None
            if artifact.get("provider") != provider:
                return None
            if str(artifact.get("team", {}).get("team_id")) != str(team_id):
                return None
            return reconstruct_team_profile(artifact)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(
        self,
        result: TeamProfileResult,
        *,
        provider: str,
        match_capabilities: dict[str, ProviderCapabilities] | None = None,
    ) -> Path:
        path = self.path_for(provider, result.team_identity.team_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = profile_artifact(
            result, provider=provider, match_capabilities=match_capabilities
        )
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        temporary = path.with_suffix(".tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(path)
        return path


TeamResolver = Callable[[str | int], tuple]


def precompute_team_profile(
    provider: str,
    team_id: str | int,
    resolver: TeamResolver,
    store: TeamProfileArtifactStore,
) -> tuple[TeamProfileResult, Path]:
    """Discover, preflight through the provider resolver, and process sequentially."""
    resolved = resolver(team_id)
    identity, bundles = resolved[:2]
    preexcluded = resolved[2] if len(resolved) > 2 else ()
    capabilities: dict[str, ProviderCapabilities] = {}

    def sequential_bundles() -> Iterable[CanonicalMatchBundle]:
        for bundle in bundles:
            if bundle.provider != provider:
                raise ValueError(
                    f"Resolver returned provider {bundle.provider!r}; expected {provider!r}."
                )
            match_id = bundle.matches.match_id.iloc[0]
            capabilities[str(match_id)] = bundle.capabilities
            yield bundle

    result = build_team_profile(
        sequential_bundles(), identity, preexcluded_matches=preexcluded
    )
    return result, store.save(
        result, provider=provider, match_capabilities=capabilities
    )
