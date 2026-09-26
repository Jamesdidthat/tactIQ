"""Generate a product QA audit for contrasting deterministic Match Stories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import assemble_match_story
from src.api import load_event_profile_artifact


AUDIT_MATCHES = (266961, 266620, 266653, 3825627, 266166)

SELECTION_RATIONALE = {
    266961: "Four-point mixed story spanning a relationship, archetype, and single metrics.",
    266620: "Relationship-led story with two archetypes and progression-related overlap risk.",
    266653: "Maximum-length five-point story with transition/direct-attack evidence.",
    3825627: "Strong chance-conversion residual but no qualifying archetype.",
    266166: "Zero-point control case for empty-state and threshold behavior.",
}

# These are deliberately product-review judgments, not calculated labels. Keeping
# them beside the generated evidence makes the human QA layer explicit and easy
# to revise without changing the story assembler.
MANUAL_QA = {
    266961: {
        "coherent": "Partial",
        "redundant": "Yes — the shot-volume/xG-per-shot archetype and longer-shot-distance point both describe shot quality from related angles.",
        "too_statistical": "Partial — ‘expected’ needs its season-relationship comparator visible to a football user.",
        "missing_context": "Opponent, result, venue and match-state context are absent; the turnover-exposure point feels detached from the three attacking points.",
        "misleadingly_strong": "Possible — Strong means robust season deviation, not certainty or tactical importance.",
        "verdict": "Useful attacking outline, but one semantic duplicate remains and the fourth point does not form a continuous narrative.",
    },
    266620: {
        "coherent": "Partial",
        "redundant": "Yes — progression appears in both the relationship residual and an archetype, despite the metrics not crossing the current overlap threshold.",
        "too_statistical": "Yes — multiple robust relationship/archetype concepts require the expanded evidence to understand.",
        "missing_context": "No opponent, score, home/away or match-state explanation; the story does not say whether progression translated into territory or chances in plain sequence order.",
        "misleadingly_strong": "Possible — high component scores can make an internally overlapping story look more conclusive than it is.",
        "verdict": "Evidence-rich but cognitively dense; it exposes semantic redundancy that metric-set overlap alone does not suppress.",
    },
    266653: {
        "coherent": "Partial",
        "redundant": "Yes — two archetypes plus a relationship and single metrics create a long list with overlapping transition/direct-attack themes.",
        "too_statistical": "Yes — five points is heavy, and relationship residuals plus rule strengths compete for attention.",
        "missing_context": "No sequence timing, opponent shape, score state, or explicit explanation tying high regains to the attacking observations.",
        "misleadingly_strong": "Possible — the full five-point story looks comprehensive although every statement remains descriptive and season-relative.",
        "verdict": "Shows the value of diversity, but also the current upper-bound problem: five qualified points can still be too much for a coherent match story.",
    },
    3825627: {
        "coherent": "Partial",
        "redundant": "No material metric duplication; the points are instead weakly connected.",
        "too_statistical": "Partial — the shots→xG expectation is meaningful but needs a football-readable comparator in the collapsed view.",
        "missing_context": "The chance-creation, interception and possession observations are not joined by match phase, score state, or chronology.",
        "misleadingly_strong": "Yes, potentially — all three are Strong robust deviations, which can read like three confirmed tactical conclusions.",
        "verdict": "The leading point is useful; the remaining points are notable facts rather than a coherent story arc.",
    },
    266166: {
        "coherent": "Not applicable — no point passed the evidence and redundancy gates.",
        "redundant": "No.",
        "too_statistical": "No visible story, but the empty state should explain that ordinary does not mean uneventful.",
        "missing_context": "The zero-point result gives no account of the match and cannot distinguish ‘typical relative to baseline’ from unavailable or tactically uneventful.",
        "misleadingly_strong": "No; the fail-closed behavior is appropriately cautious.",
        "verdict": "Correctly unpadded. Product copy must avoid implying that no unusual season-relative metric means there was no match story.",
    },
}


def _match_context(metadata_path: Path, team_id: int) -> dict[int, dict]:
    records = json.loads(metadata_path.read_text(encoding="utf-8"))
    context = {}
    for match in records:
        match_id = match["match_id"]
        if match_id not in AUDIT_MATCHES:
            continue
        home = match["home_team"]
        away = match["away_team"]
        is_home = home["home_team_id"] == team_id
        opponent = away["away_team_name"] if is_home else home["home_team_name"]
        context[match_id] = {
            "date": match.get("match_date"),
            "opponent": opponent,
            "venue": "Home" if is_home else "Away",
            "score": f"{match.get('home_score', '?')}–{match.get('away_score', '?')}",
        }
    return context


def _table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default="artifacts/statsbomb_barcelona_2015_2016_event_profile_v1.json")
    parser.add_argument("--matches", default="external_data/statsbomb_open_data/data/matches/11/27.json")
    parser.add_argument("--report", default="docs/barcelona_2015_2016_match_story_qa.md")
    options = parser.parse_args()

    profile = load_event_profile_artifact(options.artifact)
    context = _match_context(Path(options.matches), int(profile.team_id))
    all_stories = {match_id: assemble_match_story(profile, match_id) for match_id in profile.match_metrics.match_id}
    zero = [match_id for match_id, story in all_stories.items() if not story.story_points]
    one = [match_id for match_id, story in all_stories.items() if len(story.story_points) == 1]

    sections = []
    for match_id in AUDIT_MATCHES:
        story = all_stories[match_id]
        match_context = context.get(match_id, {})
        rows = [[
            index,
            point.title,
            point.story_type.replace("metric_relationship_residual", "relationship").replace("match_archetype", "archetype").replace("single_metric_deviation", "single-metric"),
            f"{point.priority_score:.3f}",
            point.evidence_level.title(),
            ", ".join(metric["metric"] for metric in point.supporting_metrics),
        ] for index, point in enumerate(story.story_points, 1)]
        story_table = _table(
            ["Order", "Story point", "Source", "Score", "Evidence", "Supporting metrics"],
            rows,
        ) if rows else "*No story point passed the deterministic qualification and redundancy gates.*"
        qa = MANUAL_QA[match_id]
        sections.append(f"""## Match {match_id} — {match_context.get('venue', 'Venue unavailable')} vs {match_context.get('opponent', 'opponent unavailable')}

**Date:** {match_context.get('date', 'Unavailable')}  
**Recorded score:** {match_context.get('score', 'Unavailable')}  
**Selection reason:** {SELECTION_RATIONALE[match_id]}

{story_table}

### Manual product review

{_table(
    ["Check", "Assessment"],
    [
        ["Coherent", qa["coherent"]],
        ["Redundant", qa["redundant"]],
        ["Too statistical", qa["too_statistical"]],
        ["Missing obvious context", qa["missing_context"]],
        ["Misleadingly strong", qa["misleadingly_strong"]],
    ],
)}

**QA verdict:** {qa['verdict']}
""")

    report = f"""# Barcelona 2015/16 Match Story product QA

## Scope

This audit reviews five deliberately contrasting Barcelona matches. It evaluates the current deterministic output as a product narrative; it does not change thresholds, ranking, redundancy, archetype, or relationship logic. Scores below are internal deterministic priority scores, not probabilities or statistical confidence.

## Season-wide shortlist coverage

- Analysed matches: **{len(all_stories)}**
- Matches with zero qualifying story points: **{len(zero)}** — {', '.join(map(str, zero))}
- Matches with only one qualifying story point: **{len(one)}** — {', '.join(map(str, one))}
- Five-match audit sample: **{', '.join(map(str, AUDIT_MATCHES))}**

{"\n\n".join(sections)}

## Cross-match failure modes

1. **Semantic redundancy is broader than metric overlap.** Related shot-quality or progression observations can survive because their exact metric sets differ.
2. **Diversity does not guarantee narrative coherence.** Points from attacking output, defensive activity and possession can be individually valid while lacking a joined match story.
3. **Relationship and archetype evidence remains cognitively statistical.** Collapsed cards need observed-versus-expected wording; robust z-scores and rule strengths belong in expanded evidence.
4. **Evidence labels can be over-read.** `Strong` currently describes robust season-relative deviation and coverage, not causal certainty, tactical importance, or repeatability.
5. **Match context is absent.** Opponent, result, venue, score state and chronology are not inputs to story selection, so the assembler cannot explain when or why observations occurred.
6. **Maximum-length stories can still feel overfilled.** Five diverse qualified points may be less useful than a tighter two- or three-point account.
7. **Zero-point behavior is cautious but ambiguous.** It correctly avoids padding, yet users need to understand that ‘no unusual season-relative evidence’ does not mean ‘nothing happened’.

## Product conclusion

The layer reliably produces traceable observations and fails closed, but it is not yet consistently a coherent *story*. The most important next design questions are semantic redundancy, context-aware linking, and whether source diversity should remain subordinate to narrative unity. No ranking changes were made during this audit.
"""
    report_path = Path(options.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"matches_audited={len(AUDIT_MATCHES)} zero={len(zero)} one={len(one)} report={report_path}")


if __name__ == "__main__":
    main()
