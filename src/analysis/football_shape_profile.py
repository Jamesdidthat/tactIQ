"""Football-first team shape descriptions from compatible tracking profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .team_profile import TeamProfileResult


@dataclass(frozen=True)
class ShapeFrameReference:
    match_id: str | int
    frame: int
    period: int
    label: str
    highlight: str
    clip_before_seconds: float
    clip_after_seconds: float
    clip_reason: str


@dataclass(frozen=True)
class ShapeConceptEvidence:
    metric: str
    metric_label: str
    median_metres: float
    q25_metres: float
    q75_metres: float
    contributing_matches: int
    tracked_frame_count: int
    possession_status: str | None
    tactical_phase: str | None
    provider: str
    required_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class FootballShapeConcept:
    concept_id: str
    headline: str
    explanation: str
    what_this_looks_like: str
    evidence_basis: str
    evidence: tuple[ShapeConceptEvidence, ...]
    representative_frames: tuple[ShapeFrameReference, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class FootballShapeProfile:
    schema_version: str
    available: bool
    availability_message: str
    team_id: str | int
    team_name: str
    provider: str | None
    source_label: str
    with_ball: tuple[FootballShapeConcept, ...]
    without_ball: tuple[FootballShapeConcept, ...]
    transitions: tuple[FootballShapeConcept, ...]
    unsupported_concepts: tuple[str, ...]
    limitations: tuple[str, ...]


LABELS = {
    "outfield_width": "Outfield width", "outfield_length": "Back-to-front team length",
    "outfield_tactical_centroid_x": "Overall team position",
    "defence_tactical_median_x": "Defensive-line position", "midfield_tactical_median_x": "Midfield-line position",
    "defence_to_midfield_gap": "Defence-to-midfield distance", "midfield_to_attack_gap": "Midfield-to-attack distance",
    "total_outfield_length": "Overall back-to-front distance",
}


def _basis(count: int) -> str:
    return "Established" if count >= 10 else "Developing" if count >= 5 else "Provisional" if count >= 3 else "Limited"


def _row(profile: TeamProfileResult, provider: str, family: str, metric: str, status: str | None = None, phase: str | None = None) -> pd.Series | None:
    rows = profile.aggregate_patterns.loc[
        profile.aggregate_patterns.provider.eq(provider)
        & profile.aggregate_patterns.metric_family.eq(family)
        & profile.aggregate_patterns.metric.eq(metric)
    ]
    if status is not None:
        rows = rows.loc[rows.possession_status.eq(status)]
    if phase is not None:
        rows = rows.loc[rows.tactical_phase.eq(phase)]
    return None if rows.empty else rows.sort_values(["contributing_matches"], ascending=False, kind="stable").iloc[0]


def _evidence(profile: TeamProfileResult, provider: str, family: str, metric: str, status: str | None = None, phase: str | None = None) -> ShapeConceptEvidence | None:
    row = _row(profile, provider, family, metric, status, phase)
    if row is None:
        return None
    samples = profile.match_level_values.loc[
        profile.match_level_values.provider.eq(provider)
        & profile.match_level_values.metric_family.eq(family)
        & profile.match_level_values.metric.eq(metric)
    ]
    if status is not None:
        samples = samples.loc[samples.possession_status.eq(status)]
    if phase is not None:
        samples = samples.loc[samples.tactical_phase.eq(phase)]
    return ShapeConceptEvidence(
        metric=metric, metric_label=LABELS[metric], median_metres=float(row.median_across_matches),
        q25_metres=float(row.q25_across_matches), q75_metres=float(row.q75_across_matches),
        contributing_matches=int(row.contributing_matches), tracked_frame_count=int(samples.sample_size.sum()),
        possession_status=None if pd.isna(row.possession_status) else str(row.possession_status),
        tactical_phase=None if pd.isna(row.tactical_phase) else str(row.tactical_phase),
        provider=provider, required_capabilities=tuple(str(row.required_capabilities).split(",")),
    )


def _review_window(concept_id: str) -> tuple[float, float, str]:
    """Declare enough surrounding time to inspect the stated geometry."""
    if concept_id == "attacking_phase_change":
        return 6.0, 6.0, "Compare whether the phase-specific shape is established before and after the evidence moment."
    if concept_id == "block_behaviour":
        return 8.0, 8.0, "A longer window is needed to see whether the defensive block spacing is maintained."
    if concept_id in {"defence_midfield_gap", "defensive_compactness", "defensive_line_height", "midfield_line_position"}:
        return 6.0, 6.0, "Review line movement around the evidence moment rather than judging one frozen position."
    if concept_id in {"in_possession_length", "in_possession_height"}:
        return 5.0, 5.0, "Review how the back-to-front structure develops around the evidence moment."
    return 4.0, 4.0, "Review whether the observed width persists around the evidence moment."


def _frames(profile: TeamProfileResult, provider: str, evidence: tuple[ShapeConceptEvidence, ...], highlight: str,
            clip_before_seconds: float, clip_after_seconds: float, clip_reason: str) -> tuple[ShapeFrameReference, ...]:
    choices = []
    for item in evidence:
        rows = profile.match_level_values.loc[
            profile.match_level_values.provider.eq(provider)
            & profile.match_level_values.metric.eq(item.metric)
            & profile.match_level_values.representative_frame.notna()
            & profile.match_level_values.representative_period.notna()
        ]
        if item.possession_status is not None:
            rows = rows.loc[rows.possession_status.eq(item.possession_status)]
        if item.tactical_phase is not None:
            rows = rows.loc[rows.tactical_phase.eq(item.tactical_phase)]
        for row in rows.sort_values(["sample_size", "match_id"], ascending=[False, True], kind="stable").itertuples(index=False):
            choices.append(ShapeFrameReference(
                row.match_id, int(row.representative_frame), int(row.representative_period),
                f"{item.tactical_phase.replace('_', ' ').title() if item.tactical_phase else 'Typical tracked shape'}",
                highlight, clip_before_seconds, clip_after_seconds, clip_reason,
            ))
    output, seen = [], set()
    for item in choices:
        key = (item.match_id, item.frame, item.period)
        if key not in seen:
            output.append(item); seen.add(key)
        if len(output) == 2:
            break
    return tuple(output)


def _concept(profile: TeamProfileResult, provider: str, concept_id: str, headline: str, explanation: str,
             looks: str, evidence: tuple[ShapeConceptEvidence | None, ...], highlight: str, *limitations: str) -> FootballShapeConcept | None:
    valid = tuple(item for item in evidence if item is not None)
    if not valid:
        return None
    clip_before, clip_after, clip_reason = _review_window(concept_id)
    return FootballShapeConcept(concept_id, headline, explanation, looks, _basis(min(item.contributing_matches for item in valid)),
                                valid, _frames(profile, provider, valid, highlight, clip_before, clip_after, clip_reason), tuple(limitations))


def _width_words(value: float) -> tuple[str, str]:
    if value >= 48: return "They make the pitch very wide with the ball.", "Players spread towards both touchlines, creating a broad attacking shape."
    if value >= 38: return "They use a balanced amount of width.", "Their attacking shape stretches the pitch without always occupying its full width."
    return "They tend to stay fairly narrow with the ball.", "Players remain closer to the centre instead of spreading across the full pitch."


def _length_words(value: float) -> tuple[str, str]:
    if value >= 38: return "Their shape can become stretched from back to front.", "The deepest and highest outfield players are often separated by a sizeable distance."
    if value <= 28: return "They keep their lines close from back to front.", "The outfield unit usually occupies a relatively short section of the pitch."
    return "Their back-to-front spacing is usually balanced.", "The team generally avoids becoming extremely short or heavily stretched."


def build_football_shape_profile(profile: TeamProfileResult) -> FootballShapeProfile:
    tracking = profile.capability_coverage.loc[profile.capability_coverage.capability.eq("has_continuous_tracking")]
    providers = sorted(profile.aggregate_patterns.loc[profile.aggregate_patterns.required_capabilities.astype(str).str.contains("has_continuous_tracking"), "provider"].unique())
    if tracking.empty or int(tracking.available_matches.iloc[0]) == 0 or not providers:
        return FootballShapeProfile("tactiq.football-shape-profile.v1", False, "Detailed team shape requires tracking data",
                                    profile.team_identity.team_id, profile.team_identity.team_name, None, "Tracking-derived structure", (), (), (),
                                    ("width", "defensive height", "compactness", "line movement in transitions"),
                                    ("No compatible continuous tracking is available for this team profile.",))
    provider = max(providers, key=lambda item: (profile.matches_included.provider.eq(item).sum(), item))
    limitations = []
    if len(providers) > 1:
        limitations.append(f"Shape evidence is shown for {provider} only so incompatible provider contexts are not pooled.")

    overall_width = _evidence(profile, provider, "overall_team_shape", "outfield_width")
    overall_length = _evidence(profile, provider, "overall_team_shape", "outfield_length")
    build_width = _evidence(profile, provider, "phase_team_shape", "outfield_width", "in_possession", "build_up")
    create_width = _evidence(profile, provider, "phase_team_shape", "outfield_width", "in_possession", "create")
    build_length = _evidence(profile, provider, "phase_team_shape", "outfield_length", "in_possession", "build_up")
    build_height = _evidence(profile, provider, "phase_defensive_line_structure", "outfield_tactical_centroid_x", "in_possession", "build_up")
    width_head, width_explain = _width_words((build_width or overall_width).median_metres) if (build_width or overall_width) else ("", "")
    length_head, length_explain = _length_words((build_length or overall_length).median_metres) if (build_length or overall_length) else ("", "")
    phase_change = None
    if build_width and create_width:
        difference = create_width.median_metres - build_width.median_metres
        if abs(difference) >= 4:
            action = "spread wider" if difference > 0 else "become narrower"
            phase_change = _concept(profile, provider, "attacking_phase_change", f"They {action} as attacks develop.",
                                    f"Their shape changes noticeably between early build-up and the stage where chances are being created.",
                                    "Compare where the widest players stand during early circulation and later attacking moves.",
                                    (build_width, create_width), "width")
    with_ball = tuple(item for item in (
        _concept(profile, provider, "in_possession_width", width_head, width_explain, "Look at the distance between the two widest outfield players.", (build_width or overall_width,), "width") if width_head else None,
        _concept(profile, provider, "in_possession_length", length_head, length_explain, "Look at the distance from the deepest outfield player to the highest one.", (build_length or overall_length,), "length") if length_head else None,
        _concept(profile, provider, "in_possession_height", "They position the team high up the pitch with the ball." if build_height and build_height.median_metres >= 5 else "Their possession shape starts from a deeper position." if build_height and build_height.median_metres <= -5 else "Their possession shape is built from around the middle of the pitch.", "This describes where the centre of the outfield unit sits during build-up, with both attacking directions placed on the same scale.", "Look at whether most of the outfield unit has moved into the attacking half or remains closer to its own goal.", (build_height,), "team_position") if build_height else None,
        phase_change,
    ) if item is not None)

    block_evidence = tuple(_evidence(profile, provider, "phase_defensive_line_structure", "total_outfield_length", "out_of_possession", phase) for phase in ("low_block", "medium_block", "high_block"))
    medium_defence = _evidence(profile, provider, "phase_defensive_line_structure", "defence_tactical_median_x", "out_of_possession", "medium_block")
    medium_midfield = _evidence(profile, provider, "phase_defensive_line_structure", "midfield_tactical_median_x", "out_of_possession", "medium_block")
    medium_gap = _evidence(profile, provider, "phase_defensive_line_structure", "defence_to_midfield_gap", "out_of_possession", "medium_block")
    medium_length = _evidence(profile, provider, "phase_defensive_line_structure", "total_outfield_length", "out_of_possession", "medium_block")
    without_ball = tuple(item for item in (
        _concept(profile, provider, "defensive_line_height", "Their defensive line holds a relatively high position." if medium_defence and medium_defence.median_metres >= -15 else "Their defensive line usually sits deeper.", "The back line's usual position is measured only while the team is defending in its middle block.", "Look at how far the back line stands from its own goal while the opposition has settled possession.", (medium_defence,), "defensive_line") if medium_defence else None,
        _concept(profile, provider, "midfield_line_position", "The midfield line holds a relatively high position." if medium_midfield and medium_midfield.median_metres >= -5 else "The midfield line usually drops into a deeper position.", "The midfield unit's usual position is measured during settled defending rather than inferred from event locations.", "Look at where the midfield line forms between the ball and the back line.", (medium_midfield,), "midfield_line") if medium_midfield else None,
        _concept(profile, provider, "defence_midfield_gap", "The defence and midfield usually stay close together." if medium_gap and medium_gap.median_metres <= 10 else "A larger space can appear between midfield and defence.", "This describes the vertical distance between the two defensive lines during the middle block.", "Look for the amount of playable space between the midfielders and defenders.", (medium_gap,), "defence_midfield_gap") if medium_gap else None,
        _concept(profile, provider, "defensive_compactness", "They defend in a compact block." if medium_length and medium_length.median_metres <= 30 else "Their defensive block can become stretched.", "The full outfield unit occupies a relatively short section of the pitch while defending." if medium_length and medium_length.median_metres <= 30 else "The front and back of the defensive unit are often separated by a larger distance.", "Look at the distance from the highest defender to the deepest defender while the opposition has the ball.", (medium_length,), "length") if medium_length else None,
        _concept(profile, provider, "block_behaviour", "Their spacing changes with the height of the defensive block.", "Low, middle and high blocks are kept separate so different defensive situations are not blended together.", "Compare how close the lines remain when the team drops deep, holds midfield, or defends higher.", block_evidence, "length") if sum(item is not None for item in block_evidence) >= 2 else None,
    ) if item is not None)

    unsupported = ["generic transition retreat/advance speed"]
    if not medium_defence: unsupported.append("defensive line height by defensive phase")
    if not medium_midfield: unsupported.append("midfield line position by defensive phase")
    return FootballShapeProfile("tactiq.football-shape-profile.v1", True, "Tracking-derived team shape is available",
                                profile.team_identity.team_id, profile.team_identity.team_name, provider, "Tracking-derived structure",
                                with_ball, without_ball, (), tuple(unsupported), tuple(limitations + [
                                    "Distances summarize observed player positions; they do not identify tactical intent.",
                                    "Transition speed is not described until a validated generic possession-change trajectory is available.",
                                ]))
