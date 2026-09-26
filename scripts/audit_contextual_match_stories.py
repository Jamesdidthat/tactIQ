"""Generate the second Barcelona Match Story product QA audit.

This script is intentionally read-only with respect to story logic. Human review
judgments are explicit constants; generated story evidence always comes from the
current persisted profile and assembler.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import assemble_match_story
from src.api import load_event_profile_artifact


AUDIT_MATCHES = (266961, 266620, 266653, 266254, 3825617, 266670, 267327, 3825627, 266664, 266166)

MANUAL_REVIEW = {
    266961: (
        "Yes", "Low", "High", "Yes — the 2–2 result and equal leading/drawing exposure make the observations easier to situate.",
        "Natural: territorial access → shot-quality combination → shot location.", "None; shot location adds a concrete dimension to the shot-quality point.",
        "Moderate risk — the relationship-led point displays High after merging a stronger same-topic single metric, although the relationship residual itself was Moderate.",
    ),
    266620: (
        "Mostly", "Moderate — progressive passes appear in both the relationship and chance-creation archetype across adjacent topics.", "Moderate to high",
        "Yes — Barcelona led for 92% of a 4–0, which is important descriptive context for the sustained attacking profile.",
        "Natural: progression → penalty-area access → chance creation.", "The archetype partly repeats the progression point, but adds xG.",
        "Moderate risk: one High and two lower-basis points are distinguishable, but users may still equate basis with importance.",
    ),
    266653: (
        "Partial", "Low at the exact-topic level; conceptual overlap remains between counter attacks and high progression/chance creation.", "Moderate",
        "Yes — an away 5–1 with 77% leading exposure helps frame the large attacking outputs without explaining them.",
        "Mostly natural, but the set-play-shot point follows an open/transition sequence awkwardly.", "Set-play shot volume feels detached from the transition-led story.",
        "Moderate risk: three separate basis labels are useful, but the complete three-point display can look more unified than the evidence is.",
    ),
    266254: (
        "Mostly", "Low — the two archetypes use distinct metric combinations.", "High",
        "Yes — the 6–1 result and roughly equal drawing/leading exposure show that much of the match was not simply played with a long-established lead.",
        "Natural as defensive activity/transition → progression/chance creation.", "No clearly detached point, but aggregate chronology cannot prove the two patterns belonged to the same passages.",
        "Moderate to high risk: both archetypes display High and may look like established match identities rather than unusually strong season-relative combinations.",
    ),
    3825617: (
        "Partial", "Low by topic, though penalty-area access and set-play shot volume are both routes to attacking territory.", "High",
        "Yes — the away 1–2 loss and 45% trailing exposure materially temper a purely attacking reading.",
        "Broadly natural: territorial relationship before shot-source quantity.", "Set-play shots are not clearly connected to the final-third→penalty-area relationship.",
        "Moderate risk — both display High, and the relationship point inherits that basis after same-topic merging even though its residual alone was weaker.",
    ),
    266670: (
        "Yes", "Low — shot quantity and on-target output are adjacent but distinct stages.", "High",
        "Yes — 100% drawing exposure in a 0–0 strongly contextualizes the low attacking-output observations.",
        "Natural: open-play shot quantity → shots on target.", "None.",
        "Low risk; the labels describe basis rather than certainty, though both points can still be mistaken for explanations of the draw.",
    ),
    267327: (
        "No", "Low — the metrics differ, but diversity is not coherence.", "High",
        "Partly — opponent, venue and 4–0 score help, but score-state exposure is correctly unavailable because the event tally did not reconcile.",
        "Syntactically ordered from high regains to shots, but no evidence connects fewer high regains with more set-play shots.",
        "Both selected points feel detached from each other.",
        "Moderate risk: two qualified points can look like a narrative despite the absence of a relationship or archetype connecting them.",
    ),
    3825627: (
        "Yes — as a deliberately single-point story.", "None", "High",
        "Yes — the 5–2 and mixed score-state exposure are useful context, while the assembler avoids attaching unrelated possession/interception points.",
        "Natural; there is only one leading observation.", "None.",
        "Moderate risk: Evidence basis: High may still be read as certainty, but limitations and expected-value evidence are available.",
    ),
    266664: (
        "Yes — as a single observation, not a complete account.", "None", "High",
        "Yes — trailing for 96% of a 0–1 loss makes recovery volume easier to inspect, without supporting a causal explanation.",
        "Natural; one point.", "None, but the observation alone is too narrow to summarize the match.",
        "Low risk: Limited accurately tempers the single defensive-activity observation, though it does not indicate narrative completeness.",
    ),
    266166: (
        "Appropriately absent", "None", "High",
        "Yes — the away 2–1 win and mixed score state remain visible even though no unusual pattern qualifies.",
        "Not applicable.", "No point is invented; the explicit state correctly distinguishes no qualifying pattern from no important events.",
        "No finding label is shown, so there is no certainty overstatement.",
    ),
}

REVIEW_FIELDS = (
    "Narrative coherence", "Semantic redundancy", "Football readability",
    "Does context materially help?", "Natural ordering", "Detached point",
    "Could evidence basis be misread?",
)


def _table(headers: tuple[str, ...] | list[str], rows: list[list[object]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in row) + " |" for row in rows)
    return "\n".join(output)


def _percent(value: object) -> str:
    return "Unavailable" if value is None else f"{float(value) * 100:.0f}%"


def _minutes(point) -> str:
    if not point.chronology.get("available"):
        return "Unavailable"
    return f"{int(point.chronology['first_seconds'] // 60)}′–{int(point.chronology['last_seconds'] // 60) + 1}′"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default="artifacts/statsbomb_barcelona_2015_2016_event_profile_v1.json")
    parser.add_argument("--report", default="docs/barcelona_2015_2016_contextual_match_story_qa.md")
    args = parser.parse_args()
    profile = load_event_profile_artifact(args.artifact)
    stories = {match_id: assemble_match_story(profile, match_id) for match_id in profile.match_metrics.match_id}

    sections = []
    for match_id in AUDIT_MATCHES:
        result = stories[match_id]
        context = result.match_context
        exposure = context["score_state_exposure"]
        context_line = (
            f"**{context.get('home_away', 'Venue unavailable').title()} vs {context.get('opponent_team_name') or 'opponent unavailable'} · "
            f"team-relative score {context.get('team_relative_score') or 'unavailable'} · {context.get('match_date') or 'date unavailable'}**"
        )
        score_line = (
            f"Score-state exposure: leading {_percent(exposure['leading']['share'])} · "
            f"drawing {_percent(exposure['drawing']['share'])} · trailing {_percent(exposure['trailing']['share'])} · "
            f"source `{context.get('score_state_source') or 'unavailable'}`"
        )
        story_rows = [[
            index, point.title,
            point.story_type.replace("metric_relationship_residual", "Relationship").replace("match_archetype", "Archetype").replace("single_metric_deviation", "Single-metric"),
            point.semantic_topic.replace("_", " "), f"{point.priority_score:.3f}",
            point.evidence_basis, ", ".join(metric["metric"] for metric in point.supporting_metrics), _minutes(point),
        ] for index, point in enumerate(result.story_points, 1)]
        story_table = _table(
            ["#", "Story point", "Source", "Topic", "Internal score", "Evidence basis", "Supporting metrics", "Event span"],
            story_rows,
        ) if story_rows else f"**State:** `{result.status}`  \n**Product wording:** {result.message}"
        review_rows = [[field, value] for field, value in zip(REVIEW_FIELDS, MANUAL_REVIEW[match_id])]
        sections.append(f"""## Match {match_id}

{context_line}  
{score_line}

{story_table}

### Manual product assessment

{_table(["Question", "Assessment"], review_rows)}
""")

    counts = {size: sum(len(result.story_points) == size for result in stories.values()) for size in range(5)}
    audited_counts = {size: sum(len(stories[match_id].story_points) == size for match_id in AUDIT_MATCHES) for size in range(5)}
    comparison_rows = [
        ["Semantic redundancy exceeded exact metric overlap", "Improved", "One selected point per semantic topic; same-topic metrics are merged.", "Cross-topic overlap remains, notably progression inside a chance-creation archetype in 266620."],
        ["Source diversity did not ensure coherence", "Improved", "Selection now chooses a topical narrative component; source diversity is secondary.", "266653 and 267327 still combine points that are ordered but not demonstrably connected."],
        ["Relationship/archetype language was too statistical", "Improved", "Collapsed cards use observed-versus-expected evidence and football-readable titles.", "‘Expected’ and multi-metric archetypes still require expanded definitions for full understanding."],
        ["Strong evidence could be read as certainty", "Improved, not eliminated", "Cards now say Evidence basis: High/Moderate/Limited.", "High can still be mistaken for tactical importance; a merged topic can also inherit High from a single metric when its relationship residual was only Moderate."],
        ["Opponent, result, venue, score state and chronology absent", "Materially improved", "All are attached where verified; compact event spans are shown.", "Context organizes interpretation but does not connect aggregate findings to the same passage of play; five score-state timelines remain unavailable."],
        ["Five-point stories felt overfilled", "Resolved in this season", "Default cap is four; no Barcelona story currently exceeds three points.", "Three points can still be too many when unity is weak, as in 266653."],
        ["Zero-point state was ambiguous", "Resolved", "Explicit wording says no unusual season-relative pattern qualified and does not deny important events.", "The state still cannot provide a match account, by design."],
    ]
    report = f"""# Barcelona 2015/16 context-aware Match Story QA

## Audit constraints

This is a frozen product audit of the context-aware assembler. No qualification,
ranking, topic, merge, context, chronology, selection, or wording logic was changed
during the audit. Internal scores are recorded for traceability and are not
probabilities or confidence estimates.

## Coverage

- Full season: **{len(stories)} matches**
- Full-season story-length distribution: **0 points: {counts[0]} · 1 point: {counts[1]} · 2 points: {counts[2]} · 3 points: {counts[3]} · 4 points: {counts[4]}**
- Audit sample: **{len(AUDIT_MATCHES)} matches**
- Audit story-length distribution: **0 points: {audited_counts[0]} · 1 point: {audited_counts[1]} · 2 points: {audited_counts[2]} · 3 points: {audited_counts[3]} · 4 points: {audited_counts[4]}**
- Source coverage: relationship-led, archetype-led, single-metric-only, and zero-point states are all represented.
- Score-state coverage: long-leading wins, all-drawing match, long-trailing loss, mixed-state matches, and one safely unavailable timeline are represented.

{"\n\n".join(sections)}

## Explicit comparison with first-QA failure modes

{_table(["Previous failure mode", "Current status", "Observed improvement", "Remaining risk"], comparison_rows)}

## Overall product judgment

The refactor materially improved shortlist length, exact semantic duplication,
context visibility, and fail-closed behavior. The strongest outputs are 266961,
266620, 266670 and the deliberately single-point 3825627. The principal remaining
failure mode is **false narrative unity**: topical adjacency and broad chronology
can organize observations but cannot prove that they arose from the same match
passages. Match 267327 is the clearest failure, while 266653 remains partially
overfilled by a detached set-play point. Evidence-basis wording is safer than the
old confidence-like label, but `High` still needs its visible definition as
season-relative evidence adequacy rather than tactical certainty. Merged points
can also inherit the highest basis from a secondary candidate, potentially
overstating the basis of the relationship used as the point's title.
"""
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(
        f"matches_audited={len(AUDIT_MATCHES)} full_distribution={counts} "
        f"audit_distribution={audited_counts} report={path}"
    )


if __name__ == "__main__":
    main()
