"""Deterministic pre-match comparison of compatible event team-season profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd

from .event_team_profile import EventTeamSeasonProfile


MIN_CONTRIBUTING_MATCHES = 10
MIN_COVERAGE = 0.80
MATERIAL_IQR_OVERLAP = 0.25
MIN_CLEAR_STANDARDIZED_DIFFERENCE = 1.0

COMPARISON_METRICS: dict[str, tuple[str, ...]] = {
    "possession_circulation": ("possession_share_estimate", "passes_attempted_per90", "pass_completion_rate"),
    "progression": ("progressive_passes_per90", "progressive_carries_per90"),
    "final_third_access": ("passes_into_final_third_per90",),
    "penalty_area_access": ("passes_into_penalty_area_per90",),
    "shot_volume_xg": ("shots_per90", "xg_per90"),
    "shot_quality": ("xg_per_shot", "shots_on_target_per90", "average_shot_distance"),
    "defensive_activity": ("pressures_per90", "tackles_per90", "interceptions_per90", "recoveries_per90"),
    "high_regains": ("high_regains_per90",),
    "turnover_to_shot_exposure": ("turnovers_leading_to_shot_per90",),
    "explicit_counter_attack_shots": ("counter_attack_shots_per90",),
}

METRIC_LABELS = {
    "possession_share_estimate": "event-derived possession share",
    "passes_attempted_per90": "passes attempted per 90",
    "pass_completion_rate": "pass completion rate",
    "progressive_passes_per90": "progressive passes per 90",
    "progressive_carries_per90": "progressive carries per 90",
    "passes_into_final_third_per90": "final-third pass entries per 90",
    "passes_into_penalty_area_per90": "penalty-area pass entries per 90",
    "shots_per90": "shots per 90", "xg_per90": "xG per 90",
    "xg_per_shot": "xG per shot", "shots_on_target_per90": "shots on target per 90",
    "average_shot_distance": "average shot distance",
    "pressures_per90": "pressures per 90", "tackles_per90": "tackles per 90",
    "interceptions_per90": "interceptions per 90", "recoveries_per90": "recoveries per 90",
    "high_regains_per90": "high regains per 90",
    "turnovers_leading_to_shot_per90": "turnover-to-shot exposures per 90",
    "counter_attack_shots_per90": "explicit counter-attack shots per 90",
}

XG_PER_SHOT_DEFINITION = "Match xG divided by match shots where at least one shot was recorded."


@dataclass(frozen=True)
class OpponentComparisonFinding:
    finding_id: str
    rank: int
    finding_family: str
    metric: str
    title: str
    description: str
    target_value: float
    opponent_value: float
    signed_difference: float
    relative_difference: float | None
    combined_standardized_difference: float
    distributions_materially_overlap: bool
    evidence_basis: str
    priority_score: float
    contributing_matches_target: int
    contributing_matches_opponent: int
    coverage_target: float
    coverage_opponent: float
    unit: str
    limitations: tuple[str, ...]


@dataclass
class OpponentComparisonResult:
    target: dict
    opponent: dict
    compatibility: dict
    metric_comparisons: pd.DataFrame
    findings: list[OpponentComparisonFinding]
    excluded_metrics: pd.DataFrame
    configuration: dict

    def __post_init__(self) -> None:
        required = {
            "family", "metric", "target_median", "opponent_median", "signed_difference",
            "absolute_difference", "relative_difference", "standardized_by_target_variability",
            "standardized_by_opponent_variability", "combined_standardized_difference",
            "distributions_materially_overlap", "target_contributing_matches",
            "opponent_contributing_matches", "target_coverage", "opponent_coverage",
        }
        if missing := required - set(self.metric_comparisons.columns):
            raise ValueError(f"Opponent comparison metrics missing columns: {sorted(missing)}")
        if self.metric_comparisons.metric.duplicated().any():
            raise ValueError("Opponent comparison requires one row per metric.")
        if [item.rank for item in self.findings] != list(range(1, len(self.findings) + 1)):
            raise ValueError("Opponent comparison finding ranks must be contiguous.")


def _provider(profile: EventTeamSeasonProfile) -> str:
    providers = set(profile.match_metrics.get("provider", pd.Series(dtype=object)).dropna().astype(str))
    if len(providers) != 1:
        raise ValueError("Each event Team Profile must contain exactly one provider context.")
    return next(iter(providers))


def _coordinates(profile: EventTeamSeasonProfile) -> str | None:
    values = set(profile.match_metrics.coordinate_system.dropna().astype(str))
    if len(values) > 1:
        raise ValueError("A Team Profile cannot mix coordinate systems.")
    return next(iter(values)) if values else None


def _identity(profile: EventTeamSeasonProfile, provider: str) -> dict:
    return {
        "provider": provider, "team_id": profile.team_id, "team_name": profile.team_name,
        "competition_id": profile.competition_id, "competition_name": profile.competition_name,
        "season_id": profile.season_id, "season_name": profile.season_name,
        "analysed_match_count": int(len(profile.match_metrics)),
        "coordinate_system": _coordinates(profile),
    }


def _metric_series(profile: EventTeamSeasonProfile, metric: str) -> pd.Series:
    if metric == "xg_per_shot":
        xg = pd.to_numeric(profile.match_metrics.get("xg", pd.Series(index=profile.match_metrics.index, dtype=float)), errors="coerce")
        shots = pd.to_numeric(profile.match_metrics.get("shots", pd.Series(index=profile.match_metrics.index, dtype=float)), errors="coerce")
        return xg.div(shots.where(shots.gt(0)))
    return pd.to_numeric(profile.match_metrics.get(metric, pd.Series(index=profile.match_metrics.index, dtype=float)), errors="coerce")


def _metric_definition(profile: EventTeamSeasonProfile, metric: str) -> tuple[str, str]:
    if metric == "xg_per_shot":
        return "xG", XG_PER_SHOT_DEFINITION
    rows = profile.aggregate_metrics.loc[profile.aggregate_metrics.metric.eq(metric)]
    if len(rows) != 1:
        raise KeyError(f"Metric {metric} is unavailable from the profile aggregate contract.")
    row = rows.iloc[0]
    definition = row.get("definition")
    if pd.isna(definition):
        definitions = profile.definitions.loc[profile.definitions.metric.eq(metric)]
        definition = definitions.iloc[0].definition if len(definitions) == 1 else None
    if not isinstance(definition, str) or not definition:
        raise ValueError(f"Metric {metric} has no explicit definition.")
    return str(row.unit), definition


def _distribution(series: pd.Series, total: int) -> dict:
    values = series.dropna().astype(float)
    median = float(values.median())
    q25, q75 = float(values.quantile(.25)), float(values.quantile(.75))
    iqr_scale = (q75 - q25) / 1.349
    mad_scale = float((values - median).abs().median() * 1.4826)
    scale = iqr_scale if iqr_scale > 1e-12 else mad_scale if mad_scale > 1e-12 else float("nan")
    return {
        "median": median, "q25": q25, "q75": q75,
        "contributing_matches": int(len(values)), "coverage": float(len(values) / total) if total else 0.0,
        "robust_scale": float(scale),
    }


def _iqr_overlap(target: dict, opponent: dict) -> tuple[float, bool]:
    lower, upper = max(target["q25"], opponent["q25"]), min(target["q75"], opponent["q75"])
    intersection = max(upper - lower, 0.0)
    target_width, opponent_width = target["q75"] - target["q25"], opponent["q75"] - opponent["q25"]
    narrower = min(target_width, opponent_width)
    if narrower > 1e-12:
        ratio = intersection / narrower
    elif target_width <= 1e-12 and opponent_width <= 1e-12:
        ratio = 1.0 if math.isclose(target["median"], opponent["median"], abs_tol=1e-12) else 0.0
    else:
        point = target["median"] if target_width <= 1e-12 else opponent["median"]
        interval = opponent if target_width <= 1e-12 else target
        ratio = 1.0 if interval["q25"] <= point <= interval["q75"] else 0.0
    return float(ratio), bool(ratio >= MATERIAL_IQR_OVERLAP)


def _safe_standardized(difference: float, scale: float) -> float | None:
    return float(difference / scale) if pd.notna(scale) and scale > 1e-12 else None


def _title(target: str, opponent: str, metric: str, difference: float) -> str:
    higher = difference > 0
    if metric == "passes_into_penalty_area_per90":
        return f"{opponent} typically enters the penalty area {'more' if higher else 'less'} frequently than {target}"
    if metric == "passes_into_final_third_per90":
        return f"{opponent} typically enters the final third by pass {'more' if higher else 'less'} frequently than {target}"
    if metric == "possession_share_estimate":
        return f"{opponent} typically records {'more' if higher else 'less'} event-derived possession than {target}"
    if metric == "turnovers_leading_to_shot_per90":
        return f"{target}'s season contains {'fewer' if higher else 'more'} turnover-to-shot exposures than {opponent}'s season"
    if metric == "average_shot_distance":
        return f"{opponent}'s shots typically come from {'farther out' if higher else 'closer range'} than {target}'s"
    label = METRIC_LABELS[metric]
    return f"{opponent} typically records {'more' if higher else 'less'} {label} than {target}"


def compare_event_team_profiles(
    target_profile: EventTeamSeasonProfile,
    opponent_profile: EventTeamSeasonProfile,
    *, explicitly_comparable_provider_pairs: Iterable[tuple[str, str]] = (),
) -> OpponentComparisonResult:
    """Compare compatible season distributions; never pool their match rows."""
    target_provider, opponent_provider = _provider(target_profile), _provider(opponent_profile)
    if (
        target_profile.team_id == opponent_profile.team_id
        and target_profile.competition_id == opponent_profile.competition_id
        and target_profile.season_id == opponent_profile.season_id
        and target_provider == opponent_provider
    ):
        raise ValueError("Target and opponent must be different team-season profiles.")
    allowed_pairs = {tuple(map(str, pair)) for pair in explicitly_comparable_provider_pairs}
    providers_comparable = target_provider == opponent_provider or (target_provider, opponent_provider) in allowed_pairs
    if not providers_comparable:
        raise ValueError("Provider contexts differ and no explicit comparability rule was supplied.")
    target_coordinates, opponent_coordinates = _coordinates(target_profile), _coordinates(opponent_profile)
    if target_coordinates != opponent_coordinates:
        raise ValueError("Event coordinate contexts differ; comparison is not losslessly comparable.")

    target_identity = _identity(target_profile, target_provider)
    opponent_identity = _identity(opponent_profile, opponent_provider)
    rows, excluded = [], []
    for family, metrics in COMPARISON_METRICS.items():
        for metric in metrics:
            try:
                target_unit, target_definition = _metric_definition(target_profile, metric)
                opponent_unit, opponent_definition = _metric_definition(opponent_profile, metric)
                if target_unit != opponent_unit or target_definition != opponent_definition:
                    raise ValueError("metric unit or definition differs between provider contexts")
                target = _distribution(_metric_series(target_profile, metric), len(target_profile.match_metrics))
                opponent = _distribution(_metric_series(opponent_profile, metric), len(opponent_profile.match_metrics))
                quality_failures = []
                for side, distribution in (("target", target), ("opponent", opponent)):
                    if distribution["contributing_matches"] < MIN_CONTRIBUTING_MATCHES:
                        quality_failures.append(f"{side} has fewer than {MIN_CONTRIBUTING_MATCHES} contributing matches")
                    if distribution["coverage"] < MIN_COVERAGE:
                        quality_failures.append(f"{side} coverage is below {MIN_COVERAGE:.0%}")
                if quality_failures:
                    raise ValueError("; ".join(quality_failures))
                difference = opponent["median"] - target["median"]
                standardized_target = _safe_standardized(difference, target["robust_scale"])
                standardized_opponent = _safe_standardized(difference, opponent["robust_scale"])
                scales = [value for value in (target["robust_scale"], opponent["robust_scale"]) if pd.notna(value) and value > 1e-12]
                combined_scale = math.sqrt(sum(value * value for value in scales) / len(scales)) if len(scales) == 2 else float("nan")
                combined = _safe_standardized(difference, combined_scale)
                overlap_ratio, material_overlap = _iqr_overlap(target, opponent)
                rows.append({
                    "family": family, "metric": metric, "metric_label": METRIC_LABELS[metric],
                    "unit": target_unit, "definition": target_definition,
                    "target_median": target["median"], "target_q25": target["q25"], "target_q75": target["q75"],
                    "target_contributing_matches": target["contributing_matches"], "target_coverage": target["coverage"],
                    "target_robust_scale": target["robust_scale"],
                    "opponent_median": opponent["median"], "opponent_q25": opponent["q25"], "opponent_q75": opponent["q75"],
                    "opponent_contributing_matches": opponent["contributing_matches"], "opponent_coverage": opponent["coverage"],
                    "opponent_robust_scale": opponent["robust_scale"],
                    "signed_difference": difference, "absolute_difference": abs(difference),
                    "relative_difference": difference / abs(target["median"]) if abs(target["median"]) > 1e-12 else np.nan,
                    "standardized_by_target_variability": standardized_target,
                    "standardized_by_opponent_variability": standardized_opponent,
                    "combined_standardized_difference": combined,
                    "iqr_overlap_ratio": overlap_ratio, "distributions_materially_overlap": material_overlap,
                    "difference_sign_convention": "opponent_minus_target",
                })
            except (KeyError, ValueError) as error:
                excluded.append({"family": family, "metric": metric, "reason": str(error)})
    comparisons = pd.DataFrame(rows)
    if comparisons.empty:
        comparisons = pd.DataFrame(columns=[
            "family", "metric", "target_median", "opponent_median", "signed_difference",
            "absolute_difference", "relative_difference", "standardized_by_target_variability",
            "standardized_by_opponent_variability", "combined_standardized_difference",
            "distributions_materially_overlap", "target_contributing_matches",
            "opponent_contributing_matches", "target_coverage", "opponent_coverage",
        ])

    candidates = comparisons.loc[
        comparisons.combined_standardized_difference.notna()
        & comparisons.combined_standardized_difference.abs().ge(MIN_CLEAR_STANDARDIZED_DIFFERENCE)
        & ~comparisons.distributions_materially_overlap
    ].copy()
    candidates["priority_score"] = (
        .55 * candidates.combined_standardized_difference.abs().div(3).clip(upper=1)
        + .20 * candidates[["target_coverage", "opponent_coverage"]].min(axis=1)
        + .25 * candidates[["target_contributing_matches", "opponent_contributing_matches"]].min(axis=1).div(20).clip(upper=1)
    )
    candidates = candidates.sort_values(["priority_score", "family", "metric"], ascending=[False, True, True], kind="stable")
    candidates = candidates.drop_duplicates("family", keep="first")
    findings = []
    for rank, row in enumerate(candidates.itertuples(index=False), start=1):
        min_count = min(row.target_contributing_matches, row.opponent_contributing_matches)
        min_coverage = min(row.target_coverage, row.opponent_coverage)
        basis = "High" if min_count >= 20 and min_coverage >= .90 and abs(row.combined_standardized_difference) >= 2 else "Moderate"
        title = _title(target_profile.team_name, opponent_profile.team_name, row.metric, row.signed_difference)
        description = (
            f"{opponent_profile.team_name}'s season median for {row.metric_label} is {row.opponent_median:.3f}; "
            f"{target_profile.team_name}'s is {row.target_median:.3f}. The interquartile distributions do not materially overlap under the configured rule."
        )
        findings.append(OpponentComparisonFinding(
            finding_id=f"opponent-comparison:{target_provider}:{target_profile.team_id}:{target_profile.season_id}:{opponent_profile.team_id}:{opponent_profile.season_id}:{row.metric}",
            rank=rank, finding_family=row.family, metric=row.metric, title=title, description=description,
            target_value=row.target_median, opponent_value=row.opponent_median,
            signed_difference=row.signed_difference,
            relative_difference=None if pd.isna(row.relative_difference) else row.relative_difference,
            combined_standardized_difference=row.combined_standardized_difference,
            distributions_materially_overlap=row.distributions_materially_overlap,
            evidence_basis=basis, priority_score=row.priority_score,
            contributing_matches_target=row.target_contributing_matches,
            contributing_matches_opponent=row.opponent_contributing_matches,
            coverage_target=row.target_coverage, coverage_opponent=row.opponent_coverage,
            unit=row.unit,
            limitations=(
                "This compares separate team-season distributions and does not predict their head-to-head match.",
                "The comparison is descriptive and does not establish causes or tactical quality.",
            ),
        ))
    return OpponentComparisonResult(
        target_identity, opponent_identity,
        {
            "comparable": True,
            "provider_rule": "same_provider" if target_provider == opponent_provider else "explicit_provider_pair",
            "coordinate_system": target_coordinates,
            "required_capabilities": ("has_events",),
            "target_capabilities": {"has_events": True, "has_continuous_tracking": False},
            "opponent_capabilities": {"has_events": True, "has_continuous_tracking": False},
        },
        comparisons, findings, pd.DataFrame(excluded, columns=["family", "metric", "reason"]),
        {
            "minimum_contributing_matches": MIN_CONTRIBUTING_MATCHES,
            "minimum_coverage": MIN_COVERAGE,
            "material_iqr_overlap_threshold": MATERIAL_IQR_OVERLAP,
            "finding_minimum_absolute_standardized_difference": MIN_CLEAR_STANDARDIZED_DIFFERENCE,
            "difference_sign_convention": "opponent_minus_target",
            "unit_of_historical_evidence": "match",
        },
    )
