"""Football-first, deterministic presentation of existing team-season evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .event_team_profile import EventTeamSeasonProfile


MINIMUM_MATCHES = 5
MINIMUM_COVERAGE = 0.70


@dataclass(frozen=True)
class FootballConceptEvidence:
    metric: str
    football_label: str
    season_median: float
    q25: float
    q75: float
    unit: str
    contributing_matches: int
    coverage: float
    definition: str
    representative_matches: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class FootballStyleConcept:
    concept_id: str
    title: str
    summary: str
    what_this_looks_like: str
    evidence_basis: str
    supporting_evidence: tuple[FootballConceptEvidence, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamStyleDimension:
    dimension_id: str
    label: str
    level: str
    concept_id: str


@dataclass(frozen=True)
class FootballStyleProfile:
    schema_version: str
    team_id: str | int
    team_name: str
    competition_id: str | int
    competition_name: str | None
    season_id: str | int
    season_name: str | None
    analysed_match_count: int
    playing_identity: str
    style_at_a_glance: tuple[TeamStyleDimension, ...]
    in_possession: tuple[FootballStyleConcept, ...]
    out_of_possession: tuple[FootballStyleConcept, ...]
    transitions: tuple[FootballStyleConcept, ...]
    strengths: tuple[FootballStyleConcept, ...]
    potential_weaknesses: tuple[FootballStyleConcept, ...]
    recent_style: tuple[FootballStyleConcept, ...]
    recent_window_matches: int
    capabilities: dict[str, bool]
    limitations: tuple[str, ...] = field(default_factory=tuple)


FOOTBALL_LABELS = {
    "possession_share_estimate": "Share of the event timeline in possession",
    "passes_attempted_per90": "Passes attempted",
    "pass_completion_rate": "Pass completion",
    "progressive_passes_per90": "Forward-progressing passes",
    "progressive_carries_per90": "Forward-progressing carries",
    "passes_into_final_third_per90": "Final-third entries by pass",
    "passes_into_penalty_area_per90": "Penalty-area entries by pass",
    "shots_per90": "Shots",
    "xg_per90": "Expected goals",
    "xg_per_shot": "Expected goals per shot",
    "average_shot_distance": "Shot distance",
    "pressures_per90": "Pressure actions",
    "interceptions_per90": "Interceptions",
    "recoveries_per90": "Ball recoveries",
    "high_regains_per90": "High regains",
    "passes_into_penalty_area_conceded_per90": "Penalty-area pass entries conceded",
    "shots_conceded_per90": "Shots conceded",
    "xg_conceded_per90": "Expected goals conceded",
    "turnovers_leading_to_shot_per90": "Possession losses followed by an opposition shot",
    "counter_attack_shots_per90": "Shots explicitly labelled as counters",
    "counter_attack_shots_conceded_per90": "Counter-labelled shots conceded",
    "set_play_shots_conceded_per90": "Set-play shots conceded",
}


def _aggregate(profile: EventTeamSeasonProfile, metric: str) -> pd.Series | None:
    rows = profile.aggregate_metrics.loc[profile.aggregate_metrics.metric.eq(metric)]
    return None if rows.empty else rows.iloc[0]


def _representative_matches(profile: EventTeamSeasonProfile, metric: str, median: float) -> tuple[dict[str, Any], ...]:
    if metric not in profile.match_metrics:
        return ()
    rows = profile.match_metrics.dropna(subset=[metric]).copy()
    if rows.empty:
        return ()
    rows["distance"] = rows[metric].sub(median).abs()
    choices = [rows.sort_values(["distance", "match_id"], kind="stable").iloc[0]]
    if len(rows) > 1:
        choices.append(rows.sort_values([metric, "match_id"], ascending=[False, True], kind="stable").iloc[0])
    output, seen = [], set()
    for row in choices:
        if row.match_id in seen:
            continue
        seen.add(row.match_id)
        output.append({
            "match_id": row.match_id, "match_date": row.get("match_date"),
            "opponent_team_name": row.get("opponent_team_name"),
            "home_away": row.get("home_away"), "value": float(row[metric]),
        })
    return tuple(output)


def _evidence(profile: EventTeamSeasonProfile, *metrics: str) -> tuple[FootballConceptEvidence, ...]:
    output = []
    for metric in metrics:
        row = _aggregate(profile, metric)
        if row is None or int(row.contributing_matches) < MINIMUM_MATCHES or float(row.coverage) < MINIMUM_COVERAGE:
            continue
        output.append(FootballConceptEvidence(
            metric=metric, football_label=FOOTBALL_LABELS.get(metric, metric.replace("_", " ").title()),
            season_median=float(row.median_across_matches), q25=float(row.q25_across_matches),
            q75=float(row.q75_across_matches), unit=str(row.unit),
            contributing_matches=int(row.contributing_matches), coverage=float(row.coverage),
            definition=str(row.definition),
            representative_matches=_representative_matches(profile, metric, float(row.median_across_matches)),
        ))
    return tuple(output)


def _value(profile: EventTeamSeasonProfile, metric: str) -> float | None:
    row = _aggregate(profile, metric)
    return None if row is None or pd.isna(row.median_across_matches) else float(row.median_across_matches)


def _basis(evidence: tuple[FootballConceptEvidence, ...]) -> str:
    if not evidence:
        return "Unavailable"
    matches = min(item.contributing_matches for item in evidence)
    coverage = min(item.coverage for item in evidence)
    return "Established" if matches >= 20 and coverage >= .90 else "Developing" if matches >= 10 and coverage >= .80 else "Limited"


def _level(value: float | None, moderate: float, high: float) -> str:
    if value is None:
        return "Unavailable"
    return "High" if value >= high else "Moderate" if value >= moderate else "Low"


def _style_dimensions(profile: EventTeamSeasonProfile, concepts: tuple[FootballStyleConcept, ...]) -> tuple[TeamStyleDimension, ...]:
    """Create football-facing levels from metrics already supporting concepts."""
    available = {item.concept_id for item in concepts}
    possession = _value(profile, "possession_share_estimate")
    counters = _value(profile, "counter_attack_shots_per90")
    if possession is None or counters is None:
        directness = "Unavailable"
    elif possession <= .45 or counters >= .50:
        directness = "High"
    elif possession >= .60 and counters < .25:
        directness = "Low"
    else:
        directness = "Moderate"
    candidates = (
        TeamStyleDimension("possession_control", "Control of possession", _level(possession, .50, .60), "build_up"),
        TeamStyleDimension("directness", "Directness", directness, "progression"),
        TeamStyleDimension("forward_progression", "Forward progression", _level(_value(profile, "progressive_passes_per90"), 24, 32), "progression"),
        TeamStyleDimension("penalty_area_presence", "Penalty-area presence", _level(_value(profile, "passes_into_penalty_area_per90"), 8, 12), "territorial_access"),
        TeamStyleDimension("shot_volume", "Shot volume", _level(_value(profile, "shots_per90"), 10, 14), "chance_creation"),
        TeamStyleDimension("shot_quality", "Shot quality", _level(_value(profile, "xg_per_shot"), .09, .13), "shot_selection"),
        TeamStyleDimension("high_ball_recovery", "High-ball recovery", _level(_value(profile, "high_regains_per90"), 6, 10), "high_recovery"),
        TeamStyleDimension("counter_attacking", "Counter-attacking tendency", _level(counters, .12, .35), "counter_attack"),
    )
    return tuple(item for item in candidates if item.concept_id in available and item.level != "Unavailable")


def _concept(profile: EventTeamSeasonProfile, concept_id: str, title: str, summary: str, what_this_looks_like: str, metrics: tuple[str, ...], *limitations: str) -> FootballStyleConcept | None:
    evidence = _evidence(profile, *metrics)
    if not evidence:
        return None
    return FootballStyleConcept(concept_id, title, summary, what_this_looks_like, _basis(evidence), evidence, tuple(limitations))


def _share_above(profile: EventTeamSeasonProfile, rules: dict[str, float]) -> tuple[int, int, float]:
    available = [metric for metric in rules if metric in profile.match_metrics]
    rows = profile.match_metrics.dropna(subset=available)
    if not available or rows.empty:
        return 0, 0, 0.0
    qualifies = pd.Series(True, index=rows.index)
    for metric, threshold in rules.items():
        qualifies &= rows[metric].ge(threshold)
    return int(qualifies.sum()), int(len(rows)), float(qualifies.mean())


def _recent_style(profile: EventTeamSeasonProfile, window: int) -> tuple[FootballStyleConcept, ...]:
    ordered = profile.match_metrics.copy()
    if "match_date" in ordered:
        ordered["_date"] = pd.to_datetime(ordered.match_date, errors="coerce")
        ordered = ordered.sort_values(["_date", "match_id"], kind="stable", na_position="first")
    recent = ordered.tail(min(window, len(ordered)))
    definitions = {
        "possession_share_estimate": ("Recent possession pattern", "more", "less"),
        "progressive_passes_per90": ("Recent forward progression", "more frequent", "less frequent"),
        "passes_into_penalty_area_per90": ("Recent penalty-area access", "more frequent", "less frequent"),
        "shots_per90": ("Recent shot volume", "higher", "lower"),
        "high_regains_per90": ("Recent high regains", "more frequent", "less frequent"),
    }
    candidates = []
    for metric, (title, higher, lower) in definitions.items():
        row = _aggregate(profile, metric)
        if row is None or metric not in recent or recent[metric].notna().sum() < min(3, len(recent)):
            continue
        season = float(row.median_across_matches); recent_median = float(recent[metric].median())
        spread = max(float(row.q75_across_matches) - float(row.q25_across_matches), abs(season) * .10, .01)
        effect = (recent_median - season) / spread
        if abs(effect) < .50:
            continue
        direction = higher if effect > 0 else lower
        evidence = _evidence(profile, metric)
        visible_titles = {
            "possession_share_estimate": "They have been seeing more of the ball" if effect > 0 else "They have been seeing less of the ball",
            "progressive_passes_per90": "They have been moving forward more often" if effect > 0 else "They have been moving forward less often",
            "passes_into_penalty_area_per90": "They have been getting into the box more often" if effect > 0 else "They have been getting into the box less often",
            "shots_per90": "They have been shooting more often" if effect > 0 else "They have been shooting less often",
            "high_regains_per90": "They have been winning the ball higher more often" if effect > 0 else "They have been winning the ball high less often",
        }
        candidates.append((abs(effect), FootballStyleConcept(
            f"recent:{metric}", visible_titles[metric],
            f"Across the latest {len(recent)} matches, this has changed noticeably from the pattern seen over the full season.",
            f"Look for whether this behaviour appears more or less often than it did earlier in the season.",
            _basis(evidence), evidence,
            (f"Recent comparison uses {len(recent)} matches and may reflect opponents, score states, or availability as well as a style change.",),
        )))
    candidates.sort(key=lambda item: (-item[0], item[1].concept_id))
    return tuple(item[1] for item in candidates[:3])


def build_football_style_profile(profile: EventTeamSeasonProfile, *, recent_window: int = 5) -> FootballStyleProfile:
    """Translate validated event evidence into deterministic football language."""
    if recent_window < 1:
        raise ValueError("recent_window must be positive.")
    possession = _value(profile, "possession_share_estimate")
    progression = _value(profile, "progressive_passes_per90")
    box_entries = _value(profile, "passes_into_penalty_area_per90")
    if possession is None:
        identity = "There is not enough reliable evidence yet to describe what kind of team they are."
    else:
        control = "like to take control with the ball" if possession >= .60 else "are comfortable playing without having most of the ball" if possession <= .45 else "are comfortable in games where possession is fairly even"
        territory = "and regularly turn that control into attacks near goal" if (progression or 0) >= 30 and (box_entries or 0) >= 10 else "but the way they turn possession into danger changes from match to match"
        identity = f"{profile.team_name} {control} {territory}."

    completion = _value(profile, "pass_completion_rate") or 0
    build_summary = "They are comfortable circulating the ball and waiting for openings instead of forcing every attack immediately." if possession is not None and possession >= .58 and completion >= .82 else "They mix spells of keeping the ball with attempts to move forward when an opening appears." if possession is not None and possession >= .48 else "They are used to attacking without needing to dominate the ball for long periods."
    prog_summary = "They regularly push attacks up the pitch using both forward passes and runs with the ball." if (progression or 0) >= 32 and (_value(profile, "progressive_carries_per90") or 0) >= 15 else "Passing is their clearest way of moving attacks up the pitch." if (progression or 0) >= 28 else "They tend to move attacks forward at a more patient pace."
    box_summary = "They do not just reach advanced areas; they regularly turn those attacks into touches and passes inside the box." if (box_entries or 0) >= 12 else "They often reach attacking territory, but fewer of those moves make it all the way into the box." if (_value(profile, "passes_into_final_third_per90") or 0) >= 40 else "They reach the final third and the box at a more measured rate."
    shots, xg, xgps = _value(profile, "shots_per90") or 0, _value(profile, "xg_per90") or 0, _value(profile, "xg_per_shot") or 0
    chance_summary = "They usually produce plenty of attempts and regularly create genuinely dangerous chances." if shots >= 14 and xg >= 1.7 else "They shoot often, although those attempts do not always come from the most dangerous situations." if shots >= 14 else "They usually build their threat from a more selective number of attempts."
    shot_summary = "They tend to work the ball into better shooting positions before attempting to finish." if xgps >= .13 else "They are more willing to shoot from situations where scoring is difficult." if xgps <= .09 else "Their attempts come from a mixture of strong and more difficult shooting positions."

    in_possession = tuple(filter(None, (
        _concept(profile, "build_up", "They like to control the game with the ball." if possession and possession >= .58 else "They mix patience with direct play.", build_summary, "Look for repeated spells of passing before they choose the moment to move the attack forward.", ("possession_share_estimate", "passes_attempted_per90", "pass_completion_rate"), "Possession is estimated from the event timeline, not optical tracking."),
        _concept(profile, "progression", "They look to move forward regularly." if (progression or 0) >= 32 else "They move forward more patiently.", prog_summary, "Watch how often an attack gains ground through a forward pass or a player carrying the ball.", ("progressive_passes_per90", "progressive_carries_per90")),
        _concept(profile, "territorial_access", "They get the ball into the box regularly." if (box_entries or 0) >= 12 else "Reaching the box can be the difficult part.", box_summary, "Look for attacks that cross into the final third and whether the next action takes the ball inside the box.", ("passes_into_final_third_per90", "passes_into_penalty_area_per90")),
        _concept(profile, "chance_creation", "They create plenty of shooting opportunities." if shots >= 14 else "They are more selective with their shots.", chance_summary, "Look for how often their attacks finish with a shot and whether those shots come from genuinely dangerous situations.", ("shots_per90", "xg_per90")),
        _concept(profile, "shot_selection", "They usually work for good shooting positions." if xgps >= .13 else "They often accept difficult shots." if xgps <= .09 else "They shoot from a mixture of positions.", shot_summary, "Watch the location of the final attempt: close to goal and central, or farther away and at a tighter angle.", ("xg_per_shot", "average_shot_distance")),
    )))

    pressures = _value(profile, "pressures_per90") or 0
    regains = _value(profile, "high_regains_per90") or 0
    conceded = _value(profile, "shots_conceded_per90") or 0
    out_of_possession = tuple(filter(None, (
        _concept(profile, "defensive_activity", "They work actively to win the ball back." if pressures >= 115 else "They choose their defensive moments.", "They challenge the opposition regularly through pressure, interceptions and recoveries." if pressures >= 115 else "Their defensive actions appear at a more measured rate rather than constantly throughout the match.", "Look for how quickly and how often a nearby player engages when the opposition receives the ball.", ("pressures_per90", "recoveries_per90", "interceptions_per90")),
        _concept(profile, "high_recovery", "They often win the ball back high up the pitch." if regains >= 10 else "Winning the ball high is less common.", "Recovering possession close to the opposition goal is a recurring feature." if regains >= 10 else "They do win possession in advanced areas, but it is not one of the clearest repeated patterns.", "Look for recoveries and interceptions in the attacking third before the opposition can move up the pitch.", ("high_regains_per90",)),
        _concept(profile, "defensive_exposure", "They usually keep opponents away from goal." if conceded <= 10 else "Opponents regularly find shooting chances." if conceded >= 13 else "Opponents create a moderate number of chances.", "Opponents usually produce relatively few attempts against them." if conceded <= 10 else "Opponents are regularly able to finish attacks with an attempt." if conceded >= 13 else "The number of opposition attempts is neither consistently low nor especially high.", "Look for how often opposition attacks enter the box and finish with a shot.", ("shots_conceded_per90", "xg_conceded_per90", "passes_into_penalty_area_conceded_per90")),
    )))

    counters = _value(profile, "counter_attack_shots_per90") or 0
    turnover_exposure = _value(profile, "turnovers_leading_to_shot_per90") or 0
    transitions = tuple(filter(None, (
        _concept(profile, "counter_attack", "They can threaten quickly after winning the ball." if counters >= .35 else "Counter-attacks rarely finish with a shot.", "Quick attacks after a change of possession form a visible part of their threat." if counters >= .35 else "Only a small share of their attempts come from attacks explicitly recorded as counters.", "Look for moves that go from winning possession to a shot before the opposition can settle.", ("counter_attack_shots_per90",), "Only StatsBomb's explicit From Counter label is counted."),
        _concept(profile, "turnover_exposure", "Some lost possessions become opposition shots quickly." if turnover_exposure >= 1 else "They rarely concede an immediate shot after losing the ball.", "Opponents sometimes reach a shot soon after this team gives up possession." if turnover_exposure >= 1 else "Relatively few losses of possession are followed immediately by an opposition attempt.", "Look at the seconds after possession is lost and whether the opponent can turn that moment into an attempt.", ("turnovers_leading_to_shot_per90",)),
    )))

    strengths = []
    count, total, share = _share_above(profile, {"passes_into_penalty_area_per90": 12, "xg_per90": 1.5})
    if total >= 10 and count >= 5 and share >= .45:
        strengths.append(_concept(profile, "strength_dangerous_access", "They repeatedly get the ball into dangerous areas.", "This is not an occasional flash: getting into the box and creating meaningful chances appears across many matches.", "Look for attacks that enter the box and finish from positions where scoring is realistically possible.", ("passes_into_penalty_area_per90", "xg_per90"), f"The qualifying combination occurred in {count} of {total} analysed matches."))
    count, total, share = _share_above(profile, {"progressive_passes_per90": 30, "passes_into_final_third_per90": 40})
    if total >= 10 and count >= 5 and share >= .50:
        strengths.append(_concept(profile, "strength_progression", "They consistently move attacks up the pitch.", "Their ability to gain ground and reach attacking territory repeats across the season rather than depending on one unusual match.", "Look for sequences that start deeper and still carry the ball or pass it into the attacking third.", ("progressive_passes_per90", "passes_into_final_third_per90"), f"The qualifying combination occurred in {count} of {total} analysed matches."))

    weaknesses = []
    count, total, share = _share_above(profile, {"shots_conceded_per90": 12, "xg_conceded_per90": 1.2})
    if total >= 10 and count >= 5 and share >= .25:
        weaknesses.append(_concept(profile, "weakness_chance_exposure", "Potential weakness: opponents can build sustained danger.", "Across several matches, opponents were able to combine repeated attempts with chances from threatening situations.", "Look for periods where opposition attacks keep ending in shots rather than being stopped earlier.", ("shots_conceded_per90", "xg_conceded_per90"), f"The qualifying combination occurred in {count} of {total} analysed matches.", "This identifies repeated outcomes, not their tactical cause."))
    count, total, share = _share_above(profile, {"turnovers_leading_to_shot_per90": 1.0})
    if total >= 10 and count >= 5 and share >= .30:
        weaknesses.append(_concept(profile, "weakness_turnover_exposure", "Potential weakness: some lost balls become shots quickly.", "This pattern repeats across the season: after possession is lost, the opponent can sometimes reach an attempt before the game settles.", "Review the moments immediately after the team loses the ball and track how quickly the opponent reaches goal.", ("turnovers_leading_to_shot_per90",), f"The qualifying pattern occurred in {count} of {total} analysed matches.", "The event sequence shows timing, not why possession was lost or why the shot followed."))

    supported_concepts = (*in_possession, *out_of_possession, *transitions)
    return FootballStyleProfile(
        schema_version="tactiq.football-style-profile.v1", team_id=profile.team_id,
        team_name=profile.team_name, competition_id=profile.competition_id,
        competition_name=profile.competition_name, season_id=profile.season_id,
        season_name=profile.season_name, analysed_match_count=len(profile.match_metrics),
        playing_identity=identity,
        style_at_a_glance=_style_dimensions(profile, supported_concepts),
        in_possession=in_possession,
        out_of_possession=out_of_possession, transitions=transitions,
        strengths=tuple(item for item in strengths if item is not None),
        potential_weaknesses=tuple(item for item in weaknesses if item is not None),
        recent_style=_recent_style(profile, recent_window), recent_window_matches=min(recent_window, len(profile.match_metrics)),
        capabilities={"has_events": True, "has_continuous_tracking": False, "has_verified_defensive_height": False, "has_verified_compactness": False},
        limitations=(
            "Event data supports on-ball actions and event-timeline possession; it does not show full off-ball team shape.",
            "Defensive height, compactness and team width are not stated without compatible continuous tracking.",
            "Strengths and potential weaknesses are deterministic repeated-outcome descriptions, not causal diagnoses or recommendations.",
        ),
    )
