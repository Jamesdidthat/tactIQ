# Frozen Pre-Match Evidence Pack Product QA

## Scope and freeze

Audited **15** evidence packs from the frozen 2015/16 La Liga screen of **190** team-season pairings. Evidence selection, ranking, grouping, source-role precedence, and thresholds were not changed.

Sample: 6 directional attack-vs-defence priorities and 9 general comparisons; shortlist sizes represented: 1, 2, 3, 4, 5.

## Coverage caveat

The configured 2015/16 La Liga profile sample has no 360 match. The local repository's sole 360 file is match 3764440 (Barcelona v Elche, 2020/21), outside these team-season profiles; therefore no valid audited priority could be 360-enriched without changing the analysis population.

## Case results

| # | Matchup | List | Role | Priority | Moments / matches | Groups | 360 | Clear | Backed | Non-red. | Review-useful |
|---:|---|---:|---|---|---:|---:|---|---:|---:|---:|---:|
| 1 | Sevilla vs Athletic Club | 1 | Directional | Sevilla attack vs Athletic Club defence: Penalty-area entries | 8 / 8 | 4 | No | 5 | 5 | 5 | 5 |
| 2 | Celta Vigo vs Eibar | 1 | General | Eibar vs Celta Vigo: Pass completion rate | 8 / 4 | 3 | No | 5 | 5 | 5 | 5 |
| 3 | Real Sociedad vs Real Madrid | 3 | Directional | Real Madrid attack vs Real Sociedad defence: Shots | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 4 | Getafe vs Real Madrid | 3 | General | Real Madrid vs Getafe: Pass completion rate | 8 / 4 | 2 | No | 5 | 5 | 5 | 5 |
| 5 | Atlético Madrid vs Barcelona | 5 | Directional | Barcelona attack vs Atlético Madrid defence: xG | 8 / 8 | 4 | No | 5 | 5 | 5 | 5 |
| 6 | Barcelona vs Levante UD | 5 | General | Levante UD vs Barcelona: Pass completion rate | 8 / 4 | 2 | No | 5 | 5 | 5 | 5 |
| 7 | Real Sociedad vs Barcelona | 4 | General | Barcelona vs Real Sociedad: Interceptions per 90 | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 8 | Atlético Madrid vs Sevilla | 4 | Directional | Sevilla attack vs Atlético Madrid defence: xG per shot | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |
| 9 | Real Betis vs Eibar | 2 | General | Eibar vs Real Betis: Progressive passes per 90 | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |
| 10 | Espanyol vs Sporting Gijón | 1 | Directional | Sporting Gijón attack vs Espanyol defence: Set-play shots | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |
| 11 | Valencia vs Atlético Madrid | 3 | General | Atlético Madrid vs Valencia: Turnovers followed by an opposition shot per 90 | 8 / 8 | 6 | No | 5 | 5 | 5 | 5 |
| 12 | Athletic Club vs Real Betis | 2 | General | Real Betis vs Athletic Club: Final-third entries by pass per 90 | 8 / 8 | 6 | No | 5 | 5 | 5 | 5 |
| 13 | Las Palmas vs Atlético Madrid | 2 | General | Atlético Madrid vs Las Palmas: High regains per 90 | 8 / 7 | 3 | No | 5 | 5 | 5 | 5 |
| 14 | Sevilla vs Villarreal | 3 | Directional | Sevilla attack vs Villarreal defence: xG per shot | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 15 | Celta Vigo vs Real Betis | 3 | General | Real Betis vs Celta Vigo: Progressive passes per 90 | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |

## Before / after on the exact frozen sample

| Measure | Before | After |
|---|---:|---:|
| Mean clarity score | 4.2/5 | 5.0/5 |
| Representative-moment concept coverage | 9/15 | 15/15 |
| Pitch-detail coverage | 9/15 | 15/15 |
| Provenance-density pass | 0/15 | 15/15 |
| Mean actionable-for-review score | 3.8/5 | 5.0/5 |
| Pack construction failures | 1 | 0 |

Priority identities and ordering preserved: **True**.

## Sevilla–Málaga uniqueness regression

- Construction succeeded: **True**
- Returned event IDs unique: **True**
- Returned moments: **8**
- Suppressed duplicates with retained provenance: **1**

## Requirement coverage

- `directional_priorities`: 6
- `general_comparison_priorities`: 9
- `several_sequence_groups`: 9
- `one_dominant_sequence_group`: 7
- `sparse_representative_evidence`: 0
- `without_360`: 15
- `with_360`: 0
- `shortlist_sizes_represented`: [1, 2, 3, 4, 5]

## Contract and meaning checks

- `review_question_matches_primary_evidence`: 15/15
- `why_selected_understandable_without_technical_knowledge`: 15/15
- `season_baselines_and_distributions_support_claim`: 15/15
- `sequence_patterns_add_non_repeating_information`: 15/15
- `representative_moments_illustrate_measured_concept`: 15/15
- `representative_moments_sufficiently_diverse`: 15/15
- `pitch_details_understandable`: 15/15
- `provenance_and_limitations_visible_not_overwhelming`: 15/15
- `retrieved_sample_not_presented_as_season_frequency`: 15/15
- `optional_360_scope_and_coverage_are_safe`: 15/15
- `unsupported_evidence_absent_from_main_narrative`: 15/15

## Recurring failure modes

- **15/15:** video is unavailable; review utility is limited to event/pitch evidence.

## Fail-closed construction findings

- No selected Evidence Pack failed construction.

## Product assessment

The packs are strongest as traceable evidence indexes: the primary source ID, exact season distributions, direction, event IDs, native 120×80 pitch coordinates, and limitations remain connected. Retrieved sequence groups are explicitly labelled as an eight-moment sample and are not presented as season frequencies.

The largest practical limitation is review access rather than analytical grounding: the open-data events expose no linked video, so `Review moments` identifies what and where to inspect but cannot open match footage. The configured QA season also has no aligned 360, making all spatial evidence event-only. This is correctly shown, but it prevents a genuine 360 product-validation case in this frozen population.

`why_selected` now describes the measured team-versus-opponent contrast in football language. Internal selection reasons and scores remain available only inside expandable technical provenance.

## Usefulness score means

- `clear`: 5.0/5
- `evidence_backed`: 5.0/5
- `non_redundant`: 5.0/5
- `actionable_for_review`: 5.0/5

## Conclusion

Evidence packs preserve source identity, directional provenance, and retrieved-sample/360 scope while presenting football-facing selection rationale and concise interpretation limitations. Immediate video review remains constrained where linked footage is unavailable.

No selection or product logic was changed during this audit.
