"""Bounded event-sequence detail for one representative historical moment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.data.canonical import CanonicalMatchBundle, validate_canonical_bundle

from .representative_moments import RepresentativeMoment
from .moment_360_context import Moment360Context, build_moment_360_context


SEQUENCE_EVENT_TYPES = frozenset({
    "Pass", "Carry", "Shot", "Dribble", "Ball Receipt*", "Interception",
    "Ball Recovery", "Miscontrol", "Dispossessed", "Clearance",
})
PITCH_RENDERABLE_TYPES = frozenset({"Pass", "Carry", "Shot", "Interception", "Ball Recovery"})


@dataclass(frozen=True)
class MomentSequenceEvent:
    event_id: str
    event_index: int
    relation_to_focal: str
    period: int
    minute: int
    second: int
    elapsed_seconds: float
    possession_id: int | str | None
    possession_team_id: int | str | None
    possession_team_name: str | None
    team_id: int | str | None
    team_name: str | None
    player_id: int | str | None
    event_type: str
    event_subtype: str | None
    outcome: str | None
    start_coordinates: tuple[float, float] | None
    end_coordinates: tuple[float, float] | None
    xg: float | None
    play_pattern: str | None
    coordinate_system: str
    is_focal: bool
    pitch_renderable: bool


@dataclass(frozen=True)
class RepresentativeMomentDetail:
    match_id: int
    event_id: str
    focal_event: MomentSequenceEvent
    sequence_events: tuple[MomentSequenceEvent, ...]
    context_mode: str
    possession_id: int | str | None
    possession_team_id: int | str | None
    possession_team_name: str | None
    score_state: str | None
    score_state_verified: bool
    score_state_team_id: int | str
    score_state_team_name: str
    phase_context: dict[str, Any] | None
    coordinate_system: str
    sequence_supported: bool
    source_provenance: dict[str, Any]
    video_availability_status: str
    moment_360_context: Moment360Context
    limitations: tuple[str, ...]


def _optional(value: Any) -> Any:
    return None if pd.isna(value) else value


def _coordinates(x: Any, y: Any) -> tuple[float, float] | None:
    if pd.isna(x) or pd.isna(y):
        return None
    return float(x), float(y)


def _team_name(bundle: CanonicalMatchBundle, team_id: Any) -> str | None:
    if pd.isna(team_id):
        return None
    rows = bundle.teams.loc[bundle.teams.team_id.eq(team_id)]
    return str(rows.iloc[0].team_name) if len(rows) == 1 else None


def _subtype(event: pd.Series) -> str | None:
    attributes = event.get("attributes")
    if isinstance(attributes, dict):
        detail = attributes.get(str(event.event_type).lower().replace(" ", "_"))
        if isinstance(detail, dict):
            for key in ("type", "technique", "body_part", "height"):
                value = detail.get(key)
                if isinstance(value, dict) and value.get("name"):
                    return str(value["name"])
    if event.event_type == "Shot" and pd.notna(event.get("shot_type")):
        return str(event.shot_type)
    if event.event_type == "Interception" and pd.notna(event.get("outcome")):
        return str(event.outcome)
    return None


def _outcome(event: pd.Series) -> str | None:
    if event.event_type == "Pass":
        return "Complete" if pd.isna(event.get("pass_outcome")) else str(event.pass_outcome)
    if event.event_type == "Carry":
        return "Recorded"
    if event.event_type == "Shot":
        return None if pd.isna(event.get("shot_outcome")) else str(event.shot_outcome)
    return None if pd.isna(event.get("outcome")) else str(event.outcome)


def _sequence_event(bundle: CanonicalMatchBundle, event: pd.Series, focal_index: int) -> MomentSequenceEvent:
    index = int(event.event_index)
    relation = "focal" if index == focal_index else "previous" if index < focal_index else "next"
    possession_team_id = _optional(event.get("possession_team_id"))
    team_id = _optional(event.get("team_id"))
    event_type = str(event.event_type)
    return MomentSequenceEvent(
        event_id=str(event.event_id), event_index=index, relation_to_focal=relation,
        period=int(event.period), minute=int(event.minute), second=int(event.second),
        elapsed_seconds=float(event.elapsed_seconds), possession_id=_optional(event.get("possession_id")),
        possession_team_id=possession_team_id,
        possession_team_name=_team_name(bundle, possession_team_id),
        team_id=team_id, team_name=_team_name(bundle, team_id), player_id=_optional(event.get("player_id")),
        event_type=event_type, event_subtype=_subtype(event), outcome=_outcome(event),
        start_coordinates=_coordinates(event.get("location_x"), event.get("location_y")),
        end_coordinates=_coordinates(event.get("end_location_x"), event.get("end_location_y")),
        xg=None if pd.isna(event.get("shot_xg")) else float(event.shot_xg),
        play_pattern=None if pd.isna(event.get("play_pattern")) else str(event.play_pattern),
        coordinate_system=str(event.coordinate_system), is_focal=index == focal_index,
        pitch_renderable=event_type in PITCH_RENDERABLE_TYPES and _coordinates(event.get("location_x"), event.get("location_y")) is not None,
    )


def build_representative_moment_detail(
    moment: RepresentativeMoment,
    bundle: CanonicalMatchBundle,
    *,
    before_seconds: float = 10.0,
    after_seconds: float = 3.0,
    maximum_previous_events: int = 6,
    include_next_event: bool = True,
) -> RepresentativeMomentDetail:
    """Build ordered context without crossing a known possession boundary."""
    validate_canonical_bundle(bundle)
    if int(bundle.matches.match_id.iloc[0]) != int(moment.match_id):
        raise ValueError("Representative moment and canonical bundle match IDs differ.")
    if bundle.events is None:
        raise ValueError("Representative moment detail requires canonical events.")
    if before_seconds < 0 or after_seconds < 0 or maximum_previous_events < 0:
        raise ValueError("Sequence bounds must be non-negative.")
    matches = bundle.events.loc[bundle.events.event_id.astype(str).eq(str(moment.event_id))]
    if len(matches) != 1:
        raise KeyError(f"Focal event {moment.event_id!r} is absent or ambiguous.")
    focal = matches.iloc[0]
    ordered = bundle.events.loc[bundle.events.period.eq(focal.period)].sort_values("event_index", kind="stable")
    possession_id = _optional(focal.get("possession_id"))
    linked_ids = tuple(str(item) for item in moment.relevant_values.get("linked_sequence_event_ids", ()))
    if moment.family == "turnover_to_shot" and linked_ids:
        context_mode = "turnover_to_shot_window"
        context = ordered.loc[ordered.event_id.astype(str).isin(linked_ids)]
    elif possession_id is not None:
        context_mode = "same_possession"
        context = ordered.loc[ordered.possession_id.eq(possession_id)]
    else:
        context_mode = "bounded_time_window"
        lower = float(focal.elapsed_seconds) - before_seconds
        upper = float(focal.elapsed_seconds) + after_seconds
        context = ordered.loc[ordered.elapsed_seconds.between(lower, upper, inclusive="both")]
    if context_mode == "turnover_to_shot_window":
        sequence = context.drop_duplicates("event_id").sort_values("event_index", kind="stable")
    else:
        relevant = context.loc[context.event_type.isin(SEQUENCE_EVENT_TYPES) | context.event_id.astype(str).eq(str(moment.event_id))]
        previous = relevant.loc[relevant.event_index.lt(focal.event_index)].tail(maximum_previous_events)
        following = relevant.loc[relevant.event_index.gt(focal.event_index)].head(1 if include_next_event else 0)
        sequence = pd.concat([previous, matches, following]).drop_duplicates("event_id").sort_values("event_index", kind="stable")
    sequence_events = tuple(_sequence_event(bundle, event, int(focal.event_index)) for _, event in sequence.iterrows())
    focal_event = next(event for event in sequence_events if event.is_focal)
    possession_team_id = _optional(focal.get("possession_team_id"))
    play_pattern = None if pd.isna(focal.get("play_pattern")) else str(focal.play_pattern)
    phase_context = ({
        "label": play_pattern,
        "source": "statsbomb_event_play_pattern",
        "interpretation": "Provider event play pattern; not a tracking-derived tactical phase.",
    } if play_pattern else None)
    sequence_supported = focal_event.event_type in SEQUENCE_EVENT_TYPES
    limitations = [
        "This view contains event locations only and does not reconstruct player positions, defensive shape, passing lanes, pressure, or off-ball movement.",
        "StatsBomb 360 snapshots are not used as continuous tracking.",
    ]
    if not sequence_supported:
        limitations.append(f"Sequence visualization is unsupported for focal event type {focal_event.event_type!r}.")
    if any(event.start_coordinates is None for event in sequence_events):
        limitations.append("Events with unavailable coordinates remain in the timeline but are not positioned on the pitch.")
    return RepresentativeMomentDetail(
        match_id=moment.match_id, event_id=moment.event_id, focal_event=focal_event,
        sequence_events=sequence_events, context_mode=context_mode, possession_id=possession_id,
        possession_team_id=possession_team_id, possession_team_name=_team_name(bundle, possession_team_id),
        score_state=moment.score_state, score_state_verified=moment.score_state_verified,
        score_state_team_id=moment.score_state_team_id, score_state_team_name=moment.score_state_team_name,
        phase_context=phase_context, coordinate_system="statsbomb_120x80", sequence_supported=sequence_supported,
        source_provenance={
            "provider": bundle.provider, "source_table": "canonical_events",
            "event_ids_preserved": True, "context_mode": context_mode,
            "before_seconds": before_seconds, "after_seconds": after_seconds,
            "maximum_previous_events": maximum_previous_events,
        },
        video_availability_status=moment.video_availability_status,
        moment_360_context=build_moment_360_context(moment, bundle),
        limitations=tuple(limitations),
    )
