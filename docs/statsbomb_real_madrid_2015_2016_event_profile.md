# Real Madrid event tactical profile — La Liga 2015/2016

**Provider:** StatsBomb Open Data  
**Coordinate provenance:** `statsbomb_120x80` (not metres)  
**Matches discovered:** 38  
**Matches included:** 38  
**Matches excluded:** 0

Every observation is first calculated within one match. The table then reports
the median and quartiles across matches; individual events are never pooled as
historical evidence. Raw counts and `_per90` fields are separate in the JSON artifact.

## Match-weighted headline metrics

| metric | unit | median_across_matches | q25_across_matches | q75_across_matches | contributing_matches | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| possession_share_estimate | proportion | 0.579 | 0.521 | 0.631 | 38 | 1.000 |
| passes_attempted | count | 604.500 | 549.750 | 692.750 | 38 | 1.000 |
| pass_completion_rate | proportion | 0.848 | 0.826 | 0.860 | 38 | 1.000 |
| progressive_passes | count | 38.000 | 34.000 | 48.500 | 38 | 1.000 |
| passes_into_final_third | count | 40.500 | 33.000 | 50.500 | 38 | 1.000 |
| passes_into_penalty_area | count | 14.000 | 12.250 | 16.000 | 38 | 1.000 |
| carries | count | 488.500 | 428.500 | 565.750 | 38 | 1.000 |
| progressive_carries | count | 22.500 | 18.250 | 27.750 | 38 | 1.000 |
| shots | count | 18.000 | 15.000 | 21.000 | 38 | 1.000 |
| shots_on_target | count | 7.500 | 6.000 | 9.750 | 38 | 1.000 |
| goals | count | 2.500 | 1.250 | 4.000 | 38 | 1.000 |
| xg | xG | 1.974 | 1.462 | 2.507 | 38 | 1.000 |
| average_shot_distance | native_120x80_units | 18.504 | 16.958 | 19.245 | 38 | 1.000 |
| open_play_shots | count | 11.500 | 10.000 | 14.750 | 38 | 1.000 |
| set_play_shots | count | 6.000 | 5.000 | 8.750 | 38 | 1.000 |
| pressures | count | 137.500 | 112.250 | 150.500 | 38 | 1.000 |
| tackles | count | 18.000 | 14.250 | 22.750 | 38 | 1.000 |
| interceptions | count | 17.500 | 12.250 | 21.000 | 38 | 1.000 |
| recoveries | count | 44.500 | 39.500 | 51.000 | 38 | 1.000 |
| high_regains | count | 11.500 | 8.250 | 16.750 | 38 | 1.000 |
| turnovers_leading_to_shot | count | 1.000 | 0.000 | 1.000 | 38 | 1.000 |
| counter_attack_shots | count | 1.000 | 0.000 | 1.000 | 38 | 1.000 |

## Match-weighted per-90 metrics

| metric | unit | median_across_matches | q25_across_matches | q75_across_matches | contributing_matches | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| passes_attempted_per90 | per_90 | 585.963 | 530.232 | 664.669 | 38 | 1.000 |
| progressive_passes_per90 | per_90 | 36.905 | 32.878 | 46.421 | 38 | 1.000 |
| passes_into_final_third_per90 | per_90 | 39.063 | 31.323 | 48.511 | 38 | 1.000 |
| passes_into_penalty_area_per90 | per_90 | 13.751 | 11.773 | 15.605 | 38 | 1.000 |
| carries_per90 | per_90 | 469.724 | 410.710 | 550.097 | 38 | 1.000 |
| progressive_carries_per90 | per_90 | 21.880 | 17.748 | 26.332 | 38 | 1.000 |
| shots_per90 | per_90 | 17.559 | 14.755 | 20.300 | 38 | 1.000 |
| shots_on_target_per90 | per_90 | 7.270 | 5.795 | 9.399 | 38 | 1.000 |
| goals_per90 | per_90 | 2.393 | 1.208 | 3.912 | 38 | 1.000 |
| open_play_shots_per90 | per_90 | 11.125 | 9.486 | 14.131 | 38 | 1.000 |
| set_play_shots_per90 | per_90 | 5.863 | 4.792 | 8.395 | 38 | 1.000 |
| pressures_per90 | per_90 | 132.626 | 107.594 | 149.537 | 38 | 1.000 |
| tackles_per90 | per_90 | 17.585 | 13.764 | 21.816 | 38 | 1.000 |
| interceptions_per90 | per_90 | 16.985 | 12.098 | 20.536 | 38 | 1.000 |
| recoveries_per90 | per_90 | 43.238 | 39.022 | 48.880 | 38 | 1.000 |
| high_regains_per90 | per_90 | 11.121 | 8.076 | 16.019 | 38 | 1.000 |
| turnovers_leading_to_shot_per90 | per_90 | 0.967 | 0.000 | 0.994 | 38 | 1.000 |
| counter_attack_shots_per90 | per_90 | 0.956 | 0.000 | 0.976 | 38 | 1.000 |
| xg_per90 | xG_per_90 | 1.896 | 1.408 | 2.421 | 38 | 1.000 |

## Definitions and limitations

| metric | unit | definition |
| --- | --- | --- |
| possession_share_estimate | proportion | Share of capped event-to-next-event time (0-30s) assigned to the team's StatsBomb possession_team; an event-timeline estimate, not optical possession. |
| passes_attempted | count | All team events with event_type=Pass, including restarts. |
| pass_completion_rate | proportion | passes_completed / passes_attempted. |
| progressive_passes | count | Completed passes moving at least 10 native x units toward x=120 and reducing Euclidean distance to goal centre (120,40) by at least 25%. |
| passes_into_final_third | count | Completed passes starting before x=80 and ending at x>=80. |
| passes_into_penalty_area | count | Completed passes starting outside and ending inside x>=102 and 18<=y<=62. |
| carries | count | All team events with event_type=Carry. |
| progressive_carries | count | Carries moving at least 10 native x units toward x=120 and reducing distance to goal centre by at least 25%. |
| shots | count | All team events with event_type=Shot. |
| shots_on_target | count | Shots with outcome Goal, Saved, or Saved to Post. |
| goals | count | Shots with shot_outcome=Goal; own-goal event types are not reattributed. |
| xg | xG | Sum of StatsBomb shot.statsbomb_xg where supplied. |
| average_shot_distance | native_120x80_units | Mean Euclidean distance from shot origin to goal centre (120,40). |
| open_play_shots | count | Shots not tagged From Corner/From Free Kick and not typed Free Kick/Penalty; From Counter and possessions originating at ordinary restarts remain open-play proxies. |
| set_play_shots | count | Shots explicitly tagged From Corner/From Free Kick or typed Free Kick/Penalty. |
| pressures | count | All team Pressure events. |
| tackles | count | Team Duel events whose canonical duel_type is Tackle. |
| interceptions | count | All team Interception events. |
| recoveries | count | Team Ball Recovery events not marked recovery_failure. |
| high_regains | count | Successful Ball Recovery or non-lost Interception at x>=80 in StatsBomb's team-oriented coordinates. |
| turnovers_leading_to_shot | count | Team possessions followed by an opponent possession containing a shot within 15 elapsed seconds and its first 10 events. |
| counter_attack_shots | count | Shots whose explicit StatsBomb play_pattern is From Counter; a source-supported fast-attack proxy. |

Possession share is explicitly an event-timeline estimate. Transition reporting
is restricted to StatsBomb's explicit `From Counter` play pattern. No tactical
recommendations or generated interpretations are included.
