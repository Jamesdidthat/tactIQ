"""Transparent multi-metric match archetypes from event-season deviations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from .event_profile_findings import EventProfileFindingResult, generate_event_profile_findings
from .event_team_profile import EventTeamSeasonProfile


ARCHETYPE_Z_THRESHOLD = 0.75
ARCHETYPE_MIN_MATCHES = 10
ARCHETYPE_MIN_COVERAGE = 0.80


@dataclass(frozen=True)
class ArchetypeCondition:
    metric: str
    direction: str


@dataclass(frozen=True)
class MatchArchetype:
    archetype_id: str
    match_id: str | int
    archetype: str
    title: str
    description: str
    rule_threshold: float
    rule_strength: float
    evidence_level: str
    contributing_metrics: tuple[dict, ...]


@dataclass
class MatchArchetypeResult:
    assignments: list[MatchArchetype]
    season_summary: pd.DataFrame
    rule_definitions: pd.DataFrame
    total_matches: int

    def __post_init__(self) -> None:
        identifiers = [item.archetype_id for item in self.assignments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Match archetype IDs must be unique.")
        required = {"archetype", "match_count", "match_share", "representative_match_ids"}
        if missing := required - set(self.season_summary.columns):
            raise ValueError(f"archetype season summary missing columns: {sorted(missing)}")


ARCHETYPE_RULES: dict[str, tuple[ArchetypeCondition, ...]] = {
    "high_possession_low_progression": (
        ArchetypeCondition("possession_share_estimate", "high"),
        ArchetypeCondition("progressive_passes_per90", "low"),
    ),
    "high_progression_high_chance_creation": (
        ArchetypeCondition("progressive_passes_per90", "high"),
        ArchetypeCondition("xg_per90", "high"),
    ),
    "low_possession_direct_attack": (
        ArchetypeCondition("possession_share_estimate", "low"),
        ArchetypeCondition("counter_attack_shots_per90", "high"),
    ),
    "high_regain_transition_pressure": (
        ArchetypeCondition("high_regains_per90", "high"),
        ArchetypeCondition("pressures_per90", "high"),
    ),
    "high_penalty_area_access_low_shot_output": (
        ArchetypeCondition("passes_into_penalty_area_per90", "high"),
        ArchetypeCondition("shots_per90", "low"),
    ),
    "high_shot_volume_low_xg_per_shot": (
        ArchetypeCondition("shots_per90", "high"),
        ArchetypeCondition("xg_per_shot", "low"),
    ),
}

ARCHETYPE_TEXT = {
    "high_possession_low_progression": ("High possession, lower progression", "The match combined above-baseline event-derived possession share with below-baseline progressive-pass volume."),
    "high_progression_high_chance_creation": ("High progression and chance creation", "The match combined above-baseline progressive-pass volume with above-baseline xG."),
    "low_possession_direct_attack": ("Lower possession with explicit counter attacks", "The match combined below-baseline event-derived possession share with above-baseline shots explicitly tagged From Counter."),
    "high_regain_transition_pressure": ("High-regain and pressure activity", "The match combined above-baseline high-regain frequency with above-baseline pressure volume."),
    "high_penalty_area_access_low_shot_output": ("High penalty-area access, lower shot output", "The match combined above-baseline completed passes into the penalty area with below-baseline shot volume."),
    "high_shot_volume_low_xg_per_shot": ("High shot volume, lower xG per shot", "The match combined above-baseline shot volume with below-baseline average xG per shot."),
}


def archetype_rule_definitions() -> pd.DataFrame:
    rows = []
    for name, conditions in ARCHETYPE_RULES.items():
        title, description = ARCHETYPE_TEXT[name]
        rows.append({
            "archetype": name, "title": title, "description": description,
            "conditions": tuple(asdict(condition) for condition in conditions),
            "absolute_z_threshold": ARCHETYPE_Z_THRESHOLD,
            "minimum_contributing_matches": ARCHETYPE_MIN_MATCHES,
            "minimum_coverage": ARCHETYPE_MIN_COVERAGE,
        })
    return pd.DataFrame(rows)


def _xg_per_shot_deviations(profile: EventTeamSeasonProfile) -> pd.DataFrame:
    matches = profile.match_metrics
    values = pd.to_numeric(matches.xg, errors="coerce").div(pd.to_numeric(matches.shots, errors="coerce").where(matches.shots.gt(0)))
    observed = values.dropna()
    baseline = float(observed.median()) if not observed.empty else float("nan")
    q25, q75 = observed.quantile(.25), observed.quantile(.75)
    scale = float((q75 - q25) / 1.349)
    method = "iqr_over_1.349"
    if not scale > 1e-12:
        scale = float((observed - baseline).abs().median() * 1.4826)
        method = "mad_times_1.4826" if scale > 1e-12 else "zero_season_dispersion"
    rows = []
    coverage = len(observed) / len(matches) if len(matches) else 0.0
    for index, value in values.items():
        if pd.isna(value):
            continue
        rows.append({
            "match_id": matches.loc[index, "match_id"], "metric": "xg_per_shot",
            "observed_value": float(value), "season_baseline": baseline,
            "signed_deviation": float(value - baseline), "absolute_deviation": abs(float(value - baseline)),
            "relative_deviation": float((value - baseline) / abs(baseline)) if abs(baseline) > 1e-12 else pd.NA,
            "robust_scale": scale, "robust_scale_method": method,
            "robust_z_score": float((value - baseline) / scale) if scale > 1e-12 else pd.NA,
            "contributing_match_count": len(observed), "coverage": coverage,
            "unit": "xG_per_shot", "definition": "Match xG divided by shots; missing when a team recorded no shots.",
        })
    return pd.DataFrame(rows)


def _condition_passes(row: pd.Series, direction: str) -> bool:
    signed_z = float(row.robust_z_score) * (1 if direction == "high" else -1)
    return signed_z >= ARCHETYPE_Z_THRESHOLD


def build_match_archetypes(
    profile_or_findings: EventTeamSeasonProfile | EventProfileFindingResult,
) -> MatchArchetypeResult:
    """Apply each transparent rule independently, allowing multiple matches."""
    finding_result = (
        profile_or_findings if isinstance(profile_or_findings, EventProfileFindingResult)
        else generate_event_profile_findings(profile_or_findings)
    )
    profile = finding_result.profile
    deviations = finding_result.deviations.copy()
    if "xg_per_shot" not in set(deviations.metric):
        deviations = pd.concat([deviations, _xg_per_shot_deviations(profile)], ignore_index=True)
    lookup = deviations.set_index(["match_id", "metric"])
    assignments = []
    for match_id in profile.match_metrics.match_id:
        for name, conditions in ARCHETYPE_RULES.items():
            components, signed_strengths, supported = [], [], True
            for condition in conditions:
                key = (match_id, condition.metric)
                if key not in lookup.index:
                    supported = False
                    break
                row = lookup.loc[key]
                if isinstance(row, pd.DataFrame):
                    raise ValueError(f"Duplicate deviation rows for {key}.")
                if (
                    row.contributing_match_count < ARCHETYPE_MIN_MATCHES
                    or row.coverage < ARCHETYPE_MIN_COVERAGE
                    or pd.isna(row.robust_z_score)
                    or not _condition_passes(row, condition.direction)
                ):
                    supported = False
                    break
                signed_strengths.append(float(row.robust_z_score) * (1 if condition.direction == "high" else -1))
                components.append({
                    "metric": condition.metric, "required_direction": condition.direction,
                    "observed_value": float(row.observed_value), "season_baseline": float(row.season_baseline),
                    "robust_z_score": float(row.robust_z_score),
                    "contributing_match_count": int(row.contributing_match_count),
                    "coverage": float(row.coverage), "unit": row.unit, "definition": row.definition,
                })
            if not supported:
                continue
            strength = min(signed_strengths)
            evidence = "strong" if strength >= 1.5 and min(item["contributing_match_count"] for item in components) >= 20 else "moderate" if strength >= 1.0 else "exploratory"
            title, description = ARCHETYPE_TEXT[name]
            assignments.append(MatchArchetype(
                archetype_id=f"archetype:{profile.team_id}:{profile.season_id}:{match_id}:{name}",
                match_id=match_id, archetype=name, title=title, description=description,
                rule_threshold=ARCHETYPE_Z_THRESHOLD, rule_strength=strength,
                evidence_level=evidence, contributing_metrics=tuple(components),
            ))
    assignments.sort(key=lambda item: (str(item.match_id), item.archetype))
    frame = pd.DataFrame([asdict(item) for item in assignments])
    summaries = []
    for name in ARCHETYPE_RULES:
        group = frame.loc[frame.archetype.eq(name)] if not frame.empty else frame
        ordered = group.sort_values(["rule_strength", "match_id"], ascending=[False, True], kind="stable") if not group.empty else group
        title, description = ARCHETYPE_TEXT[name]
        summaries.append({
            "archetype": name, "title": title, "description": description,
            "match_count": int(group.match_id.nunique()) if not group.empty else 0,
            "match_share": float(group.match_id.nunique() / len(profile.match_metrics)) if len(profile.match_metrics) else 0.0,
            "representative_match_ids": tuple(ordered.match_id.head(3)) if not group.empty else tuple(),
            "representative_rule_strengths": tuple(float(value) for value in ordered.rule_strength.head(3)) if not group.empty else tuple(),
        })
    summary = pd.DataFrame(summaries).sort_values(["match_count", "archetype"], ascending=[False, True], kind="stable").reset_index(drop=True)
    return MatchArchetypeResult(assignments, summary, archetype_rule_definitions(), len(profile.match_metrics))
