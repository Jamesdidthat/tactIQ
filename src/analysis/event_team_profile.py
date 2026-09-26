"""Provider-independent, match-weighted event-based team tactical profiles."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable

import numpy as np
import pandas as pd

from src.data import CanonicalMatchBundle, validate_canonical_bundle


GOAL_CENTRE = (120.0, 40.0)
FINAL_THIRD_X = 80.0
PENALTY_AREA_X = 102.0
PENALTY_AREA_Y = (18.0, 62.0)
HIGH_REGAIN_X = 80.0
TURNOVER_SHOT_SECONDS = 15.0
TURNOVER_SHOT_EVENTS = 10
SET_PLAY_PATTERNS = {
    "From Corner", "From Free Kick",
}
SET_PLAY_SHOT_TYPES = {"Free Kick", "Penalty"}
SHOT_ON_TARGET_OUTCOMES = {"Goal", "Saved", "Saved to Post"}
FAILED_INTERCEPTION_OUTCOMES = {"Lost", "Lost In Play", "Lost Out"}

EVENT_PROFILE_COLUMNS = {
    "match_id", "event_id", "event_index", "period", "elapsed_seconds",
    "team_id", "event_type", "possession_id", "possession_team_id",
    "play_pattern", "location_x", "location_y", "end_location_x",
    "end_location_y", "pass_outcome", "shot_xg", "shot_outcome",
    "shot_type", "duel_type", "ball_recovery_failure", "coordinate_system",
}

COUNT_METRICS = (
    "passes_attempted", "passes_completed", "progressive_passes",
    "passes_into_final_third", "passes_into_penalty_area", "carries",
    "progressive_carries", "shots", "shots_on_target", "goals",
    "open_play_shots", "set_play_shots", "pressures", "tackles",
    "interceptions", "recoveries", "high_regains",
    "turnovers_leading_to_shot", "counter_attack_shots",
)
CONCEDED_COUNT_METRICS = (
    "passes_into_penalty_area_conceded", "shots_conceded",
    "set_play_shots_conceded", "counter_attack_shots_conceded",
)
MATCH_IDENTITY_COLUMNS = (
    "provider", "match_id", "match_date", "competition_id", "season_id",
    "team_id", "team_name", "opponent_team_id", "opponent_team_name",
    "home_away", "home_score", "away_score", "team_score", "opponent_score",
    "leading_seconds", "drawing_seconds", "trailing_seconds",
    "leading_share", "drawing_share", "trailing_share", "score_state_source",
    "metric_chronology", "match_minutes", "coordinate_system",
)


def metric_definitions() -> pd.DataFrame:
    """Return stable definitions; all distances are native 120x80 units."""
    definitions = {
        "possession_share_estimate": ("proportion", "Share of capped event-to-next-event time (0-30s) assigned to the team's StatsBomb possession_team; an event-timeline estimate, not optical possession."),
        "passes_attempted": ("count", "All team events with event_type=Pass, including restarts."),
        "passes_completed": ("count", "Passes with no StatsBomb pass_outcome; StatsBomb records an outcome primarily for unsuccessful passes."),
        "pass_completion_rate": ("proportion", "passes_completed / passes_attempted."),
        "progressive_passes": ("count", "Completed passes moving at least 10 native x units toward x=120 and reducing Euclidean distance to goal centre (120,40) by at least 25%."),
        "passes_into_final_third": ("count", "Completed passes starting before x=80 and ending at x>=80."),
        "passes_into_penalty_area": ("count", "Completed passes starting outside and ending inside x>=102 and 18<=y<=62."),
        "carries": ("count", "All team events with event_type=Carry."),
        "progressive_carries": ("count", "Carries moving at least 10 native x units toward x=120 and reducing distance to goal centre by at least 25%."),
        "shots": ("count", "All team events with event_type=Shot."),
        "shots_on_target": ("count", "Shots with outcome Goal, Saved, or Saved to Post."),
        "goals": ("count", "Shots with shot_outcome=Goal; own-goal event types are not reattributed."),
        "xg": ("xG", "Sum of StatsBomb shot.statsbomb_xg where supplied."),
        "average_shot_distance": ("native_120x80_units", "Mean Euclidean distance from shot origin to goal centre (120,40)."),
        "open_play_shots": ("count", "Shots not tagged From Corner/From Free Kick and not typed Free Kick/Penalty; From Counter and possessions originating at ordinary restarts remain open-play proxies."),
        "set_play_shots": ("count", "Shots explicitly tagged From Corner/From Free Kick or typed Free Kick/Penalty."),
        "pressures": ("count", "All team Pressure events."),
        "tackles": ("count", "Team Duel events whose canonical duel_type is Tackle."),
        "interceptions": ("count", "All team Interception events."),
        "recoveries": ("count", "Team Ball Recovery events not marked recovery_failure."),
        "high_regains": ("count", "Successful Ball Recovery or non-lost Interception at x>=80 in StatsBomb's team-oriented coordinates."),
        "turnovers_leading_to_shot": ("count", "Team possessions followed by an opponent possession containing a shot within 15 elapsed seconds and its first 10 events."),
        "counter_attack_shots": ("count", "Shots whose explicit StatsBomb play_pattern is From Counter; a source-supported fast-attack proxy."),
        "xg_per_shot": ("xG", "Match xG divided by match shots where at least one shot was recorded."),
        "passes_into_penalty_area_conceded": ("count", "Completed penalty-area pass entries recorded by the opposition in the same match; the exact mirror of passes_into_penalty_area."),
        "shots_conceded": ("count", "Opposition Shot events in the same match; the exact mirror of shots."),
        "xg_conceded": ("xG", "Sum of opposition StatsBomb shot.statsbomb_xg in the same match; the exact mirror of xg where supplied."),
        "xg_per_shot_conceded": ("xG", "Opposition match xG divided by opposition shots where at least one shot was recorded."),
        "set_play_shots_conceded": ("count", "Opposition shots explicitly classified by this profile as set-play shots; the exact mirror of set_play_shots."),
        "counter_attack_shots_conceded": ("count", "Opposition shots explicitly tagged From Counter; the exact mirror of counter_attack_shots."),
    }
    rows = [{"metric": metric, "unit": unit, "definition": definition} for metric, (unit, definition) in definitions.items()]
    for metric in COUNT_METRICS:
        rows.append({"metric": f"{metric}_per90", "unit": "per_90", "definition": f"{metric} / analysed match minutes x 90."})
    for metric in CONCEDED_COUNT_METRICS:
        rows.append({"metric": f"{metric}_per90", "unit": "per_90", "definition": f"{metric} / analysed match minutes x 90."})
    rows.append({"metric": "xg_per90", "unit": "xG_per_90", "definition": "xg / analysed match minutes x 90."})
    rows.append({"metric": "xg_conceded_per90", "unit": "xG_per_90", "definition": "xg_conceded / analysed match minutes x 90."})
    return pd.DataFrame(rows)


@dataclass
class EventTeamSeasonProfile:
    team_id: str | int
    team_name: str
    competition_id: str | int
    season_id: str | int
    match_metrics: pd.DataFrame
    aggregate_metrics: pd.DataFrame
    definitions: pd.DataFrame
    matches_excluded: pd.DataFrame
    competition_name: str | None = None
    season_name: str | None = None

    def __post_init__(self) -> None:
        required_match = {"match_id", "team_id", "match_minutes", "coordinate_system"}
        required_aggregate = {"metric", "median_across_matches", "q25_across_matches", "q75_across_matches", "contributing_matches", "total_matches", "coverage"}
        if missing := required_match - set(self.match_metrics.columns):
            raise ValueError(f"match_metrics missing columns: {sorted(missing)}")
        if missing := required_aggregate - set(self.aggregate_metrics.columns):
            raise ValueError(f"aggregate_metrics missing columns: {sorted(missing)}")
        if self.match_metrics.match_id.duplicated().any():
            raise ValueError("Event team-season profile requires one row per match.")


# Product-facing name retained for callers that treat the season as the profile
# scope; both names represent the same validated match-weighted contract.
EventTeamProfileResult = EventTeamSeasonProfile


def _require_event_profile_contract(bundle: CanonicalMatchBundle) -> pd.DataFrame:
    validate_canonical_bundle(bundle)
    if not bundle.capabilities.has_events or bundle.events is None:
        raise ValueError("Event team profiles require canonical events.")
    missing = EVENT_PROFILE_COLUMNS - set(bundle.events.columns)
    if missing:
        raise ValueError(f"Canonical events do not support event team profiles; missing {sorted(missing)}")
    coordinate_systems = set(bundle.events.coordinate_system.dropna().unique())
    if coordinate_systems != {"statsbomb_120x80"}:
        raise ValueError(f"This profile definition currently requires StatsBomb 120x80 event coordinates, got {sorted(coordinate_systems)}")
    return bundle.events.loc[bundle.events.period.le(4)].sort_values(["period", "event_index"], kind="stable").copy()


def _goal_distance(x: pd.Series, y: pd.Series) -> pd.Series:
    return np.sqrt((GOAL_CENTRE[0] - x.astype(float)) ** 2 + (GOAL_CENTRE[1] - y.astype(float)) ** 2)


def _progressive(events: pd.DataFrame) -> pd.Series:
    valid = events[["location_x", "location_y", "end_location_x", "end_location_y"]].notna().all(axis=1)
    start = _goal_distance(events.location_x, events.location_y)
    end = _goal_distance(events.end_location_x, events.end_location_y)
    return valid & events.end_location_x.sub(events.location_x).ge(10.0) & end.le(start.mul(0.75))


def _possession_share(events: pd.DataFrame, team_id: object) -> float:
    timeline = events.loc[events.possession_team_id.notna() & events.elapsed_seconds.notna()].copy()
    if len(timeline) < 2:
        return float("nan")
    next_time = timeline.groupby("period", sort=False).elapsed_seconds.shift(-1)
    weights = next_time.sub(timeline.elapsed_seconds).clip(lower=0.0, upper=30.0).fillna(0.0)
    total = float(weights.sum())
    return float(weights.loc[timeline.possession_team_id.eq(team_id)].sum() / total) if total > 0 else float("nan")


def _turnovers_leading_to_shot(events: pd.DataFrame, team_id: object) -> int:
    return len(_turnover_shot_times(events, team_id))


def _turnover_shot_times(events: pd.DataFrame, team_id: object) -> list[float]:
    return [float(link["shot_elapsed_seconds"]) for link in _turnover_shot_links(events, team_id)]


def _turnover_shot_links(events: pd.DataFrame, team_id: object) -> list[dict]:
    """Return event-level provenance for the existing turnover-to-shot rule.

    The possession-ending event is an observable boundary proxy, not a claim
    about the mechanism that caused possession to change.
    """
    possession_events = events.loc[events.possession_id.notna() & events.possession_team_id.notna()]
    sequences = []
    for (period, possession_id), group in possession_events.groupby(["period", "possession_id"], sort=False):
        ordered = group.sort_values("event_index", kind="stable")
        sequences.append((period, possession_id, ordered.possession_team_id.iloc[0], ordered))
    sequences.sort(key=lambda row: (row[0], row[3].event_index.min()))
    links: list[dict] = []
    for current, following in zip(sequences, sequences[1:]):
        if current[0] != following[0] or current[2] != team_id or following[2] == team_id:
            continue
        opponent = following[3].head(TURNOVER_SHOT_EVENTS)
        start = opponent.elapsed_seconds.dropna().min()
        shots = opponent.loc[opponent.event_type.eq("Shot") & opponent.elapsed_seconds.notna()]
        eligible = shots.loc[shots.elapsed_seconds.sub(start).le(TURNOVER_SHOT_SECONDS)] if pd.notna(start) else shots.iloc[0:0]
        if not eligible.empty:
            shot = eligible.iloc[0]
            turnover = current[3].iloc[-1]
            linked_opponent = opponent.loc[opponent.event_index.le(shot.event_index)]
            links.append({
                "turnover_event_id": str(turnover.event_id),
                "turnover_event_index": int(turnover.event_index),
                "shot_event_id": str(shot.event_id),
                "shot_event_index": int(shot.event_index),
                "shot_elapsed_seconds": float(shot.elapsed_seconds),
                "sequence_start_elapsed_seconds": float(start),
                "seconds_to_shot": float(shot.elapsed_seconds) - float(start),
                "linked_sequence_event_ids": (
                    str(turnover.event_id),
                    *tuple(linked_opponent.event_id.astype(str)),
                ),
                "opponent_possession_event_count_through_shot": int(len(linked_opponent)),
                "definition": (
                    "Team possession followed by an opponent possession containing a shot "
                    "within 15 elapsed seconds and its first 10 events."
                ),
            })
    return links


def _time_summary(values: pd.Series | list[float]) -> dict | None:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna().sort_values(kind="stable")
    if series.empty:
        return None
    return {
        "first_seconds": float(series.iloc[0]),
        "median_seconds": float(series.median()),
        "last_seconds": float(series.iloc[-1]),
        "event_count": int(len(series)),
    }


def _score_state_exposure(
    events: pd.DataFrame, team_id: object, opponent_id: object,
    match_seconds: float, *, expected_team_score: object = None,
    expected_opponent_score: object = None,
) -> dict:
    """Derive descriptive time in each score state from explicit goal events."""
    goals = events.loc[
        (events.event_type.eq("Shot") & events.shot_outcome.eq("Goal"))
        | events.event_type.isin({"Own Goal Against", "Own Goal For"})
    ].sort_values(["elapsed_seconds", "event_index"], kind="stable")
    team_goals = opponent_goals = 0
    last_seconds = 0.0
    exposure = {"leading": 0.0, "drawing": 0.0, "trailing": 0.0}
    for goal in goals.itertuples(index=False):
        seconds = min(max(float(goal.elapsed_seconds), last_seconds), match_seconds)
        state = "leading" if team_goals > opponent_goals else "trailing" if team_goals < opponent_goals else "drawing"
        exposure[state] += seconds - last_seconds
        scoring_team = goal.team_id
        if goal.event_type == "Own Goal Against":
            scoring_team = opponent_id if goal.team_id == team_id else team_id
        if scoring_team == team_id:
            team_goals += 1
        elif scoring_team == opponent_id:
            opponent_goals += 1
        last_seconds = seconds
    state = "leading" if team_goals > opponent_goals else "trailing" if team_goals < opponent_goals else "drawing"
    exposure[state] += max(match_seconds - last_seconds, 0.0)
    verified = True
    if pd.notna(expected_team_score) and pd.notna(expected_opponent_score):
        verified = team_goals == int(expected_team_score) and opponent_goals == int(expected_opponent_score)
    safe_exposure = exposure if verified else {"leading": None, "drawing": None, "trailing": None}
    return {
        "leading_seconds": safe_exposure["leading"], "drawing_seconds": safe_exposure["drawing"],
        "trailing_seconds": safe_exposure["trailing"],
        "leading_share": safe_exposure["leading"] / match_seconds if verified and match_seconds > 0 else float("nan"),
        "drawing_share": safe_exposure["drawing"] / match_seconds if verified and match_seconds > 0 else float("nan"),
        "trailing_share": safe_exposure["trailing"] / match_seconds if verified and match_seconds > 0 else float("nan"),
        "score_state_source": "event_goal_timeline_verified" if verified else "event_goal_timeline_final_score_mismatch",
    }


def calculate_event_team_match_metrics(bundle: CanonicalMatchBundle) -> pd.DataFrame:
    """Calculate one descriptive event row per team for one canonical match."""
    events = _require_event_profile_contract(bundle)
    match_id = bundle.matches.match_id.iloc[0]
    match_minutes = float(events.elapsed_seconds.max() / 60.0) if not events.empty else float("nan")
    rows = []
    for team in bundle.teams.itertuples(index=False):
        match = bundle.matches.iloc[0]
        opponent = bundle.teams.loc[bundle.teams.team_id.ne(team.team_id)].iloc[0]
        home_away = getattr(team, "home_away", None)
        is_home = home_away == "home"
        team_score = match.get("home_score") if is_home else match.get("away_score")
        opponent_score = match.get("away_score") if is_home else match.get("home_score")
        team_events = events.loc[events.team_id.eq(team.team_id)]
        passes = team_events.loc[team_events.event_type.eq("Pass")]
        completed = passes.loc[passes.pass_outcome.isna()]
        carries = team_events.loc[team_events.event_type.eq("Carry")]
        shots = team_events.loc[team_events.event_type.eq("Shot")]
        shot_distance = _goal_distance(shots.location_x, shots.location_y).where(shots[["location_x", "location_y"]].notna().all(axis=1))
        set_play = shots.play_pattern.isin(SET_PLAY_PATTERNS) | shots.shot_type.isin(SET_PLAY_SHOT_TYPES)
        interceptions = team_events.loc[team_events.event_type.eq("Interception")]
        recoveries = team_events.loc[team_events.event_type.eq("Ball Recovery") & ~team_events.ball_recovery_failure.fillna(False).astype(bool)]
        successful_interceptions = interceptions.loc[~interceptions.outcome.isin(FAILED_INTERCEPTION_OUTCOMES)]
        high_regains = pd.concat([recoveries, successful_interceptions]).location_x.ge(HIGH_REGAIN_X).sum()
        progressive_pass_mask = _progressive(completed)
        progressive_carry_mask = _progressive(carries)
        final_third_mask = completed.location_x.lt(FINAL_THIRD_X) & completed.end_location_x.ge(FINAL_THIRD_X)
        penalty_area_mask = ~(completed.location_x.ge(PENALTY_AREA_X) & completed.location_y.between(*PENALTY_AREA_Y)) & completed.end_location_x.ge(PENALTY_AREA_X) & completed.end_location_y.between(*PENALTY_AREA_Y)
        turnover_shot_times = _turnover_shot_times(events, team.team_id)
        values = {
            "possession_share_estimate": _possession_share(events, team.team_id),
            "passes_attempted": len(passes), "passes_completed": len(completed),
            "pass_completion_rate": len(completed) / len(passes) if len(passes) else float("nan"),
            "progressive_passes": int(progressive_pass_mask.sum()),
            "passes_into_final_third": int(final_third_mask.sum()),
            "passes_into_penalty_area": int(penalty_area_mask.sum()),
            "carries": len(carries), "progressive_carries": int(progressive_carry_mask.sum()),
            "shots": len(shots), "shots_on_target": int(shots.shot_outcome.isin(SHOT_ON_TARGET_OUTCOMES).sum()),
            "goals": int(shots.shot_outcome.eq("Goal").sum()),
            "xg": float(shots.shot_xg.sum()) if shots.shot_xg.notna().any() else (0.0 if shots.empty else float("nan")),
            "average_shot_distance": float(shot_distance.mean()) if shot_distance.notna().any() else float("nan"),
            "set_play_shots": int(set_play.sum()), "open_play_shots": int((~set_play).sum()),
            "pressures": int(team_events.event_type.eq("Pressure").sum()),
            "tackles": int((team_events.event_type.eq("Duel") & team_events.duel_type.eq("Tackle")).sum()),
            "interceptions": len(interceptions), "recoveries": len(recoveries),
            "high_regains": int(high_regains),
            "turnovers_leading_to_shot": len(turnover_shot_times),
            "counter_attack_shots": int(shots.play_pattern.eq("From Counter").sum()),
            "xg_per_shot": float(shots.shot_xg.sum() / len(shots)) if len(shots) and shots.shot_xg.notna().all() else float("nan"),
        }
        if match_minutes > 0:
            for metric in COUNT_METRICS:
                values[f"{metric}_per90"] = float(values[metric]) * 90.0 / match_minutes
            values["xg_per90"] = values["xg"] * 90.0 / match_minutes if pd.notna(values["xg"]) else float("nan")
        metric_times = {
            "possession_share_estimate": team_events.loc[team_events.possession_team_id.eq(team.team_id), "elapsed_seconds"],
            "passes_attempted": passes.elapsed_seconds, "passes_completed": completed.elapsed_seconds,
            "pass_completion_rate": passes.elapsed_seconds,
            "progressive_passes": completed.loc[progressive_pass_mask, "elapsed_seconds"],
            "passes_into_final_third": completed.loc[final_third_mask, "elapsed_seconds"],
            "passes_into_penalty_area": completed.loc[penalty_area_mask, "elapsed_seconds"],
            "carries": carries.elapsed_seconds, "progressive_carries": carries.loc[progressive_carry_mask, "elapsed_seconds"],
            "shots": shots.elapsed_seconds, "shots_on_target": shots.loc[shots.shot_outcome.isin(SHOT_ON_TARGET_OUTCOMES), "elapsed_seconds"],
            "goals": shots.loc[shots.shot_outcome.eq("Goal"), "elapsed_seconds"], "xg": shots.elapsed_seconds,
            "average_shot_distance": shots.elapsed_seconds,
            "set_play_shots": shots.loc[set_play, "elapsed_seconds"], "open_play_shots": shots.loc[~set_play, "elapsed_seconds"],
            "pressures": team_events.loc[team_events.event_type.eq("Pressure"), "elapsed_seconds"],
            "tackles": team_events.loc[team_events.event_type.eq("Duel") & team_events.duel_type.eq("Tackle"), "elapsed_seconds"],
            "interceptions": interceptions.elapsed_seconds, "recoveries": recoveries.elapsed_seconds,
            "high_regains": pd.concat([recoveries, successful_interceptions]).loc[lambda frame: frame.location_x.ge(HIGH_REGAIN_X), "elapsed_seconds"],
            "turnovers_leading_to_shot": turnover_shot_times,
            "counter_attack_shots": shots.loc[shots.play_pattern.eq("From Counter"), "elapsed_seconds"],
        }
        chronology = {metric: summary for metric, times in metric_times.items() if (summary := _time_summary(times)) is not None}
        for metric in COUNT_METRICS:
            if metric in chronology:
                chronology[f"{metric}_per90"] = chronology[metric]
        if "xg" in chronology:
            chronology["xg_per90"] = chronology["xg"]
            chronology["xg_per_shot"] = chronology["xg"]
        score_state = _score_state_exposure(
            events, team.team_id, opponent.team_id, match_minutes * 60.0,
            expected_team_score=team_score, expected_opponent_score=opponent_score,
        )
        row = {
            "provider": bundle.provider, "match_id": match_id, "match_date": bundle.matches.iloc[0].get("match_date"),
            "competition_id": bundle.matches.iloc[0].get("competition_id"), "season_id": bundle.matches.iloc[0].get("season_id"),
            "team_id": team.team_id, "team_name": getattr(team, "team_name", team.team_code),
            "opponent_team_id": opponent.team_id, "opponent_team_name": getattr(opponent, "team_name", opponent.team_code),
            "home_away": home_away, "home_score": match.get("home_score"), "away_score": match.get("away_score"),
            "team_score": team_score, "opponent_score": opponent_score,
            "metric_chronology": chronology, "match_minutes": match_minutes,
            "coordinate_system": "statsbomb_120x80", **score_state, **values,
        }
        rows.append(row)
    result = pd.DataFrame(rows)
    production_to_exposure = {
        "passes_into_penalty_area": "passes_into_penalty_area_conceded",
        "shots": "shots_conceded", "xg": "xg_conceded",
        "xg_per_shot": "xg_per_shot_conceded",
        "set_play_shots": "set_play_shots_conceded",
        "counter_attack_shots": "counter_attack_shots_conceded",
    }
    for index, row in result.iterrows():
        opposition = result.loc[result.team_id.ne(row.team_id)]
        if len(opposition) != 1:
            raise ValueError("Conceded event metrics require exactly one opposition team row.")
        opposition_row = opposition.iloc[0]
        for production, exposure in production_to_exposure.items():
            result.at[index, exposure] = opposition_row[production]
            per90_production, per90_exposure = f"{production}_per90", f"{exposure}_per90"
            if per90_production in result:
                result.at[index, per90_exposure] = opposition_row[per90_production]
    return result


def build_event_team_season_profile(
    bundles: Iterable[CanonicalMatchBundle], *, team_id: str | int,
    competition_id: str | int, season_id: str | int,
) -> EventTeamSeasonProfile:
    """Aggregate match observations; never pool individual events across matches."""
    rows, excluded, team_name = [], [], None
    for bundle in bundles:
        match_id = bundle.matches.match_id.iloc[0]
        try:
            metrics = calculate_event_team_match_metrics(bundle)
            selected = metrics.loc[
                metrics.team_id.eq(team_id) & metrics.competition_id.eq(competition_id) & metrics.season_id.eq(season_id)
            ]
            if len(selected) != 1:
                raise ValueError("requested team/competition/season is absent from match")
            rows.append(selected.iloc[0].to_dict())
            team_name = str(selected.team_name.iloc[0])
        except Exception as error:
            excluded.append({"match_id": match_id, "reason": str(error)})
    match_metrics = pd.DataFrame(rows)
    return aggregate_event_team_match_metrics(
        match_metrics, team_id=team_id, team_name=team_name or str(team_id),
        competition_id=competition_id, season_id=season_id,
        matches_excluded=pd.DataFrame(excluded, columns=["match_id", "reason"]),
    )


def aggregate_event_team_match_metrics(
    match_metrics: pd.DataFrame, *, team_id: str | int, team_name: str,
    competition_id: str | int, season_id: str | int,
    matches_excluded: pd.DataFrame | None = None,
) -> EventTeamSeasonProfile:
    """Aggregate already-compact match rows without access to raw event tables."""
    match_metrics = match_metrics.copy()
    if match_metrics.empty:
        match_metrics = pd.DataFrame(columns=list(MATCH_IDENTITY_COLUMNS))
    elif match_metrics.match_id.duplicated().any():
        raise ValueError("Cannot aggregate duplicate team-match observations.")
    definitions = metric_definitions()
    aggregate_rows = []
    for definition in definitions.itertuples(index=False):
        if definition.metric not in match_metrics:
            continue
        values = pd.to_numeric(match_metrics[definition.metric], errors="coerce").dropna()
        aggregate_rows.append({
            "metric": definition.metric, "unit": definition.unit,
            "median_across_matches": float(values.median()) if not values.empty else float("nan"),
            "q25_across_matches": float(values.quantile(.25)) if not values.empty else float("nan"),
            "q75_across_matches": float(values.quantile(.75)) if not values.empty else float("nan"),
            "contributing_matches": int(len(values)), "total_matches": int(len(match_metrics)),
            "coverage": float(len(values) / len(match_metrics)) if len(match_metrics) else 0.0,
            "coordinate_system": "statsbomb_120x80" if "distance" in definition.metric or "progressive" in definition.metric or "final_third" in definition.metric or "penalty_area" in definition.metric or "high_regains" in definition.metric else pd.NA,
            "definition": definition.definition,
        })
    aggregates = pd.DataFrame(aggregate_rows)
    excluded_frame = (
        matches_excluded.copy() if matches_excluded is not None
        else pd.DataFrame(columns=["match_id", "reason"])
    )
    return EventTeamSeasonProfile(team_id, team_name, competition_id, season_id, match_metrics, aggregates, definitions, excluded_frame)
