"""Provider-aware, match-weighted descriptive team profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import pandas as pd

from src.data import CanonicalMatchBundle, validate_canonical_bundle
from src.metrics import calculate_defensive_line_structure, calculate_team_shape

from .phase_shape import summarize_phase_shape
from .tactical_findings import (MatchAnalysisResult, generate_phase_shape_findings,
    generate_shot_local_context_findings, generate_shot_sequence_findings,
    generate_team_shape_extreme_findings)
from .finding_prioritization import prioritize_findings


@dataclass(frozen=True)
class TeamProfileIdentity:
    team_id: str | int
    team_name: str
    provider_team_ids: Mapping[str, str | int]

    def __post_init__(self) -> None:
        if not str(self.team_id) or not self.team_name.strip() or not self.provider_team_ids:
            raise ValueError("Team profile identity requires an ID, name, and provider team-ID mapping.")


@dataclass
class TeamProfileResult:
    team_identity: TeamProfileIdentity
    matches_included: pd.DataFrame
    matches_excluded: pd.DataFrame
    capability_coverage: pd.DataFrame
    sample_periods: pd.DataFrame
    match_level_values: pd.DataFrame
    aggregate_patterns: pd.DataFrame
    match_deviations: pd.DataFrame
    recurring_finding_families: pd.DataFrame

    def __post_init__(self) -> None:
        required = {
            "matches_included": {"match_id", "provider", "provider_team_id"},
            "matches_excluded": {"match_id", "provider", "reason"},
            "capability_coverage": {"capability", "available_matches", "included_matches", "coverage"},
            "sample_periods": {"match_id", "provider", "period", "tracked_frames", "represented_seconds"},
            "match_level_values": {"match_id", "provider", "metric_family", "metric", "value", "capability_signature"},
            "aggregate_patterns": {"provider", "metric_family", "metric", "median_across_matches", "q25_across_matches", "q75_across_matches", "contributing_matches", "evidence_band", "baseline_label"},
            "match_deviations": {"match_id", "metric", "team_baseline", "deviation_from_baseline", "deviation_label", "contributing_matches", "evidence_band", "baseline_label", "comparison_label"},
            "recurring_finding_families": {"provider", "finding_family", "contributing_matches", "finding_count"},
        }
        for field, columns in required.items():
            missing = columns - set(getattr(self, field).columns)
            if missing:
                raise ValueError(f"{field} is missing columns: {sorted(missing)}")
        if self.match_level_values.duplicated(["match_id", "provider", "metric_family", "metric", "possession_status", "tactical_phase"]).any():
            raise ValueError("Team profile contains duplicate match-level metric observations.")


CAPABILITIES = (
    "has_continuous_tracking", "has_ball_tracking", "has_verified_roles",
    "has_attacking_direction", "has_events", "has_tactical_phases",
    "has_lineups", "has_360_snapshots",
)
DEFAULT_EVIDENCE_BANDS = (
    (3, "insufficient"),
    (5, "provisional"),
    (10, "developing"),
    (float("inf"), "established"),
)
VALUE_COLUMNS = [
    "match_id", "provider", "provider_team_id", "metric_family", "metric",
    "possession_status", "tactical_phase", "value", "match_q25", "match_q75",
    "sample_size", "required_capabilities", "capability_signature", "evidence_finding_id",
    "representative_frame", "representative_period",
]


def profile_evidence_band(
    contributing_matches: int,
    bands: Sequence[tuple[float, str]] = DEFAULT_EVIDENCE_BANDS,
) -> str:
    """Classify profile evidence using configurable, ordered upper bounds."""
    if contributing_matches < 0:
        raise ValueError("contributing_matches cannot be negative")
    for upper_bound, label in bands:
        if contributing_matches < upper_bound:
            return label
    raise ValueError("evidence bands must include a final bound covering all sample sizes")


def profile_baseline_label(contributing_matches: int) -> str:
    if contributing_matches == 1:
        return "single-match provisional reference"
    if contributing_matches == 2:
        return "two-match provisional baseline"
    return f"{profile_evidence_band(contributing_matches)} baseline"


def _signature(bundle: CanonicalMatchBundle, required: Sequence[str]) -> str:
    return ";".join(f"{name}={int(getattr(bundle.capabilities, name))}" for name in required)


def _value_rows(bundle, team_id, shape, match_id):
    rows = []
    phase_joined = None
    team_shape = shape.reset_index().loc[lambda x: x.team_id.eq(team_id)]
    definitions = [("full_team_width", ("has_continuous_tracking",)), ("full_team_length", ("has_continuous_tracking",))]
    if bundle.capabilities.has_verified_roles:
        definitions += [("outfield_width", ("has_continuous_tracking", "has_verified_roles")), ("outfield_length", ("has_continuous_tracking", "has_verified_roles"))]
    for metric, required in definitions:
        values = team_shape[metric].dropna()
        if not values.empty:
            row = _metric_row(bundle, team_id, match_id, "overall_team_shape", metric, values, required)
            nearest = team_shape.loc[values.sub(values.median()).abs().idxmin()]
            row.update(representative_frame=int(nearest.frame), representative_period=int(nearest.period))
            rows.append(row)

    phases = bundle.tactical_phases
    if bundle.capabilities.has_tactical_phases and bundle.capabilities.has_verified_roles and phases is not None:
        contexts = []
        match_teams = set(bundle.teams.team_id)
        for phase in phases.itertuples(index=False):
            other = next(iter(match_teams - {phase.possession_team_id}))
            if team_id == phase.possession_team_id:
                status, label = "in_possession", getattr(phase, "attacking_phase_type", None)
            elif team_id == other:
                status, label = "out_of_possession", getattr(phase, "defending_phase_type", None)
            else:
                continue
            if pd.isna(label):
                continue
            contexts.extend(
                {
                    "frame": frame,
                    "period": phase.period,
                    "possession_status": status,
                    "tactical_phase": label,
                    "possession_team_id": phase.possession_team_id,
                    "phase_frame_start": int(phase.frame_start),
                    "phase_frame_end": int(phase.frame_end_exclusive),
                }
                for frame in range(int(phase.frame_start), int(phase.frame_end_exclusive))
            )
        if contexts:
            joined = team_shape.merge(pd.DataFrame(contexts), on=["frame", "period"], how="inner", validate="one_to_one")
            phase_joined = joined.set_index(["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"])
            for (status, phase), group in joined.groupby(["possession_status", "tactical_phase"]):
                for metric in ("outfield_width", "outfield_length"):
                    values = group[metric].dropna()
                    if not values.empty:
                        row = _metric_row(bundle, team_id, match_id, "phase_team_shape", metric, values, ("has_continuous_tracking", "has_verified_roles", "has_tactical_phases"))
                        row.update(possession_status=status, tactical_phase=phase)
                        nearest = group.loc[values.sub(values.median()).abs().idxmin()]
                        row.update(representative_frame=int(nearest.frame), representative_period=int(nearest.period))
                        rows.append(row)

    if bundle.capabilities.has_verified_roles and bundle.capabilities.has_attacking_direction:
        lines = calculate_defensive_line_structure(bundle.player_positions, bundle.match_info).reset_index()
        lines = lines.loc[lines.team_id.eq(team_id)]
        centroids = team_shape[["frame", "period", "outfield_centroid_x"]].drop_duplicates(["frame", "period"])
        lines = lines.merge(centroids, on=["frame", "period"], how="left", validate="one_to_one")
        lines["outfield_tactical_centroid_x"] = lines["outfield_centroid_x"] * lines["attacking_direction_sign"]
        for metric in ("outfield_tactical_centroid_x", "defence_tactical_median_x", "midfield_tactical_median_x", "attack_tactical_median_x", "defence_to_midfield_gap", "midfield_to_attack_gap", "total_outfield_length"):
            values = lines[metric].dropna()
            if not values.empty:
                row = _metric_row(bundle, team_id, match_id, "defensive_line_structure", metric, values, ("has_continuous_tracking", "has_verified_roles", "has_attacking_direction"))
                nearest = lines.loc[values.sub(values.median()).abs().idxmin()]
                row.update(representative_frame=int(nearest.frame), representative_period=int(nearest.period))
                rows.append(row)
        if phase_joined is not None:
            context = phase_joined.reset_index()[["frame", "period", "possession_status", "tactical_phase"]]
            contextual_lines = lines.merge(context, on=["frame", "period"], how="inner", validate="one_to_one")
            required = ("has_continuous_tracking", "has_verified_roles", "has_attacking_direction", "has_tactical_phases")
            for (status, phase), group in contextual_lines.groupby(["possession_status", "tactical_phase"], sort=False):
                for metric in ("outfield_tactical_centroid_x", "defence_tactical_median_x", "midfield_tactical_median_x", "defence_to_midfield_gap", "midfield_to_attack_gap", "total_outfield_length"):
                    values = group[metric].dropna()
                    if values.empty:
                        continue
                    row = _metric_row(bundle, team_id, match_id, "phase_defensive_line_structure", metric, values, required)
                    row.update(possession_status=status, tactical_phase=phase)
                    nearest = group.loc[values.sub(values.median()).abs().idxmin()]
                    row.update(representative_frame=int(nearest.frame), representative_period=int(nearest.period))
                    rows.append(row)

    if bundle.capabilities.has_events and bundle.events is not None:
        shots = bundle.events.loc[bundle.events.is_shot.eq(True)]
        for metric, value in (("shots_for", shots.team_id.eq(team_id).sum()), ("shots_conceded", shots.team_id.ne(team_id).sum())):
            rows.append(_metric_row(bundle, team_id, match_id, "shot_counts", metric, pd.Series([float(value)]), ("has_events",)))
    return rows, phase_joined


def _metric_row(bundle, team_id, match_id, family, metric, values, required):
    return {"match_id": match_id, "provider": bundle.provider, "provider_team_id": team_id, "metric_family": family, "metric": metric,
            "possession_status": pd.NA, "tactical_phase": pd.NA, "value": float(values.median()), "match_q25": float(values.quantile(.25)),
            "match_q75": float(values.quantile(.75)), "sample_size": len(values), "required_capabilities": ",".join(required),
            "capability_signature": _signature(bundle, required),
            "representative_frame": pd.NA, "representative_period": pd.NA}


def _attach_evidence_links(rows, result):
    shortlisted = prioritize_findings(result, shortlist_size=10).shortlist
    for row in rows:
        match = None
        for finding in shortlisted:
            metrics = finding.evidence_metrics
            if row["metric_family"] == "overall_team_shape" and finding.finding_type == "team_shape_extreme" and finding.finding_id.endswith(row["metric"]):
                match = finding.finding_id
            elif row["metric_family"] == "phase_team_shape" and finding.finding_type == "phase_shape_variability" and metrics.get("dimension") in row["metric"] and metrics.get("tactical_phase") == row["tactical_phase"] and metrics.get("possession_status") == row["possession_status"]:
                match = finding.finding_id
            if match:
                break
        row["evidence_finding_id"] = match


def _deviation_label(metric: str, deviation: float) -> str:
    if abs(deviation) < 1e-12:
        return "at_team_baseline"
    positive = deviation > 0
    if "width" in metric: return "wider" if positive else "narrower"
    if metric == "defence_tactical_median_x": return "higher" if positive else "deeper"
    if "length" in metric: return "more_stretched" if positive else "more_compact"
    if "gap" in metric: return "larger_gap" if positive else "smaller_gap"
    return "above_baseline" if positive else "below_baseline"


def _finding_family(finding_type: str) -> str:
    if finding_type == "phase_shape_variability": return "phase_shape"
    if finding_type == "team_shape_extreme": return "team_shape_extreme"
    if finding_type in {"shot_sequence_density", "shot_local_context"}: return "shot_sequence_local_context"
    return "other"


def build_team_profile(
    bundles: Iterable[CanonicalMatchBundle],
    identity: TeamProfileIdentity,
    *,
    analysis_results: Mapping[str | int, MatchAnalysisResult] | None = None,
    preexcluded_matches: Iterable[Mapping[str, object]] | None = None,
) -> TeamProfileResult:
    """Build match-weighted baselines without pooling frames across matches."""
    included = []
    excluded = [dict(row) for row in (preexcluded_matches or ())]
    periods, values, family_rows = [], [], []
    accepted_capabilities = []
    for bundle in bundles:
        match_id = bundle.matches.match_id.iloc[0]
        try:
            validate_canonical_bundle(bundle)
            expected_id = identity.provider_team_ids.get(bundle.provider)
            if expected_id is None:
                raise ValueError("team identity has no mapping for this provider")
            if expected_id not in set(bundle.teams.team_id):
                raise ValueError("mapped team ID is absent from this match")
            if bundle.capabilities.has_tactical_phases and bundle.tactical_phases is not None:
                tracked_periods = bundle.player_positions[["frame", "period"]].drop_duplicates().set_index("frame").period
                for phase in bundle.tactical_phases.itertuples(index=False):
                    observed = tracked_periods.reindex(range(int(phase.frame_start), int(phase.frame_end_exclusive))).dropna()
                    if not observed.eq(phase.period).all():
                        raise ValueError("canonical tactical-phase and tracking periods disagree")
        except Exception as error:
            excluded.append({"match_id": match_id, "provider": bundle.provider, "reason": str(error)})
            continue
        try:
            match_periods = []
            tracked = bundle.player_positions.loc[bundle.player_positions.team_id.eq(expected_id)]
            for period, period_group in tracked.groupby("period"):
                frames = period_group.frame.nunique()
                times = period_group[["frame", "elapsed_seconds"]].drop_duplicates("frame").elapsed_seconds.dropna().sort_values()
                steps = times.diff().dropna()
                represented_seconds = float(times.max() - times.min() + steps.median()) if len(times) > 1 and not steps.empty else 0.
                match_periods.append({"match_id": match_id, "provider": bundle.provider, "period": period, "tracked_frames": frames, "represented_seconds": represented_seconds})
            shape = calculate_team_shape(bundle.player_positions)
            match_values, phase_joined = _value_rows(bundle, expected_id, shape, match_id)
            supplied_result = (analysis_results or {}).get(match_id)
            if supplied_result is not None:
                findings = supplied_result.findings
                result_for_links = supplied_result
            else:
                team_names = {team["id"]: team.get("name") or team.get("acronym") or str(team["id"]) for team in (bundle.match_info.get("home_team", {}), bundle.match_info.get("away_team", {})) if "id" in team}
                findings = generate_team_shape_extreme_findings(shape, match_id=match_id, team_names=team_names)
                if phase_joined is not None:
                    findings += generate_phase_shape_findings(summarize_phase_shape(phase_joined), phase_joined.reset_index(), match_id=match_id)
                local, _ = generate_shot_local_context_findings(bundle) if bundle.capabilities.has_events and bundle.capabilities.has_ball_tracking and bundle.capabilities.has_verified_roles and bundle.capabilities.has_attacking_direction else ([], None)
                sequence, _ = generate_shot_sequence_findings(bundle) if bundle.capabilities.has_events and bundle.capabilities.has_tactical_phases else ([], None)
                findings += local + sequence
                coverage = pd.DataFrame([{"analysis": name, "status": "run", "finding_count": 0} for name in ("team_shape", "phase_shape_analysis", "local_defensive_context", "temporal_shot_analysis")])
                result_for_links = MatchAnalysisResult(findings, coverage, [], {"provider": bundle.provider, "capabilities": bundle.capabilities, "allow_assumed_roles": False})
            _attach_evidence_links(match_values, result_for_links)
            match_families = [{"match_id": match_id, "provider": bundle.provider, "finding_family": _finding_family(finding.finding_type)} for finding in findings if finding.team_id == expected_id]
        except Exception as error:
            excluded.append({"match_id": match_id, "provider": bundle.provider, "reason": f"profile processing failed: {error}"})
            continue
        accepted_capabilities.append((bundle.provider, bundle.capabilities))
        included.append({"match_id": match_id, "provider": bundle.provider, "provider_team_id": expected_id})
        periods.extend(match_periods)
        values.extend(match_values)
        family_rows.extend(match_families)

    included_df = pd.DataFrame(included, columns=["match_id", "provider", "provider_team_id"])
    excluded_df = pd.DataFrame(excluded, columns=["match_id", "provider", "reason"])
    periods_df = pd.DataFrame(periods, columns=["match_id", "provider", "period", "tracked_frames", "represented_seconds"])
    value_df = pd.DataFrame(values, columns=VALUE_COLUMNS)
    capability_rows = []
    for capability in CAPABILITIES:
        count = sum(bool(getattr(capabilities, capability)) for _, capabilities in accepted_capabilities)
        capability_rows.append({"capability": capability, "available_matches": count, "included_matches": len(accepted_capabilities), "coverage": count / len(accepted_capabilities) if accepted_capabilities else 0., "providers": ",".join(sorted({provider for provider, capabilities in accepted_capabilities if getattr(capabilities, capability)}))})
    capability_df = pd.DataFrame(capability_rows)
    group = ["provider", "capability_signature", "metric_family", "metric", "possession_status", "tactical_phase", "required_capabilities"]
    if value_df.empty:
        summary = pd.DataFrame(columns=group + ["median_across_matches", "q25_across_matches", "q75_across_matches", "contributing_matches", "match_ids", "evidence_band", "baseline_label"])
        deviations = pd.DataFrame(columns=list(value_df.columns) + ["team_baseline", "deviation_from_baseline", "deviation_label", "contributing_matches", "evidence_band", "baseline_label", "comparison_label"])
    else:
        summary = value_df.groupby(group, dropna=False).agg(median_across_matches=("value", "median"), q25_across_matches=("value", lambda x: x.quantile(.25)), q75_across_matches=("value", lambda x: x.quantile(.75)), contributing_matches=("match_id", "nunique"), match_ids=("match_id", lambda x: tuple(sorted(set(x))))).reset_index()
        summary["evidence_band"] = summary.contributing_matches.map(profile_evidence_band)
        summary["baseline_label"] = summary.contributing_matches.map(profile_baseline_label)
        deviations = value_df.copy()
        deviations["team_baseline"] = value_df.groupby(group, dropna=False)["value"].transform("median")
        deviations["contributing_matches"] = value_df.groupby(group, dropna=False)["match_id"].transform("nunique")
        deviations["evidence_band"] = deviations.contributing_matches.map(profile_evidence_band)
        deviations["baseline_label"] = deviations.contributing_matches.map(profile_baseline_label)
        deviations["deviation_from_baseline"] = deviations.value - deviations.team_baseline
        deviations["deviation_label"] = [_deviation_label(metric, delta) for metric, delta in zip(deviations.metric, deviations.deviation_from_baseline)]
        deviations["comparison_label"] = [f"Match {match_id} vs {label}" for match_id, label in zip(deviations.match_id, deviations.baseline_label)]
    family_df = pd.DataFrame(family_rows, columns=["match_id", "provider", "finding_family"])
    recurring = (family_df.groupby(["provider", "finding_family"]).agg(contributing_matches=("match_id", "nunique"), finding_count=("finding_family", "size"), match_ids=("match_id", lambda x: tuple(sorted(set(x))))).reset_index() if not family_df.empty else pd.DataFrame(columns=["provider", "finding_family", "contributing_matches", "finding_count", "match_ids"]))
    recurring = recurring.loc[recurring.contributing_matches.ge(2)].reset_index(drop=True)
    return TeamProfileResult(identity, included_df, excluded_df, capability_df, periods_df, value_df, summary, deviations, recurring)
