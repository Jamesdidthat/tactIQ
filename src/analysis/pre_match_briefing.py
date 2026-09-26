"""Deterministic briefing assembly over selected pre-match review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .opponent_comparison import OpponentComparisonResult
from .pre_match_review import PreMatchReviewPriority, PreMatchReviewResult


@dataclass(frozen=True)
class PreMatchBriefingPriority:
    priority_id: str
    rank: int
    title: str
    review_question: str
    evidence_summary: str
    evidence_support: str
    primary_source_role: str
    direction: str
    football_family: str
    evidence_pack_link: str


@dataclass(frozen=True)
class PreMatchBriefing:
    matchup_identity: dict[str, Any]
    target_team: dict[str, Any]
    opponent_team: dict[str, Any]
    competition: dict[str, Any]
    season: dict[str, Any]
    briefing_summary: str
    review_priorities: tuple[PreMatchBriefingPriority, ...]
    evidence_pack_links: dict[str, str]
    key_comparison_context: tuple[dict[str, Any], ...]
    directional_matchup_context: tuple[dict[str, Any], ...]
    data_capabilities: dict[str, Any]
    limitations: tuple[str, ...]
    video_availability: dict[str, Any]

    def __post_init__(self) -> None:
        if len(self.review_priorities) > 5:
            raise ValueError("Pre-match briefing cannot contain more than five review priorities.")
        ranks = [item.rank for item in self.review_priorities]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("Pre-match briefing must preserve contiguous ranked priority order.")
        priority_ids = [item.priority_id for item in self.review_priorities]
        if len(priority_ids) != len(set(priority_ids)):
            raise ValueError("Pre-match briefing priority IDs must be unique.")
        if set(priority_ids) != set(self.evidence_pack_links):
            raise ValueError("Every briefing priority must have exactly one Evidence Pack link.")
        if any(item.evidence_pack_link != self.evidence_pack_links[item.priority_id] for item in self.review_priorities):
            raise ValueError("Briefing priority links and Evidence Pack link index disagree.")


def _format_value(value: Any, unit: str) -> str:
    number = float(value)
    if unit == "proportion":
        return f"{number * 100:.1f}%"
    if unit == "xG":
        return f"{number:.2f} xG"
    if unit == "xG_per_90":
        return f"{number:.2f} xG per 90"
    if unit in {"per_90", "count_per_90"}:
        return f"{number:.1f} per 90"
    if unit == "native_120x80_units":
        return f"{number:.1f} native units"
    return f"{number:.1f}"


def _overlap_wording(primary: dict[str, Any]) -> str:
    overlap = primary.get("distributions_materially_overlap")
    if overlap is True:
        return "the season interquartile ranges materially overlap"
    if overlap is False:
        return "the season interquartile ranges have limited overlap"
    return "distribution overlap is unavailable"


def _priority_evidence_summary(priority: PreMatchReviewPriority) -> str:
    target = priority.target_baseline
    opponent = priority.opponent_baseline
    unit = str(target.get("unit") or opponent.get("unit") or "")
    target_value = _format_value(target["median"], unit)
    opponent_value = _format_value(opponent["median"], unit)
    overlap = _overlap_wording(priority.primary_evidence)
    if priority.primary_source_role == "directional_matchup_interaction":
        baselines = (target, opponent)
        attack = next(item for item in baselines if item.get("role") == "attacking_production")
        defence = next(item for item in baselines if item.get("role") == "defensive_exposure")
        attack_value = target_value if attack is target else opponent_value
        defence_value = target_value if defence is target else opponent_value
        return (
            f"{attack['team_name']} attacking median: {attack_value}; "
            f"{defence['team_name']} defensive-exposure median: {defence_value}; {overlap}."
        )
    return (
        f"{opponent['team_name']} season median: {opponent_value}; "
        f"{target['team_name']} season median: {target_value}; {overlap}."
    )


def _evidence_pack_link(identity: tuple[Any, ...], priority_id: str) -> str:
    encoded_identity = "/".join(quote(str(value), safe="") for value in identity)
    return (
        f"/opponent-comparisons/{encoded_identity}/review-priorities/"
        f"{quote(priority_id, safe='')}/evidence-pack"
    )


def _executive_summary(priorities: list[PreMatchReviewPriority]) -> str:
    count = len(priorities)
    if count == 0:
        return (
            "No matchup themes qualified for review. This does not mean the matchup lacks important tactical questions."
        )
    if count == 1:
        return f"One matchup theme qualified for review: {priorities[0].title}."
    leading = " and ".join(f"“{item.title}”" for item in priorities[:2])
    return f"{count} matchup themes qualified for review. The leading themes are {leading}."


def build_pre_match_briefing(
    review: PreMatchReviewResult,
    comparison: OpponentComparisonResult,
    *,
    identity: tuple[Any, ...],
) -> PreMatchBriefing:
    """Assemble selected evidence into a compact briefing without new claims."""
    if len(identity) != 8:
        raise ValueError("Pre-match briefing identity requires target and opponent provider/team/competition/season.")
    selected = list(review.priorities)
    links = {
        priority.priority_id: _evidence_pack_link(identity, priority.priority_id)
        for priority in selected
    }
    summaries = tuple(PreMatchBriefingPriority(
        priority_id=priority.priority_id,
        rank=priority.rank,
        title=priority.title,
        review_question=priority.review_question,
        evidence_summary=_priority_evidence_summary(priority),
        evidence_support=priority.evidence_basis,
        primary_source_role=priority.primary_source_role,
        direction=priority.direction,
        football_family=priority.football_family,
        evidence_pack_link=links[priority.priority_id],
    ) for priority in selected)
    general_context = tuple({
        "priority_id": priority.priority_id,
        "rank": priority.rank,
        "metric": priority.primary_evidence.get("metric"),
        "target_baseline": priority.target_baseline,
        "opponent_baseline": priority.opponent_baseline,
        "distributions_materially_overlap": priority.primary_evidence.get("distributions_materially_overlap"),
    } for priority in selected if priority.primary_source_role == "general_team_comparison")
    directional_context = tuple({
        "priority_id": priority.priority_id,
        "rank": priority.rank,
        "direction": priority.direction,
        "production_metric": priority.primary_evidence.get("production_metric"),
        "exposure_metric": priority.primary_evidence.get("exposure_metric"),
        "attacking_or_target_baseline": priority.target_baseline,
        "defending_or_opponent_baseline": priority.opponent_baseline,
        "distributions_materially_overlap": priority.primary_evidence.get("distributions_materially_overlap"),
    } for priority in selected if priority.primary_source_role == "directional_matchup_interaction")
    target, opponent = dict(review.target), dict(review.opponent)
    shared_competition = (
        target.get("competition_id") == opponent.get("competition_id")
        and target.get("competition_name") == opponent.get("competition_name")
    )
    shared_season = (
        target.get("season_id") == opponent.get("season_id")
        and target.get("season_name") == opponent.get("season_name")
    )
    return PreMatchBriefing(
        matchup_identity={
            "id": ":".join(map(str, identity)),
            "target_team_id": target["team_id"],
            "opponent_team_id": opponent["team_id"],
            "comparison_type": "event_team_season",
        },
        target_team=target,
        opponent_team=opponent,
        competition={
            "shared": shared_competition,
            "target": {"id": target.get("competition_id"), "name": target.get("competition_name")},
            "opponent": {"id": opponent.get("competition_id"), "name": opponent.get("competition_name")},
        },
        season={
            "shared": shared_season,
            "target": {"id": target.get("season_id"), "name": target.get("season_name")},
            "opponent": {"id": opponent.get("season_id"), "name": opponent.get("season_name")},
        },
        briefing_summary=_executive_summary(selected),
        review_priorities=summaries,
        evidence_pack_links=links,
        key_comparison_context=general_context,
        directional_matchup_context=directional_context,
        data_capabilities={
            "comparable": comparison.compatibility.get("comparable", False),
            "provider_rule": comparison.compatibility.get("provider_rule"),
            "coordinate_system": comparison.compatibility.get("coordinate_system"),
            "required_capabilities": comparison.compatibility.get("required_capabilities", ()),
            "target_capabilities": comparison.compatibility.get("target_capabilities", {}),
            "opponent_capabilities": comparison.compatibility.get("opponent_capabilities", {}),
            "continuous_tracking_used": False,
        },
        limitations=(
            "The briefing organizes selected historical season evidence; it does not add analytical claims, causal interpretation, recommendations, or predictions.",
            "Each team's values come from separate match-level season distributions and do not describe the future head-to-head match.",
            "Representative events and detailed provenance remain in the linked Evidence Packs.",
        ),
        video_availability={
            "status": "unavailable",
            "message": "Linked match video is unavailable in the configured source data.",
        },
    )
