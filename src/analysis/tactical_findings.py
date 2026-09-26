"""Deterministic, capability-aware descriptive tactical findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

import pandas as pd

from src.data import CanonicalMatchBundle, supported_analyses
from src.data.phase_context import expand_phase_context, join_phase_context_to_team_shape
from src.metrics import calculate_defensive_line_structure, calculate_local_defensive_context, calculate_team_shape

from .phase_shape import summarize_phase_shape
from .phase_shape_evidence import INTERVAL_KEY, PHASE_NAMES, dimension_distinction, quartile_moments
from .team_shape_evidence import select_typical_and_extreme_moments


CONFIDENCE_LEVELS = {"descriptive_low", "descriptive_moderate"}


@dataclass(frozen=True)
class TacticalFinding:
    """A deterministic observation with transparent evidence and constraints."""

    finding_id: str
    match_id: str | int
    team_id: str | int
    finding_type: str
    title: str
    description: str
    evidence_metrics: Mapping[str, float | int | str]
    sample_size: int
    confidence_level: str
    supporting_references: tuple[Mapping[str, Any], ...]
    required_capabilities: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.finding_id or not self.finding_type or not self.title or not self.description:
            raise ValueError("A TacticalFinding requires non-empty identity, type, title, and description.")
        if self.sample_size < 1:
            raise ValueError("A TacticalFinding sample_size must be positive.")
        if self.confidence_level not in CONFIDENCE_LEVELS:
            raise ValueError(f"Unsupported confidence level: {self.confidence_level}")
        if not self.evidence_metrics or not self.required_capabilities:
            raise ValueError("A TacticalFinding requires evidence metrics and required capabilities.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatchAnalysisResult:
    """Structured deterministic analysis output for one canonical match bundle."""

    findings: list[TacticalFinding]
    analysis_coverage: pd.DataFrame
    warnings: list[str]
    metadata: dict[str, Any]


def _confidence(sample_size: int, *, moderate_at: int) -> str:
    return "descriptive_moderate" if sample_size >= moderate_at else "descriptive_low"


def _references(rows: pd.DataFrame, maximum: int = 3) -> tuple[Mapping[str, Any], ...]:
    columns = [column for column in ("frame", "period", "elapsed_seconds", "timestamp", "phase_frame_start", "phase_frame_end") if column in rows]
    return tuple(rows[columns].head(maximum).to_dict("records"))


def _team_display_name(name: str) -> str:
    """Keep official identity while avoiding a cumbersome generic suffix."""
    return name.removesuffix(" Football Club").strip()


def generate_team_shape_extreme_findings(
    shape: pd.DataFrame,
    *,
    match_id: str | int,
    team_names: Mapping[str | int, str] | None = None,
) -> list[TacticalFinding]:
    """Describe typical shape beside a distinct high-tail shape episode."""
    rows = shape.reset_index()
    findings: list[TacticalFinding] = []
    for (team_id, acronym), group in rows.groupby(["team_id", "team_acronym"], dropna=False):
        team_label = _team_display_name(str((team_names or {}).get(team_id) or acronym))
        for metric, dimension, behavior, threshold in (
            ("outfield_length", "outfield length", "typical and more extended shapes", 30.0),
            ("outfield_width", "outfield width", "typical and wider shapes", 25.0),
        ):
            available = group.dropna(subset=[metric])
            if len(available) < 20:
                continue
            evidence = select_typical_and_extreme_moments(available, metric)
            if evidence is None or evidence["q95_metres"] < threshold:
                continue
            exact_metrics = {
                "dimension": metric.removeprefix("outfield_"),
                "median_metres": evidence["median_metres"],
                "q95_metres": evidence["q95_metres"],
                "extreme_metres": evidence["extreme_metres"],
                # Retain the old key in the stable API while moving product copy
                # and evidence to the explicit typical-versus-extreme language.
                "peak_metres": evidence["extreme_metres"],
                "absolute_deviation_from_median_metres": evidence["absolute_deviation_from_median_metres"],
                "extreme_episode_count": evidence["extreme_episode_count"],
                "evidence_context_separation": evidence["evidence_context_separation"],
                "extreme_period": evidence["extreme_period"],
                "threshold_metres": threshold,
                "frame_count": len(available),
                "sample_unit": "tracked frames",
            }
            if pd.notna(evidence["extreme_timestamp"]):
                exact_metrics["extreme_timestamp"] = evidence["extreme_timestamp"]
            if pd.notna(evidence["extreme_tactical_phase"]):
                exact_metrics["extreme_tactical_phase"] = evidence["extreme_tactical_phase"]
            findings.append(TacticalFinding(
                finding_id=f"{match_id}:{team_id}:shape_extreme:{metric}", match_id=match_id, team_id=team_id,
                finding_type="team_shape_extreme", title=f"{team_label} {dimension}: {behavior}",
                description=(
                    f"{team_label}'s median {dimension} was {evidence['median_metres']:.1f} m. "
                    f"In a high-tail episode it reached {evidence['extreme_metres']:.1f} m, "
                    f"{evidence['absolute_deviation_from_median_metres']:.1f} m from the median."
                ),
                evidence_metrics=exact_metrics,
                sample_size=len(available), confidence_level=_confidence(len(available), moderate_at=500),
                supporting_references=evidence["references"], required_capabilities=("has_continuous_tracking", "has_verified_roles"),
                limitations=(
                    "Native pitch coordinates only; this describes shape geometry, not tactical quality or causation.",
                    "The extreme example represents one contiguous high-tail episode; adjacent frames are not independent examples.",
                ),
            ))
    return findings


def generate_phase_shape_findings(
    phase_summary: pd.DataFrame, phase_rows: pd.DataFrame, *, match_id: str | int
) -> list[TacticalFinding]:
    """Describe each dimension with faithful, distinct-interval evidence."""
    findings: list[TacticalFinding] = []
    for item in phase_summary.itertuples(index=False):
        width_iqr = float(item.q75_outfield_width - item.q25_outfield_width)
        length_iqr = float(item.q75_outfield_length - item.q25_outfield_length)
        if item.frame_count < 50 or max(width_iqr, length_iqr) < 8.0:
            continue
        selected = phase_rows.loc[
            phase_rows.team_id.eq(item.team_id)
            & phase_rows.possession_status.eq(item.possession_status)
            & phase_rows.tactical_phase.eq(item.tactical_phase)
        ]
        distinction = dimension_distinction(selected)
        for dimension in ('width', 'length'):
            metric = f'outfield_{dimension}'
            available = selected.dropna(subset=[metric, *INTERVAL_KEY])
            q25, median, q75 = available[metric].quantile([.25, .5, .75]).tolist()
            if len(available) < 50 or q75 - q25 < 8.:
                continue
            references = quartile_moments(available, dimension)
            if not references:
                continue
            count = len(available[INTERVAL_KEY].drop_duplicates())
            phase = PHASE_NAMES.get(item.tactical_phase, str(item.tactical_phase).replace('_', ' '))
            behavior = 'narrower and wider shapes' if dimension == 'width' else 'shorter and longer shapes'
            findings.append(TacticalFinding(
                finding_id=f"{match_id}:{item.team_id}:phase_shape:{item.possession_status}:{item.tactical_phase}:{dimension}",
                match_id=match_id, team_id=item.team_id, finding_type="phase_shape_variability",
                title=f"{item.team_acronym} {dimension} during {phase}: {behavior}",
                description=f"During {phase}, {item.team_acronym}'s outfield {dimension} was between {q25:.1f} and {q75:.1f} m in the middle half of tracked frames, with a median of {median:.1f} m across {count} phase intervals.",
                evidence_metrics={'dimension': dimension, 'tactical_phase': item.tactical_phase, 'possession_status': item.possession_status,
                    'q25_metres': q25, 'median_metres': median, 'q75_metres': q75, 'iqr_metres': q75-q25,
                    'phase_intervals': count, 'frame_count': len(available), 'sample_unit': 'phase intervals',
                    'aggregation': 'frame-weighted quartiles', **distinction},
                sample_size=count, confidence_level=_confidence(count, moderate_at=10),
                supporting_references=references, required_capabilities=("has_continuous_tracking", "has_verified_roles", "has_tactical_phases"),
                limitations=("Provider-supplied phase labels; variation alone does not establish tactical quality or causation.",
                    "Quartiles are frame weighted, so longer intervals contribute more frames. Examples are snapshots from three distinct intervals, not a sequence.",
                    "Width/length separation uses an exploratory interval-rank rule, not statistical significance."),
            ))
    return findings


def generate_shot_local_context_findings(
    bundle: CanonicalMatchBundle, *, max_shots: int = 200
) -> tuple[list[TacticalFinding], str | None]:
    """Describe local defending context at available opponent-shot frames."""
    shots = bundle.events.loc[bundle.events.is_shot.eq(True)].head(max_shots).copy() if bundle.events is not None else pd.DataFrame()
    if shots.empty or "frame_end" not in shots or shots.frame_end.isna().all():
        return [], "No canonical shot frames were available for local-context snapshots."
    event_frames = shots.dropna(subset=["frame_end"])[["frame_end", "period"]].rename(columns={"frame_end": "frame"})
    players = bundle.player_positions.merge(event_frames.drop_duplicates(), on=["frame", "period"], how="inner")
    balls = bundle.ball_positions.merge(event_frames.drop_duplicates(), on=["frame", "period"], how="inner")
    if players.empty or balls.empty:
        return [], "No player/ball tracking aligned to canonical shot frames."
    lines = calculate_defensive_line_structure(players, bundle.match_info)
    local = calculate_local_defensive_context(players, balls, lines, bundle.match_info)
    attackers = shots[["frame_end", "period", "team_id"]].rename(columns={"frame_end": "frame", "team_id": "attacking_team_id"})
    defending = local.merge(attackers, on=["frame", "period"], how="inner")
    defending = defending.loc[defending.team_id.ne(defending.attacking_team_id)].dropna(subset=["nearest_defender_distance"])
    findings: list[TacticalFinding] = []
    for (team_id, acronym), group in defending.groupby(["team_id", "team_acronym"], dropna=False):
        if len(group) < 3:
            continue
        median = float(group.nearest_defender_distance.median())
        if median < 3.0:
            continue
        findings.append(TacticalFinding(
            finding_id=f"{bundle.matches.match_id.iloc[0]}:{team_id}:shot_local_context", match_id=bundle.matches.match_id.iloc[0], team_id=team_id,
            finding_type="shot_local_context", title=f"{acronym} opponent-shot nearest-defender distance",
            description=f"At aligned opponent-shot frames, median nearest-defender distance to the ball was {median:.1f} m.",
            evidence_metrics={"median_nearest_defender_distance_metres": median, "q25_metres": float(group.nearest_defender_distance.quantile(.25)), "q75_metres": float(group.nearest_defender_distance.quantile(.75)), "threshold_metres": 3.0},
            sample_size=len(group), confidence_level=_confidence(len(group), moderate_at=15), supporting_references=_references(group.sort_values("nearest_defender_distance", ascending=False)),
            required_capabilities=("has_continuous_tracking", "has_ball_tracking", "has_verified_roles", "has_attacking_direction", "has_events"),
            limitations=("Shot events and frames are provider supplied; snapshots do not establish causation or possession identity.",),
        ))
    return findings, None


def generate_shot_sequence_findings(bundle: CanonicalMatchBundle) -> tuple[list[TacticalFinding], str | None]:
    """Describe observed same-team event density before shots without classifying mechanisms."""
    if bundle.events is None or "frame_end" not in bundle.events:
        return [], "Canonical events lack frame_end, so shot-sequence density cannot be described."
    events = bundle.events.dropna(subset=["frame_end"]).copy()
    time_lookup = bundle.player_positions[["frame", "period", "elapsed_seconds", "timestamp"]].drop_duplicates(["frame", "period"]).set_index(["frame", "period"])
    shots = events.loc[events.is_shot.eq(True)]
    if shots.empty:
        return [], "No canonical shot events were available for sequence analysis."
    rows = []
    for shot in shots.itertuples(index=False):
        prior = events.loc[
            events.team_id.eq(shot.team_id) & events.period.eq(shot.period)
            & events.frame_end.lt(shot.frame_end) & events.frame_end.ge(shot.frame_end - 100)
        ]
        timing = time_lookup.loc[(shot.frame_end, shot.period)] if (shot.frame_end, shot.period) in time_lookup.index else None
        rows.append({"team_id": shot.team_id, "frame": shot.frame_end, "period": shot.period, "elapsed_seconds": timing.elapsed_seconds if timing is not None else pd.NA, "timestamp": timing.timestamp if timing is not None else pd.NA, "preceding_event_count": len(prior)})
    sequences = pd.DataFrame(rows)
    findings = []
    for team_id, group in sequences.groupby("team_id"):
        if len(group) < 3:
            continue
        median = float(group.preceding_event_count.median())
        if median < 3:
            continue
        team_code = bundle.teams.loc[bundle.teams.team_id.eq(team_id), "team_code"].iloc[0]
        findings.append(TacticalFinding(
            finding_id=f"{bundle.matches.match_id.iloc[0]}:{team_id}:shot_sequence_density", match_id=bundle.matches.match_id.iloc[0], team_id=team_id,
            finding_type="shot_sequence_density", title=f"{team_code} dense pre-shot event sequences",
            description=f"In the available event feed, the median shot had {median:.0f} same-team events ending in its preceding 10 seconds.",
            evidence_metrics={"median_preceding_events": median, "q25_preceding_events": float(group.preceding_event_count.quantile(.25)), "q75_preceding_events": float(group.preceding_event_count.quantile(.75)), "window_seconds": 10},
            sample_size=len(group), confidence_level=_confidence(len(group), moderate_at=15), supporting_references=_references(group),
            required_capabilities=("has_continuous_tracking", "has_events", "has_tactical_phases"),
            limitations=("Event density is not a possession reconstruction and does not classify shot-creation mechanisms or establish causation.",),
        ))
    return findings, None


def run_match_analysis(bundle: CanonicalMatchBundle, *, allow_assumed_roles: bool = False) -> MatchAnalysisResult:
    """Run only capability-supported deterministic modules for one match."""
    coverage = supported_analyses(bundle, allow_assumed_roles=allow_assumed_roles).copy()
    coverage["status"] = coverage.supported.map({True: "available_not_implemented", False: "skipped"})
    coverage["finding_count"] = 0
    warnings = [f"{row.analysis} skipped: {row.reason}" for row in coverage.loc[~coverage.supported].itertuples(index=False)]
    findings: list[TacticalFinding] = []
    match_id = bundle.matches.match_id.iloc[0]

    team_shape_supported = bool(coverage.loc[coverage.analysis.eq("team_shape"), "supported"].iloc[0])
    phase_shape_supported = bool(coverage.loc[coverage.analysis.eq("phase_shape_analysis"), "supported"].iloc[0])
    shape = calculate_team_shape(bundle.player_positions) if team_shape_supported or phase_shape_supported else None
    joined_shape = None
    if phase_shape_supported and "phases" in bundle.raw:
        context = expand_phase_context(bundle.raw["phases"], bundle.match_info)
        joined_shape = join_phase_context_to_team_shape(shape, context, bundle.match_info)

    if team_shape_supported:
        team_names = {
            team["id"]: team.get("name") or team.get("acronym") or str(team["id"])
            for team in (bundle.match_info.get("home_team", {}), bundle.match_info.get("away_team", {}))
            if "id" in team
        }
        generated = generate_team_shape_extreme_findings(
            joined_shape if joined_shape is not None else shape,
            match_id=match_id,
            team_names=team_names,
        )
        findings.extend(generated)
        index = coverage.analysis.eq("team_shape")
        coverage.loc[index, ["status", "finding_count"]] = ["run", len(generated)]
    if phase_shape_supported:
        if "phases" not in bundle.raw:
            warnings.append("phase_shape_analysis skipped: raw provider phase table is unavailable for the current interval adapter.")
        else:
            summary = summarize_phase_shape(joined_shape)
            generated = generate_phase_shape_findings(summary, joined_shape.reset_index(), match_id=match_id)
            findings.extend(generated)
            index = coverage.analysis.eq("phase_shape_analysis")
            coverage.loc[index, ["status", "finding_count"]] = ["run", len(generated)]
    if bool(coverage.loc[coverage.analysis.eq("local_defensive_context"), "supported"].iloc[0]) and bundle.capabilities.has_events:
        generated, warning = generate_shot_local_context_findings(bundle)
        findings.extend(generated)
        if warning:
            warnings.append(warning)
        index = coverage.analysis.eq("local_defensive_context")
        coverage.loc[index, ["status", "finding_count"]] = ["run", len(generated)]
    elif bundle.capabilities.has_events:
        warnings.append("shot_local_context skipped: local defensive context prerequisites are unavailable.")
    if bool(coverage.loc[coverage.analysis.eq("temporal_shot_analysis"), "supported"].iloc[0]):
        generated, warning = generate_shot_sequence_findings(bundle)
        findings.extend(generated)
        if warning:
            warnings.append(warning)
        index = coverage.analysis.eq("temporal_shot_analysis")
        coverage.loc[index, ["status", "finding_count"]] = ["run", len(generated)]

    return MatchAnalysisResult(
        findings=findings, analysis_coverage=coverage,
        warnings=warnings,
        metadata={"match_id": match_id, "provider": bundle.provider, "capabilities": bundle.capabilities, "allow_assumed_roles": allow_assumed_roles},
    )
