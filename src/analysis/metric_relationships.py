"""Robust, interpretable metric relationships for event team profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from .event_team_profile import EventTeamSeasonProfile


MIN_RELATIONSHIP_MATCHES = 10
MIN_RELATIONSHIP_COVERAGE = 0.80
UNUSUAL_RESIDUAL_Z = 2.0

METRIC_RELATIONSHIPS = (
    ("possession_share_estimate", "progressive_passes_per90"),
    ("progressive_passes_per90", "passes_into_final_third_per90"),
    ("passes_into_final_third_per90", "passes_into_penalty_area_per90"),
    ("passes_into_penalty_area_per90", "shots_per90"),
    ("shots_per90", "xg_per90"),
    ("high_regains_per90", "counter_attack_shots_per90"),
)


@dataclass(frozen=True)
class MetricRelationshipFinding:
    finding_id: str
    match_id: str | int
    team_id: str | int
    team_name: str
    upstream_metric: str
    downstream_metric: str
    title: str
    description: str
    upstream_value: float
    observed_downstream_value: float
    expected_downstream_value: float
    residual: float
    absolute_residual: float
    residual_robust_z: float
    contributing_match_count: int
    coverage: float
    evidence_level: str
    relationship_method: str
    slope: float
    intercept: float
    residual_prediction_low: float
    residual_prediction_high: float


@dataclass
class MetricRelationshipResult:
    relationship_fits: pd.DataFrame
    match_deviations: pd.DataFrame
    findings: list[MetricRelationshipFinding]
    total_matches: int

    def __post_init__(self) -> None:
        required_fit = {
            "upstream_metric", "downstream_metric", "slope", "intercept",
            "contributing_match_count", "coverage", "residual_robust_scale",
        }
        required_deviation = {
            "match_id", "upstream_metric", "downstream_metric",
            "expected_downstream_value", "residual", "residual_robust_z",
        }
        if missing := required_fit - set(self.relationship_fits.columns):
            raise ValueError(f"relationship_fits missing columns: {sorted(missing)}")
        if missing := required_deviation - set(self.match_deviations.columns):
            raise ValueError(f"match_deviations missing columns: {sorted(missing)}")


def _theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i, j in combinations(range(len(x)), 2)
        if abs(x[j] - x[i]) > 1e-12
    ]
    if not slopes:
        return float("nan"), float("nan")
    slope = float(np.median(slopes))
    return slope, float(np.median(y - slope * x))


def _robust_scale(values: np.ndarray) -> tuple[float, str]:
    series = pd.Series(values)
    scale = float((series.quantile(.75) - series.quantile(.25)) / 1.349)
    if scale > 1e-12:
        return scale, "residual_iqr_over_1.349"
    scale = float((series - series.median()).abs().median() * 1.4826)
    return (scale, "residual_mad_times_1.4826") if scale > 1e-12 else (float("nan"), "zero_residual_dispersion")


def _slope_sensitivity(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slopes = []
    for omitted in range(len(x)):
        keep = np.arange(len(x)) != omitted
        slope, _ = _theil_sen(x[keep], y[keep])
        if np.isfinite(slope):
            slopes.append(slope)
    if not slopes:
        return float("nan"), float("nan")
    return float(np.quantile(slopes, .025)), float(np.quantile(slopes, .975))


def _finding_title(team: str, upstream: str, downstream: str, residual: float) -> str:
    direction = "more" if residual > 0 else "fewer"
    readable = {
        "progressive_passes_per90": "progressive passes",
        "passes_into_final_third_per90": "final-third pass entries",
        "passes_into_penalty_area_per90": "penalty-area pass entries",
        "shots_per90": "shots",
        "xg_per90": "xG",
        "counter_attack_shots_per90": "explicitly tagged counter-attack shots",
    }[downstream]
    if downstream == "xg_per90":
        direction = "higher" if residual > 0 else "lower"
        return f"{team} recorded {direction} xG than expected for its shot volume"
    return f"{team} recorded {direction} {readable} than expected"


def build_metric_relationship_deviations(profile: EventTeamSeasonProfile) -> MetricRelationshipResult:
    """Fit declared Theil–Sen relationships and test robust residuals."""
    matches = profile.match_metrics
    fits, deviations, findings = [], [], []
    total = len(matches)
    for upstream, downstream in METRIC_RELATIONSHIPS:
        if upstream not in matches or downstream not in matches:
            continue
        paired = matches[["match_id", upstream, downstream]].copy()
        paired[upstream] = pd.to_numeric(paired[upstream], errors="coerce")
        paired[downstream] = pd.to_numeric(paired[downstream], errors="coerce")
        paired = paired.dropna()
        coverage = len(paired) / total if total else 0.0
        if len(paired) < MIN_RELATIONSHIP_MATCHES or coverage < MIN_RELATIONSHIP_COVERAGE:
            continue
        x, y = paired[upstream].to_numpy(float), paired[downstream].to_numpy(float)
        slope, intercept = _theil_sen(x, y)
        if not np.isfinite(slope):
            continue
        expected = intercept + slope * x
        residual = y - expected
        residual_centre = float(np.median(residual))
        centred = residual - residual_centre
        scale, scale_method = _robust_scale(centred)
        q25, q75 = float(np.quantile(centred, .25)), float(np.quantile(centred, .75))
        sensitivity_low, sensitivity_high = _slope_sensitivity(x, y)
        spearman = float(pd.Series(x).corr(pd.Series(y), method="spearman"))
        prediction_half_width = 1.96 * scale if np.isfinite(scale) else float("nan")
        fits.append({
            "upstream_metric": upstream, "downstream_metric": downstream,
            "method": "theil_sen_median_pairwise_slope", "slope": slope,
            "intercept": intercept, "equation": f"expected_y = {intercept:.6g} + {slope:.6g} * x",
            "spearman_rank_correlation": spearman,
            "slope_leave_one_out_low": sensitivity_low,
            "slope_leave_one_out_high": sensitivity_high,
            "slope_interval_kind": "leave_one_match_out_2.5_to_97.5_percentile_sensitivity_not_confidence_interval",
            "residual_centre": residual_centre, "residual_q25": q25, "residual_q75": q75,
            "residual_robust_scale": scale, "residual_scale_method": scale_method,
            "descriptive_prediction_half_width_95": prediction_half_width,
            "prediction_interval_kind": "expected_value_plus_or_minus_1.96_robust_residual_scales_not_model_confidence",
            "contributing_match_count": len(paired), "coverage": coverage,
        })
        paired = paired.reset_index(drop=True)
        for position in range(len(paired)):
            match_id = paired.at[position, "match_id"]
            upstream_value, downstream_value = float(x[position]), float(y[position])
            centred_residual = float(centred[position])
            residual_z = centred_residual / scale if np.isfinite(scale) and scale > 0 else float("nan")
            record = {
                "match_id": match_id, "upstream_metric": upstream,
                "downstream_metric": downstream, "upstream_value": upstream_value,
                "observed_downstream_value": downstream_value,
                "expected_downstream_value": float(expected[position] + residual_centre),
                "residual": centred_residual, "absolute_residual": abs(centred_residual),
                "residual_robust_z": residual_z,
                "prediction_low": float(expected[position] + residual_centre - prediction_half_width) if np.isfinite(prediction_half_width) else float("nan"),
                "prediction_high": float(expected[position] + residual_centre + prediction_half_width) if np.isfinite(prediction_half_width) else float("nan"),
                "contributing_match_count": len(paired), "coverage": coverage,
            }
            deviations.append(record)
            if not np.isfinite(residual_z) or abs(residual_z) < UNUSUAL_RESIDUAL_Z:
                continue
            evidence = "strong" if len(paired) >= 20 and coverage >= .90 and abs(residual_z) >= 2.5 else "moderate"
            title = _finding_title(profile.team_name, upstream, downstream, centred_residual)
            findings.append(MetricRelationshipFinding(
                finding_id=f"metric-relationship:{profile.team_id}:{profile.season_id}:{match_id}:{upstream}:{downstream}",
                match_id=match_id, team_id=profile.team_id, team_name=profile.team_name,
                upstream_metric=upstream, downstream_metric=downstream,
                title=title,
                description=f"Observed {downstream.replace('_', ' ')} was {downstream_value:.3f}; the season relationship expected {float(expected[position] + residual_centre):.3f} at this {upstream.replace('_', ' ')} value.",
                upstream_value=upstream_value, observed_downstream_value=downstream_value,
                expected_downstream_value=float(expected[position] + residual_centre),
                residual=centred_residual, absolute_residual=abs(centred_residual),
                residual_robust_z=residual_z, contributing_match_count=len(paired),
                coverage=coverage, evidence_level=evidence,
                relationship_method="theil_sen_median_pairwise_slope",
                slope=slope, intercept=intercept,
                residual_prediction_low=float(expected[position] + residual_centre - prediction_half_width),
                residual_prediction_high=float(expected[position] + residual_centre + prediction_half_width),
            ))
    fit_columns = [
        "upstream_metric", "downstream_metric", "method", "slope", "intercept",
        "contributing_match_count", "coverage", "residual_robust_scale",
    ]
    deviation_columns = [
        "match_id", "upstream_metric", "downstream_metric", "expected_downstream_value",
        "residual", "residual_robust_z",
    ]
    fit_frame = pd.DataFrame(fits) if fits else pd.DataFrame(columns=fit_columns)
    deviation_frame = pd.DataFrame(deviations) if deviations else pd.DataFrame(columns=deviation_columns)
    findings.sort(key=lambda item: (-abs(item.residual_robust_z), str(item.match_id), item.downstream_metric))
    return MetricRelationshipResult(fit_frame, deviation_frame, findings, total)
