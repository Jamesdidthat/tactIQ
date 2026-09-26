"""Transparent event-sequence features, distances, and groups for review moments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations
from typing import Any, Mapping, Sequence

from .event_team_profile import SET_PLAY_PATTERNS, SET_PLAY_SHOT_TYPES
from .representative_moment_detail import RepresentativeMomentDetail
from .representative_moments import RepresentativeMoment


@dataclass(frozen=True)
class MomentSequenceFeatures:
    event_id: str
    match_id: int
    entry_type: str
    start_zone: str | None
    end_zone: str | None
    corridor: str | None
    sequence_length_events: int
    sequence_duration_seconds: float
    preceding_event_count: int
    preceding_pass_count: int
    preceding_carry_count: int
    sequence_band: str
    play_context: str
    explicit_counter: bool
    shot_outcome: str | None
    shot_xg: float | None
    score_state: str | None
    score_state_verified: bool
    sequence_pattern_id: str
    sequence_pattern_label: str


@dataclass(frozen=True)
class MomentSequencePattern:
    pattern_id: str
    pattern_label: str
    count: int
    share_of_retrieved_moments: float
    contributing_matches: tuple[int, ...]
    representative_event_ids: tuple[str, ...]
    original_subgroup_ids: tuple[str, ...]
    defining_features: dict[str, Any]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class MomentSequenceSimilarity:
    event_id_a: str
    event_id_b: str
    distance: float
    similarity: float
    compared_feature_count: int
    shared_categorical_features: tuple[str, ...]
    differing_categorical_features: tuple[str, ...]


@dataclass(frozen=True)
class MomentSequenceGroupingResult:
    priority_id: str
    features: tuple[MomentSequenceFeatures, ...]
    patterns: tuple[MomentSequencePattern, ...]
    similarities: tuple[MomentSequenceSimilarity, ...]
    limitations: tuple[str, ...]


def _zone(coordinates: tuple[float, float] | None) -> str | None:
    if coordinates is None:
        return None
    x, y = coordinates
    if x >= 102.0 and 18.0 <= y <= 62.0:
        return "penalty_area"
    if x >= 80.0:
        return "final_third"
    if x >= 40.0:
        return "middle_third"
    return "defensive_third"


def _corridor(coordinates: tuple[float, float] | None) -> str | None:
    if coordinates is None:
        return None
    return "central" if 18.0 <= coordinates[1] <= 62.0 else "wide"


def _entry_type(event_type: str) -> str:
    return {
        "Pass": "pass", "Carry": "carry", "Shot": "shot",
        "Ball Recovery": "recovery", "Interception": "interception",
    }.get(event_type, event_type.lower().replace(" ", "_"))


def _play_context(moment: RepresentativeMoment, detail: RepresentativeMomentDetail) -> str:
    play_pattern = detail.focal_event.play_pattern or moment.relevant_values.get("play_pattern")
    shot_type = moment.relevant_values.get("shot_type")
    if play_pattern == "From Counter":
        return "explicit_counter"
    if play_pattern in SET_PLAY_PATTERNS or shot_type in SET_PLAY_SHOT_TYPES:
        return "set_play"
    return "open_play"


def _sequence_band(previous_count: int) -> str:
    if previous_count == 0:
        return "no_preceding_relevant_event"
    return "short_sequence" if previous_count <= 2 else "three_plus_event_sequence"


MATERIAL_SEQUENCE_COUNT_GAP = 5


def _pattern_label(
    moment: RepresentativeMoment, entry_type: str, corridor: str | None,
    play_context: str, band: str, same_possession: bool,
) -> str:
    location = "Central" if corridor == "central" else "Wide" if corridor == "wide" else "Location-unavailable"
    origin = "Set-play" if play_context == "set_play" else "Explicit counter" if play_context == "explicit_counter" else "Open-play"
    if moment.family in {"penalty_area_entries", "final_third_entries"}:
        base = f"{location} {entry_type} entry"
        if play_context != "open_play":
            base = f"{origin} {base.lower()}"
    elif entry_type == "shot":
        base = f"{origin} {location.lower()} shot"
    else:
        action = entry_type.replace("_", " ").title()
        base = action if play_context == "open_play" else f"{origin} {action.lower()}"
    if band == "no_preceding_relevant_event":
        return f"{base} without a preceding relevant event"
    if band == "short_sequence":
        context = "possession sequence" if same_possession else "event sequence"
        return f"{base} after a short {context}"
    if band == "mixed_nonzero_sequence":
        context = "possession sequence" if same_possession else "event sequence"
        return f"{base} after a {context}"
    return f"{base} after 3+ preceding events"


def _pattern_id(priority_id: str, signature: tuple[Any, ...]) -> str:
    value = "|".join(str(item) for item in (priority_id, *signature))
    return f"sequence-pattern-{sha256(value.encode('utf-8')).hexdigest()[:14]}"


def derive_moment_sequence_features(
    priority_id: str,
    moment: RepresentativeMoment,
    detail: RepresentativeMomentDetail,
) -> MomentSequenceFeatures:
    """Derive bounded event-only features with no spatial or tactical inference."""
    if str(moment.event_id) != str(detail.event_id):
        raise ValueError("Moment and event-sequence detail IDs differ.")
    focal = detail.focal_event
    previous = sorted(
        (event for event in detail.sequence_events if event.relation_to_focal == "previous"),
        key=lambda event: event.event_index,
    )
    start = focal.start_coordinates
    end = focal.end_coordinates
    action = _entry_type(focal.event_type)
    grouping_location = end if moment.family in {"penalty_area_entries", "final_third_entries"} and end is not None else start
    corridor = _corridor(grouping_location)
    play_context = _play_context(moment, detail)
    band = _sequence_band(len(previous))
    label = _pattern_label(moment, action, corridor, play_context, band, detail.context_mode == "same_possession")
    # This is the exact pre-merge subgroup. The public grouping pass may merge
    # neighboring count subgroups, but it retains these IDs as provenance.
    signature = (
        moment.family, action, corridor, play_context, _zone(start), _zone(end),
        len(previous),
    )
    first_time = previous[0].elapsed_seconds if previous else focal.elapsed_seconds
    shot_outcome = (moment.relevant_values.get("shot_outcome") or focal.outcome) if action == "shot" else None
    shot_xg = focal.xg if action == "shot" else None
    return MomentSequenceFeatures(
        event_id=moment.event_id, match_id=moment.match_id, entry_type=action,
        start_zone=_zone(start), end_zone=_zone(end), corridor=corridor,
        sequence_length_events=len(previous) + 1,
        sequence_duration_seconds=max(0.0, float(focal.elapsed_seconds - first_time)),
        preceding_event_count=len(previous),
        preceding_pass_count=sum(event.event_type == "Pass" for event in previous),
        preceding_carry_count=sum(event.event_type == "Carry" for event in previous),
        sequence_band=band, play_context=play_context,
        explicit_counter=play_context == "explicit_counter",
        shot_outcome=None if shot_outcome is None else str(shot_outcome),
        shot_xg=None if shot_xg is None else float(shot_xg),
        score_state=moment.score_state if moment.score_state_verified else None,
        score_state_verified=moment.score_state_verified,
        sequence_pattern_id=_pattern_id(priority_id, signature), sequence_pattern_label=label,
    )


def sequence_feature_distance(
    left: MomentSequenceFeatures,
    right: MomentSequenceFeatures,
) -> MomentSequenceSimilarity:
    """Return a transparent normalized distance over explicit sequence features."""
    categorical = (
        "entry_type", "start_zone", "end_zone", "corridor", "sequence_band",
        "play_context", "shot_outcome", "score_state",
    )
    shared, differing = [], []
    distance_total = weight_total = 0.0
    for field in categorical:
        a, b = getattr(left, field), getattr(right, field)
        if a is None and b is None:
            continue
        weight = 1.5 if field in {"entry_type", "play_context"} else 1.0
        weight_total += weight
        if a == b:
            shared.append(field)
        else:
            differing.append(field)
            distance_total += weight
    numeric = (
        ("sequence_duration_seconds", 10.0, .75),
        ("preceding_pass_count", 3.0, .5),
        ("preceding_carry_count", 3.0, .5),
        ("shot_xg", .30, .75),
    )
    numeric_count = 0
    for field, scale, weight in numeric:
        a, b = getattr(left, field), getattr(right, field)
        if a is None or b is None:
            continue
        numeric_count += 1
        weight_total += weight
        distance_total += min(abs(float(a) - float(b)) / scale, 1.0) * weight
    distance = distance_total / weight_total if weight_total else 0.0
    return MomentSequenceSimilarity(
        event_id_a=left.event_id, event_id_b=right.event_id,
        distance=float(distance), similarity=float(1.0 - distance),
        compared_feature_count=len(shared) + len(differing) + numeric_count,
        shared_categorical_features=tuple(shared), differing_categorical_features=tuple(differing),
    )


def _representatives(features: Sequence[MomentSequenceFeatures]) -> tuple[str, ...]:
    selected, matches = [], set()
    for feature in sorted(features, key=lambda item: (item.match_id, item.event_id)):
        if feature.match_id not in matches:
            selected.append(feature.event_id); matches.add(feature.match_id)
        if len(selected) == 3:
            return tuple(selected)
    for feature in sorted(features, key=lambda item: item.event_id):
        if feature.event_id not in selected:
            selected.append(feature.event_id)
        if len(selected) == 3:
            break
    return tuple(selected)


def _hard_semantic_key(
    family: str,
    feature: MomentSequenceFeatures,
) -> tuple[Any, ...]:
    """Return boundaries that the length-only merge pass may never cross."""
    # A defensive-third origin is a hard distinction for penalty-area entries,
    # where it represents a materially different territorial journey. Other
    # native start/end zones remain descriptors: the focal family already
    # establishes the destination boundary, and exact neighboring zones must
    # not fragment otherwise identical sequences.
    material_origin = (
        "deep_origin" if family == "penalty_area_entries" and feature.start_zone == "defensive_third"
        else "standard_origin" if family == "penalty_area_entries"
        else "defensive_or_middle_zone"
        if family in {"interceptions", "high_regains"} and feature.start_zone in {"defensive_third", "middle_third"}
        else "attacking_zone"
        if family in {"interceptions", "high_regains"} and feature.start_zone in {"final_third", "penalty_area"}
        else "origin_unavailable"
        if family in {"interceptions", "high_regains"}
        else "family_defined"
    )
    focal_corridor = (
        feature.corridor
        if family in {"penalty_area_entries", "final_third_entries"} or feature.entry_type == "shot"
        else None
    )
    return (
        family,
        feature.entry_type,
        feature.play_context,
        focal_corridor,
        material_origin,
    )


def _count_clusters(counts: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    """Partition counts only at a material observed discontinuity."""
    unique = tuple(sorted(set(counts)))
    if not unique:
        return ()
    if unique[0] == 0:
        positive = _count_clusters(unique[1:])
        return ((0,), *positive)
    gaps = [unique[index + 1] - unique[index] for index in range(len(unique) - 1)]
    material_gaps = [index for index, gap in enumerate(gaps) if gap >= MATERIAL_SEQUENCE_COUNT_GAP]
    if not material_gaps:
        return (unique,)
    split_index = max(material_gaps, key=lambda index: (gaps[index], -index))
    split_at = split_index + 1
    return (*_count_clusters(unique[:split_at]), *_count_clusters(unique[split_at:]))


def _merged_sequence_class(members: Sequence[MomentSequenceFeatures]) -> str:
    counts = {member.preceding_event_count for member in members}
    if counts == {0}:
        return "no_preceding_relevant_event"
    if max(counts) <= 2:
        return "short_sequence"
    if min(counts) >= 3:
        return "three_plus_event_sequence"
    return "mixed_nonzero_sequence"


def _zone_qualifier(feature: MomentSequenceFeatures) -> str:
    start = feature.start_zone.replace("_", " ") if feature.start_zone else "unknown origin"
    end = feature.end_zone.replace("_", " ") if feature.end_zone else "unknown destination"
    return f"from {start} to {end}"


def build_moment_sequence_grouping(
    priority_id: str,
    moments: Sequence[RepresentativeMoment],
    details: Mapping[str, RepresentativeMomentDetail],
) -> MomentSequenceGroupingResult:
    """Group retrieved moments and calculate all-pairs interpretable similarity."""
    missing = [moment.event_id for moment in moments if moment.event_id not in details]
    if missing:
        raise ValueError(f"Sequence details are missing for {len(missing)} representative moment(s).")
    initial_features = tuple(derive_moment_sequence_features(priority_id, moment, details[moment.event_id]) for moment in moments)
    family_by_event = {moment.event_id: moment.family for moment in moments}
    detail_by_event = {moment.event_id: details[moment.event_id] for moment in moments}
    semantic_buckets: dict[tuple[Any, ...], list[MomentSequenceFeatures]] = {}
    for feature in initial_features:
        semantic_buckets.setdefault(_hard_semantic_key(family_by_event[feature.event_id], feature), []).append(feature)

    merged_groups: list[tuple[str, str, list[MomentSequenceFeatures], tuple[str, ...], str]] = []
    for hard_key in sorted(semantic_buckets, key=lambda value: tuple("" if item is None else str(item) for item in value)):
        candidates = semantic_buckets[hard_key]
        for count_cluster in _count_clusters([item.preceding_event_count for item in candidates]):
            members = [item for item in candidates if item.preceding_event_count in count_cluster]
            original_ids = tuple(sorted({item.sequence_pattern_id for item in members}))
            merged_id = _pattern_id(priority_id, (*hard_key, "merged_counts", *count_cluster))
            merged_class = _merged_sequence_class(members)
            first = min(members, key=lambda item: item.event_id)
            label = _pattern_label(
                next(moment for moment in moments if moment.event_id == first.event_id),
                first.entry_type, first.corridor, first.play_context, merged_class,
                detail_by_event[first.event_id].context_mode == "same_possession",
            )
            merged_groups.append((merged_id, label, members, original_ids, merged_class))

    # If hard zone boundaries produce otherwise identical labels, surface the
    # location distinction instead of exposing duplicate analyst labels.
    label_counts: dict[str, int] = {}
    for _, label, _, _, _ in merged_groups:
        label_counts[label] = label_counts.get(label, 0) + 1

    groups: dict[str, list[MomentSequenceFeatures]] = {}
    group_provenance: dict[str, tuple[tuple[str, ...], str]] = {}
    final_features = []
    for pattern_id, base_label, members, original_ids, merged_class in merged_groups:
        label = base_label
        if label_counts[base_label] > 1:
            label = f"{base_label} - {_zone_qualifier(members[0])}"
        updated = [replace(member, sequence_pattern_id=pattern_id, sequence_pattern_label=label) for member in members]
        groups[pattern_id] = updated
        final_features.extend(updated)
        group_provenance[pattern_id] = (original_ids, merged_class)
    features = tuple(sorted(final_features, key=lambda item: item.event_id))
    patterns = []
    for pattern_id, members in groups.items():
        first = members[0]
        original_ids, merged_class = group_provenance[pattern_id]
        patterns.append(MomentSequencePattern(
            pattern_id=pattern_id, pattern_label=first.sequence_pattern_label,
            count=len(members), share_of_retrieved_moments=len(members) / len(features) if features else 0.0,
            contributing_matches=tuple(sorted({member.match_id for member in members})),
            representative_event_ids=_representatives(members),
            original_subgroup_ids=original_ids,
            defining_features={
                "entry_type": first.entry_type, "corridor": first.corridor,
                "play_context": first.play_context, "sequence_length_class": merged_class,
                "sequence_band_values": sorted({member.sequence_band for member in members}),
                "preceding_event_count_min": min(member.preceding_event_count for member in members),
                "preceding_event_count_max": max(member.preceding_event_count for member in members),
                "start_zone_values": sorted({member.start_zone for member in members if member.start_zone}),
                "end_zone_values": sorted({member.end_zone for member in members if member.end_zone}),
                "merge_applied": len(original_ids) > 1,
                "merge_reason": (
                    "Only sequence-length granularity differed; all hard semantic features matched."
                    if len(original_ids) > 1 else None
                ),
                "material_sequence_count_gap": MATERIAL_SEQUENCE_COUNT_GAP,
                "sequence_length_definition": "Previous relevant events plus the focal event; the optional next event is excluded.",
                "zone_definition": "Defensive third x<40; middle third 40<=x<80; final third x>=80; penalty area x>=102 and 18<=y<=62.",
                "corridor_definition": "Central uses inclusive y 18-62; wide lies outside that band.",
            },
            limitations=(
                "The sequence is bounded to the existing Moment Detail event window and relevant event types.",
                "Event counts do not represent continuous ball or player movement between recorded events.",
                "No defensive structure, passing lane, pressing, overload, player intention, or tactical cause is inferred.",
            ),
        ))
    patterns.sort(key=lambda item: (-item.count, item.pattern_label, item.pattern_id))
    similarities = tuple(sorted(
        (sequence_feature_distance(left, right) for left, right in combinations(features, 2)),
        key=lambda item: (item.distance, item.event_id_a, item.event_id_b),
    ))
    return MomentSequenceGroupingResult(
        priority_id=priority_id, features=features, patterns=tuple(patterns), similarities=similarities,
        limitations=(
            "Groups and distances use explicit StatsBomb event-sequence fields only; no embeddings or black-box clustering are used.",
            f"Non-zero sequence-count subgroups separate only across an observed gap of at least {MATERIAL_SEQUENCE_COUNT_GAP} preceding events; zero-context moments remain separate.",
            "Set play, explicit counter, focal action, entry/shot corridor, materially deep penalty-entry origin, and coarse defensive-event territory are hard merge boundaries.",
            "Shares use retrieved representative moments as the denominator, not all season events.",
            "Similarity is descriptive feature proximity and does not establish tactical equivalence.",
        ),
    )
