"""Audit whether match tactical output is grounded, readable, and review-worthy.

This is deliberately a frozen product audit.  It does not alter analytical
thresholds or silently turn automated checks into claims of football insight.
The generated worksheet separates machine-verifiable correctness from the
human judgement that an analyst must still provide.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import build_match_tactical_profile
from src.api import artifact_event_profile_resolver, load_event_profile_artifact
from src.api.schemas import json_safe
from src.data import StatsBombOpenDataAdapter


FROZEN_MATCH_IDS = (
    266236,  # narrow away win
    266467,  # high-output defeat
    3825627,  # high-scoring match with unusually low possession
    266424,  # high-profile away win
    266961,  # two-goal lead lost
    266670,  # goalless control
    267576,  # win with low recorded xG
    267533,  # high-profile home defeat
    266310,  # eight-goal win
    266557,  # defeat despite high attacking output
)

SELECTION_REASONS = {
    266236: "Narrow away win and a low-event scoreline.",
    266467: "Defeat despite substantial attacking output.",
    3825627: "High-scoring win with unusually low possession for the team.",
    266424: "High-profile away win against a strong opponent.",
    266961: "Two-goal lead lost in a draw, with contrasting match periods.",
    266670: "Goalless match that tests cautious and empty goal states.",
    267576: "Win despite low recorded chance quality.",
    267533: "High-profile home defeat.",
    266310: "Eight-goal win that tests extreme-output language.",
    266557: "Defeat despite high shot and territory-related output.",
}

TECHNICAL_VISIBLE_TERMS = (
    "per 90", "robust", "distribution", "baseline", "event possession timeline",
    "season sample", "coordinate", "provider-labelled",
)
UNSUPPORTED_CAUSAL_TERMS = (
    " caused ", " because ", " mistake", "weakness", "should ", "must ",
)


def _visible_text(result: Any) -> list[str]:
    text: list[str] = []
    for team in result.team_profiles:
        text.extend((team.headline, team.overview, *team.opponent_relative_observations))
        for segment in team.segments:
            text.extend((segment.headline, segment.explanation, *segment.change_from_previous))
    for goal in result.goals:
        text.extend((
            goal.what_happened, goal.what_created_the_opportunity,
            goal.had_this_been_happening_earlier, goal.recurring_season_pattern,
            goal.structural_versus_execution,
        ))
        text.extend(item.observation for item in goal.contributors)
    return [item for item in text if item]


def _term_hits(lines: list[str], terms: tuple[str, ...]) -> list[dict[str, str]]:
    hits = []
    for line in lines:
        lowered = f" {line.lower()} "
        for term in terms:
            if term in lowered:
                hits.append({"term": term.strip(), "text": line})
    return hits


def _duplicate_segment_summary(team: Any) -> dict[str, Any]:
    labels = [segment.headline for segment in team.segments]
    unique = len(set(labels))
    return {
        "segment_count": len(labels),
        "unique_headline_count": unique,
        "repeated_headline_count": len(labels) - unique,
        "repetition_share": round((len(labels) - unique) / len(labels), 3) if labels else 0.0,
    }


def audit_result(result: Any) -> dict[str, Any]:
    """Return only reproducible checks; football usefulness remains human-rated."""
    visible = _visible_text(result)
    official_goals = int(result.match_identity.get("home_score", 0) or 0) + int(result.match_identity.get("away_score", 0) or 0)
    technical_hits = _term_hits(visible, TECHNICAL_VISIBLE_TERMS)
    causal_hits = _term_hits(visible, UNSUPPORTED_CAUSAL_TERMS)
    broad_recurrence = []
    for goal in result.goals:
        for contributor in goal.contributors:
            metric = str(contributor.evidence.get("metric", ""))
            if contributor.category in {"recurring_structural_pattern", "opponent_recurring_attacking_strength"} and metric.endswith("_shots_per90"):
                broad_recurrence.append({
                    "goal_id": goal.goal_id,
                    "category": contributor.category,
                    "metric": metric,
                    "wording": contributor.observation,
                    "issue": "A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.",
                })
    empty_sequences = [goal.goal_id for goal in result.goals if not goal.preceding_actions]
    generic_goal_history = [
        goal.goal_id for goal in result.goals
        if "regular play" in goal.sequence_origin.lower()
        and "earlier shot" in goal.had_this_been_happening_earlier.lower()
    ]
    return {
        "goal_count_check": {
            "official_score_total": official_goals,
            "analysed_goal_count": len(result.goals),
            "passed": official_goals == len(result.goals),
        },
        "both_teams_present": len(result.team_profiles) == 2,
        "technical_language_hits": technical_hits,
        "unsupported_causal_language_hits": causal_hits,
        "broad_recurrence_scope_flags": broad_recurrence,
        "empty_goal_sequences": empty_sequences,
        "generic_open_play_history_flags": generic_goal_history,
        "segment_repetition": {
            str(team.team_id): _duplicate_segment_summary(team) for team in result.team_profiles
        },
        "human_review_required": True,
        "human_review_reason": "Correctness checks cannot determine whether an observation is interesting, important, or useful to a football analyst.",
    }


def _compact_result(result: Any, selection_reason: str) -> dict[str, Any]:
    return {
        "match_id": result.match_id,
        "provider": result.provider,
        "date": result.match_identity.get("date"),
        "score": f"{result.match_identity.get('home_score', '?')}-{result.match_identity.get('away_score', '?')}",
        "selection_reason": selection_reason,
        "teams": [{
            "team_id": team.team_id,
            "team_name": team.team_name,
            "opponent": team.opponent_team_name,
            "headline": team.headline,
            "season_relative_observation_count": len(team.style_deviations),
            "top_observations": [item.football_summary for item in team.style_deviations[:3]],
            "window_count": len(team.segments),
            "changed_window_count": sum(bool(item.change_from_previous) for item in team.segments),
        } for team in result.team_profiles],
        "goals": [{
            "goal_id": goal.goal_id,
            "time": f"{goal.minute}:{goal.second:02d}",
            "scoring_team": goal.scoring_team_name,
            "what_happened": goal.what_happened,
            "opportunity": goal.what_created_the_opportunity,
            "earlier_in_match": goal.had_this_been_happening_earlier,
            "season_recurrence": goal.recurring_season_pattern,
            "structure_or_execution": goal.structural_versus_execution,
            "contributor_categories": [item.category for item in goal.contributors],
        } for goal in result.goals],
        "automated_audit": audit_result(result),
        "human_scorecard": {
            "accurate_and_useful": None,
            "correct_but_obvious": None,
            "technically_correct_but_confusing": None,
            "unsupported": None,
            "important_pattern_missed": None,
            "would_review_video": None,
            "analyst_notes": "",
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = []
    detail = []
    for match in payload["matches"]:
        audit = match["automated_audit"]
        repetitions = [item["repetition_share"] for item in audit["segment_repetition"].values()]
        rows.append(
            f"| {match['match_id']} | {match['date']} | {match['score']} | "
            f"{len(match['goals'])} | {len(audit['technical_language_hits'])} | "
            f"{len(audit['broad_recurrence_scope_flags'])} | {max(repetitions, default=0):.0%} |"
        )
        teams = "\n".join(
            f"- **{team['team_name']}:** {team['headline']}"
            for team in match["teams"]
        )
        goals = "\n".join(
            f"- **{goal['time']} — {goal['scoring_team']}:** {goal['opportunity']} "
            f"_Season check:_ {goal['season_recurrence']}"
            for goal in match["goals"]
        ) or "- No goals to investigate."
        flags = audit["broad_recurrence_scope_flags"]
        flag_text = "\n".join(f"- {item['goal_id']}: {item['issue']}" for item in flags) or "- None."
        detail.append(f"""## Match {match['match_id']} — {match['date']} — {match['score']}

**Why selected:** {match['selection_reason']}

### Current first impression

{teams}

### Goal explanations

{goals}

### Automated correctness/copy flags

- Goal count agrees with recorded score: **{'Yes' if audit['goal_count_check']['passed'] else 'No'}**
- Technical-language hits in visible copy: **{len(audit['technical_language_hits'])}**
- Unsupported causal-language hits: **{len(audit['unsupported_causal_language_hits'])}**
- Empty goal sequences: **{len(audit['empty_goal_sequences'])}**
- Generic open-play history comparisons: **{len(audit['generic_open_play_history_flags'])}**

Broad recurrence-scope flags:

{flag_text}

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**
""")
    summary = payload["summary"]
    return f"""# TactIQ post-match proof-of-value audit

## Purpose

This is a frozen ten-match validation sample. It asks whether TactIQ produces a small number of understandable, grounded observations that a football analyst would actually investigate. It does **not** treat automated checks as a substitute for football judgement.

## Automated audit summary

- Matches: **{summary['matches']}**
- Goals expected from recorded scores: **{summary['official_goals']}**
- Goals analysed: **{summary['analysed_goals']}**
- Matches with complete goal coverage: **{summary['matches_with_complete_goal_coverage']}/{summary['matches']}**
- Visible technical-language hits: **{summary['technical_language_hits']}**
- Unsupported causal-language hits: **{summary['unsupported_causal_language_hits']}**
- Broad recurrence claims needing scope correction: **{summary['broad_recurrence_scope_flags']}**
- Empty goal sequences: **{summary['empty_goal_sequences']}**

| Match | Date | Score | Goals | Technical copy flags | Recurrence-scope flags | Max segment repetition |
| --- | --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## What the machine audit can and cannot establish

It can verify goal coverage, evidence presence, prohibited causal wording, recurrence provenance, and repetitive copy. It cannot decide whether the engine identified the match's most important tactical pattern. That requires reviewing footage or an independent trusted match account.

## Acceptance target for the next product milestone

Across this frozen sample, a knowledgeable reviewer should mark at least 70% of shortlisted observations **accurate and useful**, fewer than 10% **unsupported**, and identify no systematic mismatch between a goal explanation and its evidence sequence. Until that happens, TactIQ should remain a research MVP rather than claim reliable pundit-level analysis.

{chr(10).join(detail)}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--statsbomb-root", default="external_data/statsbomb_open_data")
    parser.add_argument("--target-profile", default="artifacts/event_profiles/statsbomb_11_27/statsbomb_11_27_217_event_profile_v1.json")
    parser.add_argument("--json", default="artifacts/post_match_product_value_audit.json")
    parser.add_argument("--report", default="docs/post_match_product_value_audit.md")
    options = parser.parse_args()

    target = load_event_profile_artifact(options.target_profile)
    profile_resolver = artifact_event_profile_resolver(options.artifact_root)
    adapter = StatsBombOpenDataAdapter(options.statsbomb_root)
    records = []
    for match_id in FROZEN_MATCH_IDS:
        match_row = target.match_metrics.loc[target.match_metrics.match_id.eq(match_id)]
        if len(match_row) != 1:
            raise ValueError(f"Frozen match {match_id} is absent from the target profile.")
        opponent_id = match_row.iloc[0].opponent_team_id
        profiles = {target.team_id: target}
        try:
            opponent = profile_resolver("statsbomb_open_data", opponent_id, target.competition_id, target.season_id)
            profiles[opponent.team_id] = opponent
        except KeyError:
            pass
        result = build_match_tactical_profile(adapter.load_match(match_id), event_team_profiles=profiles)
        records.append(_compact_result(result, SELECTION_REASONS[match_id]))

    audits = [record["automated_audit"] for record in records]
    payload = {
        "schema_version": "tactiq.post-match-product-value-audit.v1",
        "frozen_match_ids": list(FROZEN_MATCH_IDS),
        "target_team": {"team_id": target.team_id, "team_name": target.team_name},
        "summary": {
            "matches": len(records),
            "official_goals": sum(item["goal_count_check"]["official_score_total"] for item in audits),
            "analysed_goals": sum(item["goal_count_check"]["analysed_goal_count"] for item in audits),
            "matches_with_complete_goal_coverage": sum(item["goal_count_check"]["passed"] for item in audits),
            "technical_language_hits": sum(len(item["technical_language_hits"]) for item in audits),
            "unsupported_causal_language_hits": sum(len(item["unsupported_causal_language_hits"]) for item in audits),
            "broad_recurrence_scope_flags": sum(len(item["broad_recurrence_scope_flags"]) for item in audits),
            "empty_goal_sequences": sum(len(item["empty_goal_sequences"]) for item in audits),
        },
        "matches": records,
    }
    json_path, report_path = Path(options.json), Path(options.report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_safe(payload)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
