"""Directly observable spatial context from one event-linked 360 snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Sequence

import pandas as pd

from src.data import CanonicalMatchBundle, validate_canonical_bundle

from .event_team_profile import PENALTY_AREA_X, PENALTY_AREA_Y
from .representative_moments import RepresentativeMoment


DEFAULT_RADII = (5.0, 10.0, 15.0)


@dataclass(frozen=True)
class SnapshotPlayer:
    snapshot_player_index: int
    affiliation: str
    teammate: bool | None
    actor: bool
    keeper: bool
    location_x: float
    location_y: float


@dataclass(frozen=True)
class Moment360Context:
    event_id: str
    available: bool
    spatial_context_mode: str
    visible_teammate_count: int | None
    visible_opponent_count: int | None
    visible_unknown_affiliation_count: int | None
    nearest_opponent_distance: float | None
    nearest_teammate_distance: float | None
    opponents_within_radius: dict[str, int]
    teammates_within_radius: dict[str, int]
    visible_players_ahead_of_event: int | None
    visible_players_behind_event: int | None
    visible_teammates_ahead_of_event: int | None
    visible_opponents_ahead_of_event: int | None
    visible_teammates_in_penalty_area: int | None
    visible_opponents_in_penalty_area: int | None
    visible_player_width_range: float | None
    visible_player_depth_range: float | None
    event_location_inside_visible_player_hull: bool | None
    event_location_inside_provider_visible_area: bool | None
    snapshot_players: tuple[SnapshotPlayer, ...]
    coordinate_provenance: dict[str, Any]
    attacking_direction_provenance: dict[str, Any]
    visibility_limitations: tuple[str, ...]
    freeze_frame_source_metadata: dict[str, Any]
    evidence_wording: str


def _mode(bundle: CanonicalMatchBundle, snapshot_available: bool) -> str:
    if bundle.capabilities.has_continuous_tracking:
        return "continuous_tracking"
    return "event_plus_360_snapshot" if snapshot_available else "event_only"


def _empty(moment: RepresentativeMoment, bundle: CanonicalMatchBundle, reason: str) -> Moment360Context:
    return Moment360Context(
        event_id=moment.event_id, available=False,
        spatial_context_mode=_mode(bundle, False),
        visible_teammate_count=None, visible_opponent_count=None,
        visible_unknown_affiliation_count=None,
        nearest_opponent_distance=None, nearest_teammate_distance=None,
        opponents_within_radius={}, teammates_within_radius={},
        visible_players_ahead_of_event=None, visible_players_behind_event=None,
        visible_teammates_ahead_of_event=None, visible_opponents_ahead_of_event=None,
        visible_teammates_in_penalty_area=None, visible_opponents_in_penalty_area=None,
        visible_player_width_range=None, visible_player_depth_range=None,
        event_location_inside_visible_player_hull=None,
        event_location_inside_provider_visible_area=None, snapshot_players=(),
        coordinate_provenance={
            "provider": bundle.provider, "coordinate_system": "statsbomb_120x80",
            "distance_unit": "native_statsbomb_units", "snapshot_is_continuous_tracking": False,
        },
        attacking_direction_provenance={"known": False, "sign": None, "source": None},
        visibility_limitations=(
            reason,
            "Event-only behavior is preserved; no player positions are inferred.",
        ),
        freeze_frame_source_metadata={
            "provider": bundle.provider, "source_table": "canonical_event_snapshots",
            "matched_by": "event_id", "matched_row_count": 0,
        },
        evidence_wording="Event only",
    )


def _polygon(value: Any) -> tuple[tuple[float, float], ...] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 6 or len(value) % 2:
        return None
    return tuple((float(value[index]), float(value[index + 1])) for index in range(0, len(value), 2))


def _point_in_polygon(point: tuple[float, float], polygon: Sequence[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        cross = (y - y1) * (x2 - x1) - (x - x1) * (y2 - y1)
        if abs(cross) <= 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            intersection_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersection_x:
                inside = not inside
    return inside


def _convex_hull(points: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...] | None:
    unique = sorted(set(points))
    if len(unique) < 3:
        return None

    def cross(origin, a, b):
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = tuple(lower[:-1] + upper[:-1])
    return hull if len(hull) >= 3 else None


def _direction(bundle: CanonicalMatchBundle, event: pd.Series) -> dict[str, Any]:
    coordinate_system = str(event.get("coordinate_system"))
    if coordinate_system == "statsbomb_120x80":
        return {
            "known": True, "sign": 1,
            "source": "statsbomb_event_coordinate_convention",
            "definition": "Increasing native event x points toward the acting team's opponent goal.",
        }
    if bundle.capabilities.has_attacking_direction:
        rows = bundle.attacking_directions.loc[
            bundle.attacking_directions.period.eq(event.period)
            & bundle.attacking_directions.team_id.eq(event.team_id)
        ]
        if len(rows) == 1:
            return {"known": True, "sign": int(rows.iloc[0].attacking_x_sign), "source": "canonical_attacking_directions"}
    return {"known": False, "sign": None, "source": None}


def _optional_bool(value: Any) -> bool | None:
    return None if pd.isna(value) else bool(value)


def build_moment_360_context(
    moment: RepresentativeMoment,
    bundle: CanonicalMatchBundle,
    *,
    radii: Sequence[float] = DEFAULT_RADII,
) -> Moment360Context:
    """Enrich a moment only when an exactly aligned freeze frame is available."""
    validate_canonical_bundle(bundle)
    if int(bundle.matches.match_id.iloc[0]) != int(moment.match_id):
        raise ValueError("Representative moment and canonical bundle match IDs differ.")
    if not radii or any(float(radius) <= 0 for radius in radii):
        raise ValueError("360 context radii must be positive.")
    radii = tuple(sorted({float(radius) for radius in radii}))
    if not bundle.capabilities.has_360_snapshots or bundle.event_snapshots is None:
        return _empty(moment, bundle, "No 360 snapshot capability is available for this match.")
    snapshots = bundle.event_snapshots.loc[bundle.event_snapshots.event_id.astype(str).eq(str(moment.event_id))].copy()
    if snapshots.empty:
        return _empty(moment, bundle, "No freeze frame matches this event ID.")
    events = bundle.events.loc[bundle.events.event_id.astype(str).eq(str(moment.event_id))] if bundle.events is not None else pd.DataFrame()
    if len(events) != 1:
        raise ValueError("A 360 freeze frame must align with exactly one canonical event ID.")
    event = events.iloc[0]
    coordinate_systems = set(snapshots.coordinate_system.dropna().astype(str)) if "coordinate_system" in snapshots else set()
    if coordinate_systems and coordinate_systems != {str(event.coordinate_system)}:
        raise ValueError("360 and focal-event coordinate systems disagree.")
    valid_coordinates = snapshots[["location_x", "location_y"]].notna().all(axis=1)
    if not valid_coordinates.all():
        raise ValueError("Canonical 360 snapshot rows must contain complete player coordinates.")
    if not snapshots.location_x.between(0, 120).all() or not snapshots.location_y.between(0, 80).all():
        raise ValueError("StatsBomb 360 coordinates must remain inside the native 120x80 pitch bounds.")
    if snapshots.snapshot_player_index.duplicated().any():
        raise ValueError("A freeze frame contains duplicate snapshot player indexes.")

    players = tuple(SnapshotPlayer(
        snapshot_player_index=int(row.snapshot_player_index),
        affiliation="teammate" if _optional_bool(row.teammate) is True else "opponent" if _optional_bool(row.teammate) is False else "unknown",
        teammate=_optional_bool(row.teammate), actor=bool(row.actor) if pd.notna(row.actor) else False,
        keeper=bool(row.keeper) if pd.notna(row.keeper) else False,
        location_x=float(row.location_x), location_y=float(row.location_y),
    ) for row in snapshots.itertuples(index=False))
    teammates = tuple(player for player in players if player.teammate is True)
    opponents = tuple(player for player in players if player.teammate is False)
    non_actor_teammates = tuple(player for player in teammates if not player.actor)
    unknown_count = sum(player.teammate is None for player in players)
    anchor = None if pd.isna(event.location_x) or pd.isna(event.location_y) else (float(event.location_x), float(event.location_y))
    supplied_anchor = moment.relevant_values.get("start_coordinates")
    if anchor is not None and isinstance(supplied_anchor, (list, tuple)) and len(supplied_anchor) >= 2:
        if hypot(anchor[0] - float(supplied_anchor[0]), anchor[1] - float(supplied_anchor[1])) > 1e-6:
            raise ValueError("Representative moment and canonical focal-event coordinates disagree.")

    def distances(group: Sequence[SnapshotPlayer]) -> list[float]:
        return [] if anchor is None else [hypot(player.location_x - anchor[0], player.location_y - anchor[1]) for player in group]

    opponent_distances = distances(opponents)
    teammate_distances = distances(non_actor_teammates)
    direction = _direction(bundle, event)
    ahead = behind = teammate_ahead = opponent_ahead = None
    if anchor is not None and direction["known"]:
        sign = int(direction["sign"])
        deltas = [(player, (player.location_x - anchor[0]) * sign) for player in players if not player.actor]
        ahead = sum(delta > 0 for _, delta in deltas)
        behind = sum(delta < 0 for _, delta in deltas)
        teammate_ahead = sum(player.teammate is True and delta > 0 for player, delta in deltas)
        opponent_ahead = sum(player.teammate is False and delta > 0 for player, delta in deltas)

    def in_penalty_area(player: SnapshotPlayer) -> bool:
        if not direction["known"]:
            return False
        length_condition = player.location_x >= PENALTY_AREA_X if int(direction["sign"]) == 1 else player.location_x <= 120.0 - PENALTY_AREA_X
        return length_condition and PENALTY_AREA_Y[0] <= player.location_y <= PENALTY_AREA_Y[1]

    penalty_teammates = sum(in_penalty_area(player) for player in teammates) if direction["known"] else None
    penalty_opponents = sum(in_penalty_area(player) for player in opponents) if direction["known"] else None
    points = tuple((player.location_x, player.location_y) for player in players)
    hull = _convex_hull(points)
    visible_areas = {_polygon(value) for value in snapshots.visible_area if _polygon(value) is not None}
    if len(visible_areas) > 1:
        raise ValueError("Rows for one freeze frame contain inconsistent provider visible-area polygons.")
    visible_area = next(iter(visible_areas), None)
    limitations = [
        "This is a partial event-linked 360 snapshot, not full-team or continuous tracking.",
        "Visible-player counts and ranges describe only players inside the supplied camera-visible snapshot.",
        "No interpolation, opponent shape, team compactness, passing lane, overload, pressure, marking, or off-ball movement is inferred.",
        "Nearest-teammate distance excludes the actor so an actor located at the event origin does not force a zero distance.",
    ]
    if unknown_count:
        limitations.append(f"{unknown_count} visible player(s) lacked teammate/opponent assignment and were excluded from affiliation-specific metrics.")
    if anchor is None:
        limitations.append("The focal event location is unavailable; anchor-relative metrics remain missing.")
    if hull is None:
        limitations.append("The visible-player convex hull is unavailable because fewer than three non-collinear player locations were supplied.")
    if visible_area is None:
        limitations.append("The provider visible-area polygon is unavailable or malformed.")
    return Moment360Context(
        event_id=moment.event_id, available=True, spatial_context_mode=_mode(bundle, True),
        visible_teammate_count=len(teammates), visible_opponent_count=len(opponents),
        visible_unknown_affiliation_count=unknown_count,
        nearest_opponent_distance=min(opponent_distances) if opponent_distances else None,
        nearest_teammate_distance=min(teammate_distances) if teammate_distances else None,
        opponents_within_radius={str(radius): sum(distance <= radius for distance in opponent_distances) for radius in radii},
        teammates_within_radius={str(radius): sum(distance <= radius for distance in teammate_distances) for radius in radii},
        visible_players_ahead_of_event=ahead, visible_players_behind_event=behind,
        visible_teammates_ahead_of_event=teammate_ahead, visible_opponents_ahead_of_event=opponent_ahead,
        visible_teammates_in_penalty_area=penalty_teammates,
        visible_opponents_in_penalty_area=penalty_opponents,
        visible_player_width_range=max(point[1] for point in points) - min(point[1] for point in points) if points else None,
        visible_player_depth_range=max(point[0] for point in points) - min(point[0] for point in points) if points else None,
        event_location_inside_visible_player_hull=_point_in_polygon(anchor, hull) if anchor is not None and hull is not None else None,
        event_location_inside_provider_visible_area=_point_in_polygon(anchor, visible_area) if anchor is not None and visible_area is not None else None,
        snapshot_players=players,
        coordinate_provenance={
            "provider": bundle.provider, "coordinate_system": str(event.coordinate_system),
            "pitch_dimensions": [120.0, 80.0], "distance_unit": "native_statsbomb_units",
            "event_location_is_distance_anchor": True, "snapshot_is_continuous_tracking": False,
        },
        attacking_direction_provenance=direction,
        visibility_limitations=tuple(limitations),
        freeze_frame_source_metadata={
            "provider": bundle.provider, "source_table": "canonical_event_snapshots",
            "matched_by": "event_id", "matched_row_count": len(snapshots),
            "visible_area_available": visible_area is not None, "actor_row_count": sum(player.actor for player in players),
        },
        evidence_wording="Partial event-linked spatial context (Event + 360 snapshot)",
    )
