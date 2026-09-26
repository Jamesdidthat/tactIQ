# Pre-Match Review Diminishing-Threshold Validation

## Selector change

The selector now uses explicit, configurable admission thresholds:

| Shortlist slot | Minimum priority score |
|---|---:|
| 1 | 0.58 |
| 2 | 0.58 |
| 3 | 0.58 |
| 4 | 0.66 |
| 5 | 0.72 |

The base score formula, upstream finding qualification, source-role precedence,
compatibility rules, family cap of two, and shortlist maximum of five are
unchanged. Every candidate-audit row records the admission score required at the
point it was considered.

The semantic preparation groups are `attacking_output` (shot volume, xG/chance
creation, and xG per shot/shot quality) and `territorial_access` (final-third and
penalty-area access). Candidates are suppressed only when they have aligned
deviation direction and would express substantially the same preparation story.
Distinct qualified directional interactions are exempt from semantic collapse.

## Full 190-pair screen

| Shortlist length | Before | After |
|---:|---:|---:|
| 0 | 71 | 71 |
| 1 | 50 | 50 |
| 2 | 26 | 27 |
| 3 | 6 | 11 |
| 4 | 4 | 18 |
| 5 | 33 | 13 |

- Total priorities: 301 before, 274 after.
- Pairings legitimately retaining four or five priorities: 31 (18 with four,
  13 with five), down from 37.
- Previously selected fourth/fifth items removed: 26.
- Removed source items by reason: 7 higher-slot threshold, 27 semantic grouping.
- The remaining eight semantic removals occurred at earlier ranks; seven other
  qualified candidates filled vacancies, so the net shortlist reduction is 27.
- No previously selected directional interaction scoring at least 0.72 was lost.
- Final primary-source mix: 65 directional interactions and 209 general
  comparisons.

## Ten-pair QA rerun

| Matchup | Before | After |
|---|---:|---:|
| Barcelona vs Real Madrid | 5 | 5 |
| Barcelona vs Sporting Gijon | 5 | 4 |
| Real Madrid vs Eibar | 5 | 4 |
| Real Madrid vs Villarreal | 5 | 5 |
| Atletico Madrid vs Las Palmas | 2 | 2 |
| Barcelona vs Valencia | 5 | 5 |
| Levante UD vs Malaga | 0 | 0 |
| Malaga vs Real Sociedad | 0 | 0 |
| Valencia vs Celta Vigo | 0 | 0 |
| Valencia vs Real Sociedad | 0 | 0 |

The removed fifth items were Barcelona's penalty-area-entry interaction against
Sporting Gijon (0.693) and Real Madrid's penalty-area-entry interaction against
Eibar (0.669). Both cleared the base gate but not the 0.72 fifth-slot threshold.
The four cautious zero-priority cases remain unchanged.

## Semantic examples

Correctly suppressed examples include:

- Barcelona vs Valencia: general final-third entries supported the directional
  penalty-area-entry priority instead of creating a second territorial-access
  review item.
- Barcelona vs Valencia: general shots-on-target evidence supported the
  directional xG priority instead of repeating the same attacking-output story.
- Real Madrid vs Valencia: shots on target supported the selected shots
  comparison because both deviations pointed in the same direction.
- Barcelona vs Las Palmas: final-third entries supported penalty-area entries,
  and shots on target supported xG.

Correctly retained examples include validated directional xG plus xG-per-shot
interactions for Sevilla attack vs Atletico Madrid defence, Athletic Club attack
vs Atletico Madrid defence, and Barcelona attack vs Atletico Madrid defence.
These describe production and average chance quality separately and retain their
directional attack-versus-defence provenance.

The complete machine-readable audit is
`artifacts/pre_match_review_priority_qa_diminishing_v4.json`.
