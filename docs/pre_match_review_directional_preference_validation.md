# Pre-Match Review Directional-Preference Validation

## Frozen configuration

- Priority gate: `0.58`
- Maximum per football family: `2`
- Maximum shortlist size: `5`
- Source qualification thresholds and interaction compatibility rules: unchanged

## Selection contract

Primary evidence is assigned one explicit role:

- `directional_matchup_interaction`: compatible attack-versus-defence evidence for this matchup.
- `general_team_comparison`: same-metric season-to-season evidence.
- `supporting_tendency`: recurring season context that cannot create a priority.

When a qualified directional interaction and a general comparison cover the same
football topic, the directional interaction is the primary candidate. The general
comparison is retained in its supporting evidence. If no qualified directional
interaction covers the topic, a general comparison may remain primary. The two
attack-versus-defence directions continue to be treated independently.

Titles now name the measured concept, for example `Interceptions per 90`,
`Penalty-area entries`, `Shots`, or `xG`, instead of relying on a broad family label.

## Complete 190-pair screen

The screen used all 20 StatsBomb La Liga 2015/16 team profiles, producing 190
unordered team-season pairings.

| Result | Count |
|---|---:|
| Final priorities | 301 |
| Directional matchup-interaction primaries | 67 |
| General team-comparison primaries | 234 |
| General comparisons demoted to directional support | 47 |
| Pairings with no final priority | 71 |
| Pairings with 1–4 priorities | 86 |
| Pairings with 5 priorities | 33 |

Final-priority count distribution: 0: 71, 1: 50, 2: 26, 3: 6, 4: 4,
5: 33.

## Previous 10-pair QA rerun

| Matchup | Final priorities | Directional | General | Demoted to support |
|---|---:|---:|---:|---:|
| Barcelona vs Real Madrid | 5 | 4 | 1 | 0 |
| Barcelona vs Sporting Gijon | 5 | 1 | 4 | 2 |
| Real Madrid vs Eibar | 5 | 2 | 3 | 2 |
| Real Madrid vs Villarreal | 5 | 1 | 4 | 1 |
| Atletico Madrid vs Las Palmas | 2 | 0 | 2 | 0 |
| Barcelona vs Valencia | 5 | 1 | 4 | 2 |
| Levante UD vs Malaga | 0 | 0 | 0 | 0 |
| Malaga vs Real Sociedad | 0 | 0 | 0 | 0 |
| Valencia vs Celta Vigo | 0 | 0 | 0 | 0 |
| Valencia vs Real Sociedad | 0 | 0 | 0 | 0 |

Across these 10 matchups, directional primaries increased from 6 to 9 and general
comparison primaries fell from 21 to 18. Seven general comparisons were demoted to
support. No previously selected directional interaction disappeared.

The demotions covered:

- Barcelona vs Sporting Gijon: penalty-area entries and xG comparisons.
- Real Madrid vs Eibar: shots and penalty-area entries comparisons.
- Real Madrid vs Villarreal: shots comparison, supporting the qualified xG interaction in the shared chance-creation topic.
- Barcelona vs Valencia: penalty-area entries and xG comparisons.

The four cautious zero-priority cases introduced by the compatibility correction
remain empty. No unsupported high-regain/turnover cross-metric evidence re-entered
the shortlist.

## Product assessment

The selector now answers the matchup-specific question first whenever compatible
directional evidence exists. Generic season contrasts remain available as context
without competing against that primary interaction. Broad families still organize
redundancy and caps, but the user-facing titles identify the exact measurement.

The machine-readable audit is stored at
`artifacts/pre_match_review_priority_qa_source_roles_v3.json`.
