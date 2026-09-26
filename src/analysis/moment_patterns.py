"""Explicit event-only patterns across representative historical moments."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import hypot
from typing import Any, Mapping, Sequence

from .event_team_profile import GOAL_CENTRE, HIGH_REGAIN_X, PENALTY_AREA_Y, SET_PLAY_PATTERNS, SET_PLAY_SHOT_TYPES
from .representative_moment_detail import RepresentativeMomentDetail
from .representative_moments import RepresentativeMoment


ENTRY_FAMILIES = frozenset({"penalty_area_entries", "final_third_entries"})
SHOT_FAMILIES = frozenset({"shots", "xg", "xg_per_shot", "counter_attacks", "set_play_shots"})
DEFENSIVE_FAMILIES = frozenset({"interceptions", "high_regains"})
CENTRAL_SHOT_Y = (24.0, 56.0)


@dataclass(frozen=True)
class MomentPattern:
    pattern_id: str
    pattern_key: str
    pattern_name: str
    deterministic_definition: str
    priority_id: str
    relevant_metrics: tuple[str, ...]
    moment_count: int
    eligible_moment_count: int
    share_of_eligible_moments: float
    contributing_matches: tuple[int, ...]
    representative_moment_ids: tuple[str, ...]
    coordinate_event_field_evidence: dict[str, Any]
    limitations: tuple[str, ...]
    capability_provenance: dict[str, Any]


@dataclass(frozen=True)
class MomentPatternAssignment:
    event_id: str
    match_id: int
    pattern_ids: tuple[str, ...]
    pattern_keys: tuple[str, ...]


@dataclass(frozen=True)
class MomentPatternResult:
    priority_id: str
    eligible_moment_count: int
    patterns: tuple[MomentPattern, ...]
    assignments: tuple[MomentPatternAssignment, ...]
    limitations: tuple[str, ...]


_DEFINITIONS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "wide_pass_entry": ("Wide pass entry", "A completed pass entry whose end y-coordinate is outside the central 18–62 band.", {"fields": ["event_type", "end_coordinates"], "central_entry_y": [18.0, 62.0]}),
    "central_pass_entry": ("Central pass entry", "A completed pass entry whose end y-coordinate is inside the inclusive central 18–62 band.", {"fields": ["event_type", "end_coordinates"], "central_entry_y_inclusive": [18.0, 62.0]}),
    "carry_entry": ("Carry entry", "An entry recorded by StatsBomb as a Carry event.", {"fields": ["event_type"]}),
    "set_play_origin_entry": ("Set-play-origin entry", "An entry whose StatsBomb play_pattern is one of the configured set-play patterns.", {"fields": ["play_pattern"], "accepted_values": sorted(SET_PLAY_PATTERNS)}),
    "explicit_counter_entry": ("Explicit counter entry", "An entry whose StatsBomb play_pattern is explicitly From Counter.", {"fields": ["play_pattern"], "accepted_values": ["From Counter"]}),
    "open_play_shot": ("Open-play shot", "A shot not explicitly classified as a set play or From Counter by the available StatsBomb fields.", {"fields": ["event_type", "play_pattern", "shot_type"]}),
    "set_play_shot": ("Set-play shot", "A shot with a configured set-play play_pattern or set-play shot_type.", {"fields": ["play_pattern", "shot_type"], "play_patterns": sorted(SET_PLAY_PATTERNS), "shot_types": sorted(SET_PLAY_SHOT_TYPES)}),
    "explicit_counter_attack_shot": ("Explicit counter-attack shot", "A shot whose StatsBomb play_pattern is explicitly From Counter.", {"fields": ["play_pattern"], "accepted_values": ["From Counter"]}),
    "central_shot_location": ("Central shot location", "A shot starting inside the inclusive central y-coordinate band 24–56.", {"fields": ["start_coordinates"], "central_shot_y_inclusive": [24.0, 56.0]}),
    "wide_angle_shot_location": ("Wide-angle shot location", "A shot starting outside the central y-coordinate band 24–56; this is a location proxy, not a calculated goal angle.", {"fields": ["start_coordinates"], "central_shot_y": [24.0, 56.0]}),
    "higher_xg_shot": ("Higher-xG shot", "A shot whose xG is at or above that evidence-side team-season's median shot xG.", {"fields": ["xg", "team_season_shot_xg_distribution.median"]}),
    "lower_xg_shot": ("Lower-xG shot", "A shot whose xG is below that evidence-side team-season's median shot xG.", {"fields": ["xg", "team_season_shot_xg_distribution.median"]}),
    "interception": ("Interception", "A representative event recorded as an Interception.", {"fields": ["event_type"]}),
    "recovery": ("Recovery", "A representative event recorded as a Ball Recovery.", {"fields": ["event_type"]}),
    "high_zone_regain": ("High-zone regain", "A recovery or interception with native StatsBomb start x at or beyond 80.", {"fields": ["event_type", "start_coordinates"], "minimum_x_inclusive": HIGH_REGAIN_X}),
    "immediate_same_possession_progression": ("Immediate same-possession progression", "The next relevant same-team event in the same possession is a pass/carry advancing at least 10 native x units and reducing goal distance by at least 25%.", {"fields": ["possession_id", "team_id", "event_type", "start_coordinates", "end_coordinates"], "minimum_x_gain": 10.0, "maximum_goal_distance_ratio": 0.75}),
}


def _pattern_id(priority_id: str, pattern_key: str) -> str:
    digest = sha256(f"{priority_id}|{pattern_key}".encode("utf-8")).hexdigest()[:14]
    return f"moment-pattern-{digest}"


def _shot_distribution(moment: RepresentativeMoment) -> Mapping[str, Any] | None:
    value = moment.relevant_values.get("team_season_shot_xg_distribution")
    return value if isinstance(value, Mapping) else None


def _is_immediate_progression(detail: RepresentativeMomentDetail | None) -> bool:
    if detail is None:
        return False
    focal = detail.focal_event
    following = [event for event in detail.sequence_events if event.relation_to_focal == "next"]
    if len(following) != 1:
        return False
    event = following[0]
    if (
        focal.possession_id is None or event.possession_id != focal.possession_id
        or focal.team_id is None or event.team_id != focal.team_id
        or event.event_type not in {"Pass", "Carry"}
        or event.start_coordinates is None or event.end_coordinates is None
    ):
        return False
    start_x, start_y = event.start_coordinates
    end_x, end_y = event.end_coordinates
    start_goal_distance = hypot(GOAL_CENTRE[0] - start_x, GOAL_CENTRE[1] - start_y)
    end_goal_distance = hypot(GOAL_CENTRE[0] - end_x, GOAL_CENTRE[1] - end_y)
    return end_x - start_x >= 10.0 and end_goal_distance <= start_goal_distance * 0.75


def classify_moment_patterns(
    moment: RepresentativeMoment,
    detail: RepresentativeMomentDetail | None = None,
) -> tuple[str, ...]:
    """Return deterministic, potentially multi-label pattern keys for one moment."""
    keys: list[str] = []
    values = moment.relevant_values
    start = values.get("start_coordinates")
    end = values.get("end_coordinates")
    play_pattern = values.get("play_pattern")
    shot_type = values.get("shot_type")

    if moment.family in ENTRY_FAMILIES:
        if moment.event_type == "Carry":
            keys.append("carry_entry")
        elif moment.event_type == "Pass" and isinstance(end, (list, tuple)) and len(end) >= 2:
            keys.append("central_pass_entry" if PENALTY_AREA_Y[0] <= float(end[1]) <= PENALTY_AREA_Y[1] else "wide_pass_entry")
        if play_pattern in SET_PLAY_PATTERNS:
            keys.append("set_play_origin_entry")
        if play_pattern == "From Counter":
            keys.append("explicit_counter_entry")

    if moment.family in SHOT_FAMILIES and moment.event_type == "Shot":
        if play_pattern == "From Counter":
            keys.append("explicit_counter_attack_shot")
        elif play_pattern in SET_PLAY_PATTERNS or shot_type in SET_PLAY_SHOT_TYPES:
            keys.append("set_play_shot")
        else:
            keys.append("open_play_shot")
        if isinstance(start, (list, tuple)) and len(start) >= 2:
            keys.append("central_shot_location" if CENTRAL_SHOT_Y[0] <= float(start[1]) <= CENTRAL_SHOT_Y[1] else "wide_angle_shot_location")
        distribution = _shot_distribution(moment)
        xg = values.get("xg")
        if distribution is not None and xg is not None and distribution.get("median") is not None:
            keys.append("higher_xg_shot" if float(xg) >= float(distribution["median"]) else "lower_xg_shot")

    if moment.family in DEFENSIVE_FAMILIES:
        if moment.event_type == "Interception":
            keys.append("interception")
        elif moment.event_type == "Ball Recovery":
            keys.append("recovery")
        if moment.event_type in {"Interception", "Ball Recovery"} and isinstance(start, (list, tuple)) and len(start) >= 2 and float(start[0]) >= HIGH_REGAIN_X:
            keys.append("high_zone_regain")
        if _is_immediate_progression(detail):
            keys.append("immediate_same_possession_progression")
    return tuple(keys)


def _representative_ids(moments: Sequence[RepresentativeMoment]) -> tuple[str, ...]:
    chosen: list[str] = []
    used_matches: set[int] = set()
    for moment in moments:
        if moment.match_id not in used_matches:
            chosen.append(moment.event_id)
            used_matches.add(moment.match_id)
        if len(chosen) == 3:
            return tuple(chosen)
    for moment in moments:
        if moment.event_id not in chosen:
            chosen.append(moment.event_id)
        if len(chosen) == 3:
            break
    return tuple(chosen)


def _observed_evidence(moments: Sequence[RepresentativeMoment]) -> list[dict[str, Any]]:
    return [{
        "event_id": moment.event_id,
        "match_id": moment.match_id,
        "event_type": moment.event_type,
        "start_coordinates": moment.relevant_values.get("start_coordinates"),
        "end_coordinates": moment.relevant_values.get("end_coordinates"),
        "play_pattern": moment.relevant_values.get("play_pattern"),
        "shot_type": moment.relevant_values.get("shot_type"),
        "xg": moment.relevant_values.get("xg"),
    } for moment in moments]


def build_moment_patterns(
    priority_id: str,
    moments: Sequence[RepresentativeMoment],
    *,
    details: Mapping[str, RepresentativeMomentDetail] | None = None,
) -> MomentPatternResult:
    """Summarize explicit classifications across retrieved eligible moments."""
    details = details or {}
    eligible = tuple(moment for moment in moments if moment.family in ENTRY_FAMILIES | SHOT_FAMILIES | DEFENSIVE_FAMILIES)
    classified = [(moment, classify_moment_patterns(moment, details.get(moment.event_id))) for moment in eligible]
    assignments = tuple(MomentPatternAssignment(
        event_id=moment.event_id, match_id=moment.match_id,
        pattern_ids=tuple(_pattern_id(priority_id, key) for key in keys), pattern_keys=keys,
    ) for moment, keys in classified)
    patterns: list[MomentPattern] = []
    all_keys = sorted({key for _, keys in classified for key in keys})
    for key in all_keys:
        matching = [moment for moment, keys in classified if key in keys]
        name, definition, evidence = _DEFINITIONS[key]
        patterns.append(MomentPattern(
            pattern_id=_pattern_id(priority_id, key), pattern_key=key, pattern_name=name,
            deterministic_definition=definition, priority_id=priority_id,
            relevant_metrics=tuple(sorted({moment.metric for moment in matching})),
            moment_count=len(matching), eligible_moment_count=len(eligible),
            share_of_eligible_moments=len(matching) / len(eligible) if eligible else 0.0,
            contributing_matches=tuple(sorted({moment.match_id for moment in matching})),
            representative_moment_ids=_representative_ids(matching),
            coordinate_event_field_evidence={
                **evidence, "coordinate_system": "statsbomb_120x80",
                "observed_moments": _observed_evidence(matching),
            },
            limitations=(
                "Patterns describe only the retrieved historical event examples, not every event in the season.",
                "Labels may overlap where one explicit event supports action, origin, location, and relative-xG descriptors.",
                "Event-only data does not establish opponent shape, overloads, pressure structure, passing lanes, player roles, or tactical intent.",
            ),
            capability_provenance={
                "providers": sorted({str(moment.source_provenance.get("provider", "unknown")) for moment in matching}),
                "required_capabilities": ["has_events"],
                "has_events": True, "has_continuous_tracking": False,
                "coordinate_system": "statsbomb_120x80",
            },
        ))
    limitations = [
        "Shares use retrieved eligible moments as the denominator and may sum above 100% because supported labels can overlap.",
        "These patterns organize historical examples; they do not explain or prove a future matchup interaction.",
    ]
    unclassified = sum(not keys for _, keys in classified)
    if unclassified:
        limitations.append(f"{unclassified} eligible moment(s) remained unclassified because required event fields were unavailable.")
    return MomentPatternResult(
        priority_id=priority_id, eligible_moment_count=len(eligible), patterns=tuple(patterns),
        assignments=assignments, limitations=tuple(limitations),
    )
