"""Directional, deterministic attack-versus-defence season interactions."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from .event_team_profile import EventTeamSeasonProfile
from .opponent_comparison import (
    MATERIAL_IQR_OVERLAP, MIN_CONTRIBUTING_MATCHES, MIN_COVERAGE,
    _distribution, _iqr_overlap, _metric_definition, _metric_series,
    compare_event_team_profiles,
)


MIN_INTERACTION_STANDARDIZED_MISMATCH = 1.0

INTERACTION_SPECS = (
    {
        "interaction_family": "penalty_area_access",
        "production_metric": "passes_into_penalty_area_per90",
        "exposure_metric": "passes_into_penalty_area_conceded_per90",
        "interaction_label": "penalty-area pass entries",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "comparability_basis": "The exposure metric is the exact opposition mirror of the production metric.",
    },
    {
        "interaction_family": "shot_volume",
        "production_metric": "shots_per90", "exposure_metric": "shots_conceded_per90",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "interaction_label": "shots", "comparability_basis": "The exposure metric is the exact opposition mirror of the production metric.",
    },
    {
        "interaction_family": "xg_production",
        "production_metric": "xg_per90", "exposure_metric": "xg_conceded_per90",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "interaction_label": "xG", "comparability_basis": "The exposure metric is the exact opposition mirror of the production metric.",
    },
    {
        "interaction_family": "shot_quality",
        "production_metric": "xg_per_shot", "exposure_metric": "xg_per_shot_conceded",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "interaction_label": "xG per shot", "comparability_basis": "Both metrics use StatsBomb xG divided by shots in the same match-level unit.",
    },
    {
        "interaction_family": "high_regain_turnover_exposure",
        "production_metric": "high_regains_per90", "exposure_metric": "turnovers_leading_to_shot_per90",
        "review_priority_compatibility": "unsupported_cross_metric",
        "interaction_label": "high-regain activity and turnover-to-shot exposure",
        "comparability_basis": "Explicit cross-metric context requested by the interaction taxonomy; both are match-level event counts per 90 but represent different event concepts.",
    },
    {
        "interaction_family": "explicit_counter_attack_shots",
        "production_metric": "counter_attack_shots_per90", "exposure_metric": "counter_attack_shots_conceded_per90",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "interaction_label": "explicit counter-attack shots", "comparability_basis": "Both metrics use the same explicit StatsBomb From Counter shot tag.",
    },
    {
        "interaction_family": "set_play_shots",
        "production_metric": "set_play_shots_per90", "exposure_metric": "set_play_shots_conceded_per90",
        "review_priority_compatibility": "direct_attack_vs_defence_counterpart",
        "interaction_label": "set-play shots", "comparability_basis": "Both metrics use the same explicit set-play shot classification.",
    },
)


@dataclass(frozen=True)
class MatchupInteractionFinding:
    finding_id: str
    rank_within_direction: int
    direction_id: str
    attacking_team_id: str | int
    attacking_team_name: str
    defending_team_id: str | int
    defending_team_name: str
    interaction_family: str
    production_metric: str
    exposure_metric: str
    review_priority_compatibility: str
    title: str
    description: str
    attacking_median: float
    defending_exposure_median: float
    signed_mismatch: float
    combined_standardized_mismatch: float
    interaction_strength_score: float
    evidence_basis: str
    attacking_contributing_matches: int
    defending_contributing_matches: int
    attacking_coverage: float
    defending_coverage: float
    unit: str
    limitations: tuple[str, ...]


@dataclass
class MatchupInteractionResult:
    team_a: dict
    team_b: dict
    compatibility: dict
    interactions: pd.DataFrame
    findings: list[MatchupInteractionFinding]
    excluded_interactions: pd.DataFrame
    configuration: dict

    def __post_init__(self) -> None:
        required = {
            "direction_id", "attacking_team_id", "defending_team_id", "interaction_family",
            "attacking_median", "defending_exposure_median", "signed_mismatch",
            "combined_standardized_mismatch", "distributions_materially_overlap",
            "interaction_strength_score",
        }
        if missing := required - set(self.interactions.columns):
            raise ValueError(f"Matchup interactions missing columns: {sorted(missing)}")
        if self.interactions.duplicated(["direction_id", "interaction_family"]).any():
            raise ValueError("Each directional interaction family must be unique.")


def _interaction_title(row: pd.Series) -> str:
    attack, defence = row.attacking_team_name, row.defending_team_name
    relation = "more" if row.signed_mismatch > 0 else "fewer"
    if row.interaction_family == "penalty_area_access":
        return f"{attack} typically generates {relation} penalty-area entries than {defence} typically concedes"
    if row.interaction_family == "high_regain_turnover_exposure":
        return f"{attack}'s high-regain activity is typically {'higher' if row.signed_mismatch > 0 else 'lower'} than {defence}'s turnover-to-shot exposure count"
    return f"{attack} typically generates {relation} {row.interaction_label} than {defence} typically concedes"


def _direction_rows(attacking: EventTeamSeasonProfile, defending: EventTeamSeasonProfile) -> tuple[list[dict], list[dict]]:
    rows, excluded = [], []
    direction_id = f"{attacking.team_id}_attack_vs_{defending.team_id}_defence"
    for spec in INTERACTION_SPECS:
        try:
            production_unit, production_definition = _metric_definition(attacking, spec["production_metric"])
            exposure_unit, exposure_definition = _metric_definition(defending, spec["exposure_metric"])
            if production_unit != exposure_unit:
                raise ValueError(f"units differ: {production_unit} vs {exposure_unit}")
            attack = _distribution(_metric_series(attacking, spec["production_metric"]), len(attacking.match_metrics))
            defence = _distribution(_metric_series(defending, spec["exposure_metric"]), len(defending.match_metrics))
            failures = []
            if attack["contributing_matches"] < MIN_CONTRIBUTING_MATCHES:
                failures.append(f"attacking production has fewer than {MIN_CONTRIBUTING_MATCHES} matches")
            if defence["contributing_matches"] < MIN_CONTRIBUTING_MATCHES:
                failures.append(f"defensive exposure has fewer than {MIN_CONTRIBUTING_MATCHES} matches")
            if attack["coverage"] < MIN_COVERAGE:
                failures.append(f"attacking production coverage is below {MIN_COVERAGE:.0%}")
            if defence["coverage"] < MIN_COVERAGE:
                failures.append(f"defensive exposure coverage is below {MIN_COVERAGE:.0%}")
            if failures:
                raise ValueError("; ".join(failures))
            review_compatibility = spec["review_priority_compatibility"]
            if review_compatibility == "unsupported_cross_metric":
                mismatch = absolute_mismatch = standardized = attack_standardized = defence_standardized = float("nan")
                overlap_ratio, material_overlap, strength = None, False, None
            else:
                mismatch = attack["median"] - defence["median"]
                absolute_mismatch = abs(mismatch)
                scales = (attack["robust_scale"], defence["robust_scale"])
                combined_scale = math.sqrt(sum(scale * scale for scale in scales) / 2) if all(pd.notna(scale) and scale > 1e-12 for scale in scales) else float("nan")
                standardized = mismatch / combined_scale if pd.notna(combined_scale) and combined_scale > 1e-12 else float("nan")
                attack_standardized = mismatch / attack["robust_scale"] if pd.notna(attack["robust_scale"]) and attack["robust_scale"] > 1e-12 else float("nan")
                defence_standardized = mismatch / defence["robust_scale"] if pd.notna(defence["robust_scale"]) and defence["robust_scale"] > 1e-12 else float("nan")
                overlap_ratio, material_overlap = _iqr_overlap(attack, defence)
                evidence_coverage = min(attack["coverage"], defence["coverage"])
                evidence_sample = min(attack["contributing_matches"], defence["contributing_matches"])
                effect_component = min(abs(standardized) / 3, 1.0) if pd.notna(standardized) else 0.0
                overlap_component = 1.0 - min(overlap_ratio, 1.0)
                strength = .50 * effect_component + .20 * evidence_coverage + .15 * min(evidence_sample / 20, 1.0) + .15 * overlap_component
            rows.append({
                "direction_id": direction_id,
                "attacking_team_id": attacking.team_id, "attacking_team_name": attacking.team_name,
                "defending_team_id": defending.team_id, "defending_team_name": defending.team_name,
                **spec, "unit": production_unit,
                "production_definition": production_definition, "exposure_definition": exposure_definition,
                "attacking_median": attack["median"], "attacking_q25": attack["q25"], "attacking_q75": attack["q75"],
                "attacking_contributing_matches": attack["contributing_matches"], "attacking_coverage": attack["coverage"],
                "attacking_robust_scale": attack["robust_scale"],
                "defending_exposure_median": defence["median"], "defending_exposure_q25": defence["q25"], "defending_exposure_q75": defence["q75"],
                "defending_contributing_matches": defence["contributing_matches"], "defending_coverage": defence["coverage"],
                "defending_robust_scale": defence["robust_scale"],
                "signed_mismatch": mismatch, "absolute_mismatch": absolute_mismatch,
                "standardized_by_attacking_variability": attack_standardized,
                "standardized_by_defending_variability": defence_standardized,
                "combined_standardized_mismatch": standardized,
                "iqr_overlap_ratio": overlap_ratio, "distributions_materially_overlap": material_overlap,
                "interaction_strength_score": strength,
                "mismatch_sign_convention": "attacking_production_minus_defending_exposure",
            })
        except (KeyError, ValueError) as error:
            excluded.append({
                "direction_id": direction_id, "attacking_team_id": attacking.team_id,
                "defending_team_id": defending.team_id,
                "interaction_family": spec["interaction_family"], "reason": str(error),
            })
    return rows, excluded


def analyze_matchup_interactions(
    team_a_profile: EventTeamSeasonProfile,
    team_b_profile: EventTeamSeasonProfile,
) -> MatchupInteractionResult:
    """Build both directional interaction sets after base-profile compatibility."""
    base = compare_event_team_profiles(team_a_profile, team_b_profile)
    a_rows, a_excluded = _direction_rows(team_a_profile, team_b_profile)
    b_rows, b_excluded = _direction_rows(team_b_profile, team_a_profile)
    interactions = pd.DataFrame([*a_rows, *b_rows])
    if interactions.empty:
        interactions = pd.DataFrame(columns=[
            "direction_id", "attacking_team_id", "defending_team_id", "interaction_family",
            "attacking_median", "defending_exposure_median", "signed_mismatch",
            "combined_standardized_mismatch", "distributions_materially_overlap",
            "interaction_strength_score",
        ])
    eligible = interactions.loc[
        interactions.combined_standardized_mismatch.notna()
        & interactions.combined_standardized_mismatch.abs().ge(MIN_INTERACTION_STANDARDIZED_MISMATCH)
        & ~interactions.distributions_materially_overlap
    ].sort_values(
        ["direction_id", "interaction_strength_score", "interaction_family"],
        ascending=[True, False, True], kind="stable",
    )
    findings: list[MatchupInteractionFinding] = []
    for direction_id, group in eligible.groupby("direction_id", sort=False):
        for rank, (_, row) in enumerate(group.iterrows(), start=1):
            minimum_matches = min(row.attacking_contributing_matches, row.defending_contributing_matches)
            minimum_coverage = min(row.attacking_coverage, row.defending_coverage)
            basis = "High" if minimum_matches >= 20 and minimum_coverage >= .90 and abs(row.combined_standardized_mismatch) >= 2 else "Moderate"
            findings.append(MatchupInteractionFinding(
                finding_id=f"matchup-interaction:{direction_id}:{row.interaction_family}",
                rank_within_direction=rank, direction_id=direction_id,
                attacking_team_id=row.attacking_team_id, attacking_team_name=row.attacking_team_name,
                defending_team_id=row.defending_team_id, defending_team_name=row.defending_team_name,
                interaction_family=row.interaction_family,
                production_metric=row.production_metric, exposure_metric=row.exposure_metric,
                review_priority_compatibility=row.review_priority_compatibility,
                title=_interaction_title(row),
                description=(
                    f"{row.attacking_team_name}'s season median is {row.attacking_median:.3f}; "
                    f"{row.defending_team_name}'s conceded median is {row.defending_exposure_median:.3f}. "
                    "Their interquartile distributions do not materially overlap under the configured rule."
                ),
                attacking_median=row.attacking_median,
                defending_exposure_median=row.defending_exposure_median,
                signed_mismatch=row.signed_mismatch,
                combined_standardized_mismatch=row.combined_standardized_mismatch,
                interaction_strength_score=row.interaction_strength_score,
                evidence_basis=basis,
                attacking_contributing_matches=row.attacking_contributing_matches,
                defending_contributing_matches=row.defending_contributing_matches,
                attacking_coverage=row.attacking_coverage, defending_coverage=row.defending_coverage,
                unit=row.unit,
                limitations=(
                    "This compares separate season distributions and does not predict the head-to-head match.",
                    "The mismatch is descriptive and does not identify a weakness, cause, or tactical response.",
                    row.comparability_basis,
                ),
            ))
    return MatchupInteractionResult(
        team_a=base.target, team_b=base.opponent,
        compatibility={**base.compatibility, "directionality": "both_attack_vs_opposition_defence"},
        interactions=interactions, findings=findings,
        excluded_interactions=pd.DataFrame([*a_excluded, *b_excluded], columns=["direction_id", "attacking_team_id", "defending_team_id", "interaction_family", "reason"]),
        configuration={
            "minimum_contributing_matches": MIN_CONTRIBUTING_MATCHES,
            "minimum_coverage": MIN_COVERAGE,
            "minimum_absolute_standardized_mismatch": MIN_INTERACTION_STANDARDIZED_MISMATCH,
            "material_iqr_overlap_threshold": MATERIAL_IQR_OVERLAP,
            "mismatch_sign_convention": "attacking_production_minus_defending_exposure",
            "unit_of_historical_evidence": "match",
        },
    )
