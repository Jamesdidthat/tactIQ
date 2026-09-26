# Deterministic event Team Profile opponent comparison

The pre-match layer compares two already-built event team-season profiles. One
match remains the historical unit of evidence; event rows are never pooled
between teams or seasons. The signed difference is always `opponent - target`.

## Evidence and compatibility gates

- each metric requires at least 10 contributing matches and 80% coverage for
  both teams;
- provider contexts must match unless a caller explicitly registers the pair as
  comparable;
- metric unit, definition, and coordinate system must agree exactly;
- StatsBomb possession remains an event-timeline estimate;
- continuous tracking is neither required nor implied.

For each accepted metric, the output preserves both medians, Q25/Q75, sample
counts, coverage, absolute/relative difference, robust standardized differences
using each team's own season variability, and a combined standardized value.
Robust scale is `IQR / 1.349`, with scaled MAD as a fallback.

`distributions_materially_overlap` is true when the intersection of the two
interquartile intervals covers at least 25% of the narrower IQR. Degenerate IQRs
are handled as point intervals. This is a transparent descriptive rule, not a
hypothesis test.

## Finding selection

A comparison finding requires an absolute combined robust standardized
difference of at least 1.0 and no material IQR overlap. At most the highest
ranked contrast in each football family is retained. Titles remain descriptive;
findings do not predict the head-to-head match, explain causes, or recommend a
tactical response.

The UI route is `/opponent-comparison`. It accepts target and opponent provider,
team, competition, and season identifiers, and exposes all excluded metric
reasons alongside the comparison.

## Directional matchup interactions

The interaction layer compares one team's attacking production distribution
with the other team's corresponding defensive-exposure distribution. It always
calculates and retains both directions independently: `Team A attack vs Team B
defence` is not interchangeable with `Team B attack vs Team A defence`.

The first analysis families are penalty-area pass entries, shots, xG, xG per
shot, high-regain activity alongside turnover-to-shot exposure, explicit
counter-attack shots, and set-play shots. Exact production/concession mirrors
share the same event definition. The high-regain/turnover row is retained only
as unsupported side-by-side context: its two counts describe different event
concepts and are not treated as a mismatch.

Comparable interactions preserve both medians, Q25/Q75, contributing-match
counts, coverage, robust season scales, signed mismatch (`attacking production
- defensive exposure`), IQR overlap, and a deterministic interaction-strength
index. Unsupported cross-metric rows preserve the two source distributions but
have no mismatch, overlap verdict, strength score, or qualified finding. The
strength index is not a probability, prediction, or estimate of tactical
importance.

A directional finding is emitted only when each side passes the existing
10-match and 80% coverage gates, the absolute mismatch is at least one combined
robust season scale, and the IQRs do not materially overlap. Findings remain
descriptive and contain explicit limitations against causal, weakness,
game-plan, or outcome interpretation.

The API adds two resources beneath the existing opponent-comparison identity
path:

- `interactions`: all supported directional comparisons and exclusions;
- `interaction-findings`: the deterministic findings ranked independently
  within each direction.

## Pre-match review priorities

The `review-priorities` resource synthesizes only already-qualified opponent
comparison findings and directional interaction findings. Recurring event
profile tendencies can support a candidate, but are interpreted strictly as a
count of adequately covered season-relative unusual matches—not as a causal or
stable tactical tendency.

Before ranking, every evidence source receives one compatibility category:
`same_metric`, `direct_attack_vs_defence_counterpart`,
`validated_relationship`, or `unsupported_cross_metric`. Only the first three
can become primary evidence. A validated relationship also requires an explicit
validation reference. Unsupported evidence is recorded in the candidate audit
but receives no score and cannot create, support, merge into, or upgrade a
priority.

Each candidate also has a source role: `directional_matchup_interaction`,
`general_team_comparison`, or `supporting_tendency`. A qualified directional
interaction is primary whenever it covers the same football topic as a general
comparison. The comparison is retained as supporting evidence and cannot
displace that interaction because of a higher raw priority score. General
comparisons remain primary only for topics without qualified directional
evidence; tendencies never create priorities. Both matchup directions remain
independent.

For eligible evidence, ranking continues to combine evidence adequacy, robust
mismatch magnitude, IQR separation, recurrence support, and the source
finding's deterministic strength. The ranking weights, minimum score, family
cap, and shortlist cap are unchanged.

Candidates are deduplicated by directional provenance and semantic football
topic, capped at two per football family, and then capped at five overall. A
minimum score gate is applied before selection, so the result may contain fewer
than three items. Suppressed and excluded candidates remain visible in the API
candidate audit.

Admission is intentionally stricter as the shortlist grows: slots one through
three require 0.58, slot four requires 0.66, and slot five requires 0.72. These
thresholds are configuration exposed in the result and each audit row records
the threshold it faced. Related attacking-output and territorial-access items
may be retained as semantic support when their direction of deviation and review
story overlap. Distinct validated directional interactions are not automatically
collapsed.

Every selected item is phrased as a review question. The layer does not propose
a game plan, identify a weakness, make a causal claim, or predict an outcome.
The UI shows the shortlist above all raw comparison and interaction tables.
Titles name the measured concept (for example, `Interceptions per 90`, `Shots`,
`xG`, or `Penalty-area entries`) instead of using a broad family label unless a
priority genuinely combines validated concepts.

## Local validation pair

Barcelona and Real Madrid 2015/16 are both precomputed from 38 La Liga matches.
All 19 configured opponent metrics are comparable. The interaction table has
14 directional rows: 12 directly comparable rows and two unsupported
high-regain/turnover context rows. The interaction layer produces seven
directional findings for this validation pair.
The direct local page is:

`http://localhost:5173/opponent-comparison?target_provider=statsbomb_open_data&target_team_id=217&target_competition_id=11&target_season_id=27&opponent_provider=statsbomb_open_data&opponent_team_id=220&opponent_competition_id=11&opponent_season_id=27`

The frozen-layer ten-pair product audit and its recurring failure modes are
documented in `docs/pre_match_review_priority_multi_matchup_qa.md`; its exact
machine-readable evidence is `artifacts/pre_match_review_priority_qa_v1.json`.
Post-refactor 190-pair validation is documented in
`docs/pre_match_review_compatibility_validation.md` with evidence in
`artifacts/pre_match_review_priority_qa_compatibility_v2.json`.
