"""Deterministic, robustly standardized findings from event team profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .event_team_profile import EventTeamSeasonProfile


MIN_CONTRIBUTING_MATCHES = 10
MIN_COVERAGE = 0.80
MIN_ABSOLUTE_ROBUST_Z = 1.50
CORRELATION_SUPPRESSION_THRESHOLD = 0.85

FINDING_METRICS = {
    "possession_share_estimate": "possession_circulation",
    "passes_attempted_per90": "possession_circulation",
    "pass_completion_rate": "possession_circulation",
    "progressive_passes_per90": "progression",
    "progressive_carries_per90": "progression",
    "passes_into_final_third_per90": "progression",
    "passes_into_penalty_area_per90": "penalty_area_access",
    "shots_per90": "chance_creation",
    "shots_on_target_per90": "chance_creation",
    "xg_per90": "chance_creation",
    "average_shot_distance": "chance_creation",
    "open_play_shots_per90": "chance_creation",
    "set_play_shots_per90": "chance_creation",
    "pressures_per90": "defensive_activity",
    "tackles_per90": "defensive_activity",
    "interceptions_per90": "defensive_activity",
    "recoveries_per90": "defensive_activity",
    "high_regains_per90": "high_regains",
    "turnovers_leading_to_shot_per90": "turnover_to_shot_exposure",
    "counter_attack_shots_per90": "explicit_fast_attacks",
}


@dataclass(frozen=True)
class EventProfileFinding:
    finding_id: str
    provider: str
    team_id: str | int
    team_name: str
    competition_id: str | int
    season_id: str | int
    source_match_id: str | int
    finding_family: str
    metric: str
    title: str
    description: str
    observed_value: float
    season_baseline: float
    signed_deviation: float
    absolute_deviation: float
    relative_deviation: float | None
    robust_z_score: float
    contributing_match_count: int
    coverage: float
    evidence_level: str
    unit: str
    definition: str


@dataclass
class EventProfileFindingResult:
    profile: EventTeamSeasonProfile
    deviations: pd.DataFrame
    findings: list[EventProfileFinding]
    recurring_tendencies: pd.DataFrame
    suppressed_duplicates: pd.DataFrame

    def __post_init__(self) -> None:
        required = {
            "match_id", "metric", "observed_value", "season_baseline",
            "signed_deviation", "absolute_deviation", "relative_deviation", "robust_z_score",
            "contributing_match_count", "coverage",
        }
        if missing := required - set(self.deviations.columns):
            raise ValueError(f"event-profile deviations missing columns: {sorted(missing)}")
        ids = [finding.finding_id for finding in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("Event-profile finding IDs must be unique.")


def _robust_scale(values: pd.Series) -> tuple[float, str]:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return float("nan"), "unavailable"
    iqr_scale = float((values.quantile(.75) - values.quantile(.25)) / 1.349)
    if iqr_scale > 1e-12:
        return iqr_scale, "iqr_over_1.349"
    median = float(values.median())
    mad_scale = float((values - median).abs().median() * 1.4826)
    return (mad_scale, "mad_times_1.4826") if mad_scale > 1e-12 else (float("nan"), "zero_season_dispersion")


def _direction(metric: str, deviation: float) -> str:
    if metric == "average_shot_distance":
        return "farther from" if deviation > 0 else "closer to"
    return "above" if deviation > 0 else "below"


def _title(team: str, family: str, metric: str, deviation: float) -> str:
    up = deviation > 0
    labels = {
        "possession_share_estimate": f"{team} had {'more' if up else 'less'} of the event-derived possession timeline",
        "passes_attempted_per90": f"{team} circulated at a {'higher' if up else 'lower'} volume",
        "pass_completion_rate": f"{team}'s pass completion was {'above' if up else 'below'} its season baseline",
        "progressive_passes_per90": f"{team} made {'more' if up else 'fewer'} progressive passes",
        "progressive_carries_per90": f"{team} made {'more' if up else 'fewer'} progressive carries",
        "passes_into_final_third_per90": f"{team} entered the final third by pass {'more' if up else 'less'} often",
        "passes_into_penalty_area_per90": f"{team} accessed the penalty area by pass {'more' if up else 'less'} often",
        "shots_per90": f"{team} generated an {'elevated' if up else 'reduced'} shot volume",
        "shots_on_target_per90": f"{team} recorded {'more' if up else 'fewer'} shots on target",
        "xg_per90": f"{team}'s xG was {'above' if up else 'below'} its season baseline",
        "average_shot_distance": f"{team}'s shots came from {'farther out' if up else 'closer range'}",
        "open_play_shots_per90": f"{team} produced {'more' if up else 'fewer'} open-play shots",
        "set_play_shots_per90": f"{team} produced {'more' if up else 'fewer'} set-play shots",
        "pressures_per90": f"{team} applied {'more' if up else 'fewer'} pressures",
        "tackles_per90": f"{team} attempted {'more' if up else 'fewer'} tackles",
        "interceptions_per90": f"{team} made {'more' if up else 'fewer'} interceptions",
        "recoveries_per90": f"{team} made {'more' if up else 'fewer'} recoveries",
        "high_regains_per90": f"{team} registered {'more' if up else 'fewer'} high regains",
        "turnovers_leading_to_shot_per90": f"{team} had {'more' if up else 'fewer'} turnovers followed by an opposition shot",
        "counter_attack_shots_per90": f"{team} recorded {'more' if up else 'fewer'} explicitly tagged counter-attack shots",
    }
    return labels.get(metric, f"{team}'s {metric.replace('_', ' ')} was {_direction(metric, deviation)} baseline")


def _evidence_level(match_count: int, coverage: float, robust_z: float) -> str:
    magnitude = abs(robust_z)
    if match_count >= 20 and coverage >= .90 and magnitude >= 2.5:
        return "strong"
    if match_count >= 10 and coverage >= .80 and magnitude >= 2.0:
        return "moderate"
    return "limited"


def generate_event_profile_findings(profile: EventTeamSeasonProfile) -> EventProfileFindingResult:
    """Compare all numeric match metrics, then shortlist robust deviations."""
    matches = profile.match_metrics.copy()
    definitions = profile.definitions.set_index("metric")
    aggregate = profile.aggregate_metrics.set_index("metric")
    identity = {
        "team_id": profile.team_id, "team_name": profile.team_name,
        "competition_id": profile.competition_id, "season_id": profile.season_id,
    }
    excluded = set(matches.columns) - set(definitions.index)
    metric_names = [metric for metric in definitions.index if metric in matches.columns and metric not in excluded]
    rows: list[dict[str, Any]] = []
    for metric in metric_names:
        values = pd.to_numeric(matches[metric], errors="coerce")
        observed = values.dropna()
        baseline = float(observed.median()) if not observed.empty else float("nan")
        scale, method = _robust_scale(observed)
        coverage = float(observed.notna().sum() / len(matches)) if len(matches) else 0.0
        for index, value in values.items():
            if pd.isna(value):
                continue
            deviation = float(value - baseline)
            rows.append({
                "match_id": matches.loc[index, "match_id"], "match_date": matches.loc[index].get("match_date"),
                "metric": metric, "finding_family": FINDING_METRICS.get(metric),
                "observed_value": float(value), "season_baseline": baseline,
                "signed_deviation": deviation, "absolute_deviation": abs(deviation),
                "relative_deviation": deviation / abs(baseline) if abs(baseline) > 1e-12 else np.nan,
                "robust_scale": scale, "robust_scale_method": method,
                "robust_z_score": deviation / scale if pd.notna(scale) and scale > 0 else np.nan,
                "contributing_match_count": int(observed.notna().sum()), "coverage": coverage,
                "unit": definitions.loc[metric, "unit"], "definition": definitions.loc[metric, "definition"],
            })
    deviations = pd.DataFrame(rows)
    if deviations.empty:
        deviations = pd.DataFrame(columns=[
            "match_id", "metric", "observed_value", "season_baseline", "signed_deviation", "absolute_deviation",
            "relative_deviation", "robust_z_score", "contributing_match_count", "coverage",
        ])

    candidate = deviations.loc[
        deviations.metric.isin(FINDING_METRICS)
        & deviations.contributing_match_count.ge(MIN_CONTRIBUTING_MATCHES)
        & deviations.coverage.ge(MIN_COVERAGE)
        & deviations.robust_z_score.abs().ge(MIN_ABSOLUTE_ROBUST_Z)
    ].copy()
    candidate = candidate.sort_values(
        ["match_id", "robust_z_score", "metric"], ascending=[True, False, True], key=lambda column: column.abs() if column.name == "robust_z_score" else column,
        kind="stable",
    )
    correlation_metrics = [metric for metric in FINDING_METRICS if metric in matches]
    correlations = matches[correlation_metrics].apply(pd.to_numeric, errors="coerce").corr(method="spearman")
    kept, suppressed = [], []
    for row in candidate.to_dict("records"):
        duplicate_of = None
        for accepted in kept:
            if accepted["match_id"] != row["match_id"] or accepted["finding_family"] != row["finding_family"]:
                continue
            correlation = correlations.loc[row["metric"], accepted["metric"]]
            if pd.notna(correlation) and abs(float(correlation)) >= CORRELATION_SUPPRESSION_THRESHOLD:
                duplicate_of = accepted["metric"]
                break
        if duplicate_of:
            row["suppressed_by_metric"] = duplicate_of
            suppressed.append(row)
        else:
            kept.append(row)

    provider = str(matches.provider.iloc[0]) if not matches.empty else "unknown"
    findings = []
    for row in kept:
        evidence = _evidence_level(row["contributing_match_count"], row["coverage"], row["robust_z_score"])
        title = _title(profile.team_name, row["finding_family"], row["metric"], row["signed_deviation"])
        description = (
            f"In match {row['match_id']}, {row['metric'].replace('_', ' ')} was {row['observed_value']:.3f} "
            f"versus the {row['contributing_match_count']}-match season median of {row['season_baseline']:.3f}."
        )
        findings.append(EventProfileFinding(
            finding_id=f"event-profile:{provider}:{profile.team_id}:{profile.season_id}:{row['match_id']}:{row['metric']}",
            provider=provider, **identity, source_match_id=row["match_id"],
            finding_family=row["finding_family"], metric=row["metric"], title=title,
            description=description, observed_value=row["observed_value"],
            season_baseline=row["season_baseline"], signed_deviation=row["signed_deviation"],
            absolute_deviation=row["absolute_deviation"],
            relative_deviation=None if pd.isna(row["relative_deviation"]) else row["relative_deviation"],
            robust_z_score=row["robust_z_score"], contributing_match_count=row["contributing_match_count"],
            coverage=row["coverage"], evidence_level=evidence, unit=row["unit"], definition=row["definition"],
        ))
    findings.sort(key=lambda finding: (-abs(finding.robust_z_score), str(finding.source_match_id), finding.metric))
    finding_frame = pd.DataFrame([asdict(finding) for finding in findings])
    tendencies = (
        finding_frame.groupby("finding_family").agg(
            unusual_matches=("source_match_id", "nunique"), finding_count=("finding_id", "size"),
            above_baseline=("signed_deviation", lambda values: int(values.gt(0).sum())),
            below_baseline=("signed_deviation", lambda values: int(values.lt(0).sum())),
            strongest_robust_z=("robust_z_score", lambda values: float(values.loc[values.abs().idxmax()])),
        ).reset_index().sort_values(["unusual_matches", "finding_family"], ascending=[False, True], kind="stable")
        if not finding_frame.empty else pd.DataFrame(columns=["finding_family", "unusual_matches", "finding_count", "above_baseline", "below_baseline", "strongest_robust_z"])
    )
    return EventProfileFindingResult(profile, deviations, findings, tendencies, pd.DataFrame(suppressed))
