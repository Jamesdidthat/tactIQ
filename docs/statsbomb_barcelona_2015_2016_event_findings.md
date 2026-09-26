# Event Profile Finding audit

**Team:** Barcelona  
**Matches:** 38  
**Findings emitted:** 108  
**Correlated duplicates suppressed:** 0  
**Threshold:** absolute robust z >= 1.5, N >= 10, coverage >= 80%  
**Archetype rule:** every component must reach signed robust z >= 0.75, N >= 10, and coverage >= 80%; labels may overlap.

## Rule-based match archetypes

| archetype | title | description | match_count | match_share | representative_match_ids | representative_rule_strengths |
| --- | --- | --- | --- | --- | --- | --- |
| high_progression_high_chance_creation | High progression and chance creation | The match combined above-baseline progressive-pass volume with above-baseline xG. | 4 | 0.105 | (266254, 266653, 266620) | (1.7021889598195814, 1.462183091687294, 1.0233653347687923) |
| high_regain_transition_pressure | High-regain and pressure activity | The match combined above-baseline high-regain frequency with above-baseline pressure volume. | 2 | 0.053 | (266254, 266620) | (2.0294211721134396, 0.9797023094901128) |
| high_shot_volume_low_xg_per_shot | High shot volume, lower xG per shot | The match combined above-baseline shot volume with below-baseline average xG per shot. | 2 | 0.053 | (267422, 266961) | (0.9115528330313568, 0.7653549266823649) |
| high_possession_low_progression | High possession, lower progression | The match combined above-baseline event-derived possession share with below-baseline progressive-pass volume. | 1 | 0.026 | (267274,) | (1.0438293799076508,) |
| low_possession_direct_attack | Lower possession with explicit counter attacks | The match combined below-baseline event-derived possession share with above-baseline shots explicitly tagged From Counter. | 1 | 0.026 | (266653,) | (0.8608305515990861,) |
| high_penalty_area_access_low_shot_output | High penalty-area access, lower shot output | The match combined above-baseline completed passes into the penalty area with below-baseline shot volume. | 0 | 0.000 | () | () |

## Recurring families

| finding_family | unusual_matches | finding_count | above_baseline | below_baseline | strongest_robust_z |
| --- | --- | --- | --- | --- | --- |
| defensive_activity | 20 | 22 | 14 | 8 | 6.294 |
| chance_creation | 19 | 31 | 22 | 9 | 3.463 |
| possession_circulation | 13 | 18 | 6 | 12 | -3.471 |
| penalty_area_access | 10 | 10 | 8 | 2 | 3.696 |
| progression | 9 | 9 | 8 | 1 | 2.304 |
| high_regains | 8 | 8 | 6 | 2 | -2.455 |
| explicit_fast_attacks | 7 | 7 | 7 | 0 | 2.095 |
| turnover_to_shot_exposure | 3 | 3 | 3 | 0 | 2.719 |

## Metric relationships

| upstream_metric | downstream_metric | slope | intercept | spearman_rank_correlation | slope_leave_one_out_low | slope_leave_one_out_high | residual_robust_scale | contributing_match_count | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| possession_share_estimate | progressive_passes_per90 | 17.359 | 27.763 | 0.129 | 15.821 | 25.164 | 8.310 | 38 | 1.000 |
| progressive_passes_per90 | passes_into_final_third_per90 | 0.249 | 40.509 | 0.146 | 0.160 | 0.360 | 18.319 | 38 | 1.000 |
| passes_into_final_third_per90 | passes_into_penalty_area_per90 | 0.113 | 10.231 | 0.332 | 0.089 | 0.133 | 5.190 | 38 | 1.000 |
| passes_into_penalty_area_per90 | shots_per90 | 0.438 | 7.739 | 0.553 | 0.409 | 0.501 | 3.973 | 38 | 1.000 |
| shots_per90 | xg_per90 | 0.135 | 0.090 | 0.485 | 0.120 | 0.152 | 0.910 | 38 | 1.000 |
| high_regains_per90 | counter_attack_shots_per90 | 0.000 | 0.474 | -0.142 | 0.000 | 0.000 | 0.725 | 38 | 1.000 |

## Match Story example — 266961

| story_type | title | metrics | evidence_level | priority_score | selection_reason |
| --- | --- | --- | --- | --- | --- |
| metric_relationship_residual | Barcelona recorded more penalty-area pass entries than expected | passes_into_final_third_per90, passes_into_penalty_area_per90 | strong | 1.000 | coherent_narrative |
| match_archetype | High shot volume, lower xG per shot | shots_per90, xg_per_shot | exploratory | 0.612 | coherent_narrative |
| single_metric_deviation | Barcelona's shots came from farther out | average_shot_distance | strong | 0.956 | coherent_narrative |

## Unusual relationship residuals

| match_id | title | upstream_value | observed_downstream_value | expected_downstream_value | residual | residual_robust_z | evidence_level |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3825627 | Barcelona recorded higher xG than expected for its shot volume | 13.663 | 4.564 | 1.935 | 2.629 | 2.889 | strong |
| 266620 | Barcelona recorded more progressive passes than expected | 0.630 | 57.696 | 38.691 | 19.005 | 2.287 | moderate |
| 266961 | Barcelona recorded more penalty-area pass entries than expected | 59.309 | 28.698 | 16.952 | 11.746 | 2.263 | moderate |
| 3825617 | Barcelona recorded more penalty-area pass entries than expected | 39.269 | 25.860 | 14.681 | 11.179 | 2.154 | moderate |
| 266653 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 19.934 | 1.993 | 0.474 | 1.519 | 2.095 | moderate |
| 266498 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 10.759 | 1.956 | 0.474 | 1.482 | 2.044 | moderate |
| 3825660 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 13.693 | 1.956 | 0.474 | 1.482 | 2.044 | moderate |
| 266056 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 6.839 | 1.954 | 0.474 | 1.480 | 2.041 | moderate |
| 266490 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 17.561 | 1.951 | 0.474 | 1.477 | 2.037 | moderate |
| 267506 | Barcelona recorded more explicitly tagged counter-attack shots than expected | 9.657 | 1.931 | 0.474 | 1.457 | 2.010 | moderate |

## Strongest deviations

| source_match_id | finding_family | title | observed_value | season_baseline | signed_deviation | relative_deviation | robust_z_score | evidence_level | contributing_match_count | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3825627 | defensive_activity | Barcelona made more interceptions | 32.207 | 6.374 | 25.833 | 4.053 | 6.294 | strong | 38 | 1.000 |
| 3825637 | defensive_activity | Barcelona made more interceptions | 26.554 | 6.374 | 20.180 | 3.166 | 4.917 | strong | 38 | 1.000 |
| 266310 | defensive_activity | Barcelona made fewer recoveries | 15.988 | 44.496 | -28.508 | -0.641 | -4.283 | strong | 38 | 1.000 |
| 3825660 | defensive_activity | Barcelona made more interceptions | 22.496 | 6.374 | 16.122 | 2.529 | 3.928 | strong | 38 | 1.000 |
| 266961 | penalty_area_access | Barcelona accessed the penalty area by pass more often | 28.698 | 14.833 | 13.865 | 0.935 | 3.696 | strong | 38 | 1.000 |
| 3825627 | possession_circulation | Barcelona had less of the event-derived possession timeline | 0.434 | 0.652 | -0.219 | -0.335 | -3.471 | strong | 38 | 1.000 |
| 267422 | chance_creation | Barcelona produced more set-play shots | 13.541 | 5.867 | 7.674 | 1.308 | 3.463 | strong | 38 | 1.000 |
| 266557 | chance_creation | Barcelona produced more set-play shots | 12.717 | 5.867 | 6.850 | 1.167 | 3.091 | strong | 38 | 1.000 |
| 266557 | penalty_area_access | Barcelona accessed the penalty area by pass more often | 26.413 | 14.833 | 11.580 | 0.781 | 3.087 | strong | 38 | 1.000 |
| 266467 | possession_circulation | Barcelona's pass completion was below its season baseline | 0.797 | 0.861 | -0.064 | -0.075 | -3.010 | strong | 38 | 1.000 |
| 266310 | possession_circulation | Barcelona's pass completion was above its season baseline | 0.925 | 0.861 | 0.064 | 0.074 | 2.976 | strong | 38 | 1.000 |
| 3825617 | chance_creation | Barcelona produced more set-play shots | 12.451 | 5.867 | 6.584 | 1.122 | 2.971 | strong | 38 | 1.000 |
| 3825617 | penalty_area_access | Barcelona accessed the penalty area by pass more often | 25.860 | 14.833 | 11.027 | 0.743 | 2.940 | strong | 38 | 1.000 |
| 266160 | chance_creation | Barcelona's shots came from farther out | 22.681 | 16.769 | 5.912 | 0.353 | 2.911 | strong | 38 | 1.000 |
| 266620 | penalty_area_access | Barcelona accessed the penalty area by pass more often | 25.426 | 14.833 | 10.593 | 0.714 | 2.824 | strong | 38 | 1.000 |
| 267422 | chance_creation | Barcelona recorded more shots on target | 12.574 | 6.843 | 5.731 | 0.838 | 2.782 | strong | 38 | 1.000 |
| 3825627 | possession_circulation | Barcelona circulated at a lower volume | 450.895 | 674.944 | -224.049 | -0.332 | -2.757 | strong | 38 | 1.000 |
| 266254 | defensive_activity | Barcelona made more interceptions | 17.596 | 6.374 | 11.222 | 1.761 | 2.734 | strong | 38 | 1.000 |
| 265944 | chance_creation | Barcelona's xG was above its season baseline | 4.620 | 2.247 | 2.374 | 1.057 | 2.725 | strong | 38 | 1.000 |
| 3825627 | turnover_to_shot_exposure | Barcelona had more turnovers followed by an opposition shot | 4.880 | 0.967 | 3.913 | 4.048 | 2.719 | strong | 38 | 1.000 |

Robust scale is `IQR / 1.349`, with scaled MAD only when IQR is zero. Titles are
descriptive and do not classify observations as positive or negative.
