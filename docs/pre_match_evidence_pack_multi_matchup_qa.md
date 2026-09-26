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
| 2 | Celta Vigo vs Eibar | 1 | General | Eibar vs Celta Vigo: Pass completion rate | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |
| 3 | Real Sociedad vs Real Madrid | 3 | Directional | Real Madrid attack vs Real Sociedad defence: Shots | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 4 | Getafe vs Real Madrid | 3 | General | Real Madrid vs Getafe: Pass completion rate | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |
| 5 | Atlético Madrid vs Barcelona | 5 | Directional | Barcelona attack vs Atlético Madrid defence: xG | 8 / 8 | 4 | No | 5 | 5 | 5 | 5 |
| 6 | Barcelona vs Levante UD | 5 | General | Levante UD vs Barcelona: Pass completion rate | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |
| 7 | Real Sociedad vs Barcelona | 4 | General | Barcelona vs Real Sociedad: Interceptions per 90 | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 8 | Atlético Madrid vs Sevilla | 4 | Directional | Sevilla attack vs Atlético Madrid defence: xG per shot | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |
| 9 | Real Betis vs Eibar | 2 | General | Eibar vs Real Betis: Progressive passes per 90 | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |
| 10 | Espanyol vs Sporting Gijón | 1 | Directional | Sporting Gijón attack vs Espanyol defence: Set-play shots | 8 / 8 | 2 | No | 5 | 5 | 5 | 5 |
| 11 | Valencia vs Atlético Madrid | 3 | General | Atlético Madrid vs Valencia: Turnovers followed by an opposition shot per 90 | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |
| 12 | Athletic Club vs Real Betis | 2 | General | Real Betis vs Athletic Club: Final-third entries by pass per 90 | 8 / 8 | 6 | No | 5 | 5 | 5 | 5 |
| 13 | Las Palmas vs Atlético Madrid | 2 | General | Atlético Madrid vs Las Palmas: High regains per 90 | 8 / 7 | 3 | No | 5 | 5 | 5 | 5 |
| 14 | Sevilla vs Villarreal | 3 | Directional | Sevilla attack vs Villarreal defence: xG per shot | 8 / 8 | 3 | No | 5 | 5 | 5 | 5 |
| 15 | Celta Vigo vs Real Betis | 3 | General | Real Betis vs Celta Vigo: Progressive passes per 90 | 0 / 0 | 0 | No | 3 | 4 | 4 | 2 |

## Requirement coverage

- `directional_priorities`: 6
- `general_comparison_priorities`: 9
- `several_sequence_groups`: 7
- `one_dominant_sequence_group`: 3
- `sparse_representative_evidence`: 6
- `without_360`: 15
- `with_360`: 0
- `shortlist_sizes_represented`: [1, 2, 3, 4, 5]

## Contract and meaning checks

- `review_question_matches_primary_evidence`: 15/15
- `why_selected_understandable_without_technical_knowledge`: 15/15
- `season_baselines_and_distributions_support_claim`: 15/15
- `sequence_patterns_add_non_repeating_information`: 9/15
- `representative_moments_illustrate_measured_concept`: 9/15
- `representative_moments_sufficiently_diverse`: 15/15
- `pitch_details_understandable`: 9/15
- `provenance_and_limitations_visible_not_overwhelming`: 0/15
- `retrieved_sample_not_presented_as_season_frequency`: 15/15
- `optional_360_scope_and_coverage_are_safe`: 15/15
- `unsupported_evidence_absent_from_main_narrative`: 15/15

## Recurring failure modes

- **15/15:** provenance/limitations are incomplete or too dense.
- **15/15:** video is unavailable; review utility is limited to event/pitch evidence.
- **6/15:** no supported representative-event query exists for the primary measured concept.
- **6/15:** moment-detail coverage or coordinate provenance is incomplete.

## Fail-closed construction findings

- **Sevilla vs Málaga — `pre-match-review:213:223:target_attack_vs_opponent_defence:penalty_area_access`:** ValueError: Representative moment IDs must be unique within an evidence pack.

These were not counted as audited packs. The QA continued with deterministic replacement cases; the product validation was not weakened.

## Product assessment

The packs are strongest as traceable evidence indexes: the primary source ID, exact season distributions, direction, event IDs, native 120×80 pitch coordinates, and limitations remain connected. Retrieved sequence groups are explicitly labelled as an eight-moment sample and are not presented as season frequencies.

The largest practical limitation is review access rather than analytical grounding: the open-data events expose no linked video, so `Review moments` identifies what and where to inspect but cannot open match footage. The configured QA season also has no aligned 360, making all spatial evidence event-only. This is correctly shown, but it prevents a genuine 360 product-validation case in this frozen population.

`why_selected` remains less coach-facing when the selection reason is `priority_fill`; its text describes admission and redundancy rules. That is accurate provenance, but not independently useful football context.

## Usefulness score means

- `clear`: 4.2/5
- `evidence_backed`: 4.6/5
- `non_redundant`: 4.6/5
- `actionable_for_review`: 3.8/5

## Conclusion

Evidence packs preserve source identity, directional provenance, and retrieved-sample/360 scope. Their immediate analyst review value remains constrained where video or 360 is unavailable and where why-selected copy exposes shortlist-engine terminology.

No selection or product logic was changed during this audit.
