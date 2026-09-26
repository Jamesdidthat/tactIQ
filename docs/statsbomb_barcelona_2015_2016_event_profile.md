# Barcelona event tactical profile — La Liga 2015/2016

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
| possession_share_estimate | proportion | 0.652 | 0.608 | 0.693 | 38 | 1.000 |
| passes_attempted | count | 694.000 | 613.750 | 733.750 | 38 | 1.000 |
| pass_completion_rate | proportion | 0.861 | 0.844 | 0.873 | 38 | 1.000 |
| progressive_passes | count | 40.500 | 36.250 | 47.500 | 38 | 1.000 |
| passes_into_final_third | count | 51.500 | 37.250 | 60.000 | 38 | 1.000 |
| passes_into_penalty_area | count | 15.000 | 14.000 | 19.000 | 38 | 1.000 |
| carries | count | 574.500 | 503.750 | 635.750 | 38 | 1.000 |
| progressive_carries | count | 24.000 | 19.250 | 30.000 | 38 | 1.000 |
| shots | count | 15.000 | 12.250 | 18.750 | 38 | 1.000 |
| shots_on_target | count | 7.000 | 5.250 | 8.000 | 38 | 1.000 |
| goals | count | 2.000 | 1.250 | 4.000 | 38 | 1.000 |
| xg | xG | 2.298 | 1.751 | 2.930 | 38 | 1.000 |
| average_shot_distance | native_120x80_units | 16.769 | 15.937 | 18.677 | 38 | 1.000 |
| open_play_shots | count | 9.000 | 7.000 | 11.750 | 38 | 1.000 |
| set_play_shots | count | 6.000 | 5.000 | 8.000 | 38 | 1.000 |
| pressures | count | 125.000 | 94.000 | 138.750 | 38 | 1.000 |
| tackles | count | 17.000 | 13.000 | 19.750 | 38 | 1.000 |
| interceptions | count | 6.500 | 5.000 | 10.750 | 38 | 1.000 |
| recoveries | count | 46.000 | 42.000 | 52.000 | 38 | 1.000 |
| high_regains | count | 12.500 | 10.000 | 15.000 | 38 | 1.000 |
| turnovers_leading_to_shot | count | 1.000 | 0.000 | 2.000 | 38 | 1.000 |
| counter_attack_shots | count | 0.500 | 0.000 | 1.000 | 38 | 1.000 |

## Match-weighted per-90 metrics

| metric | unit | median_across_matches | q25_across_matches | q75_across_matches | contributing_matches | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| passes_attempted_per90 | per_90 | 674.944 | 594.416 | 704.032 | 38 | 1.000 |
| progressive_passes_per90 | per_90 | 38.906 | 35.298 | 46.299 | 38 | 1.000 |
| passes_into_final_third_per90 | per_90 | 50.086 | 36.301 | 58.510 | 38 | 1.000 |
| passes_into_penalty_area_per90 | per_90 | 14.833 | 13.524 | 18.584 | 38 | 1.000 |
| carries_per90 | per_90 | 560.662 | 488.634 | 621.336 | 38 | 1.000 |
| progressive_carries_per90 | per_90 | 23.300 | 18.824 | 29.730 | 38 | 1.000 |
| shots_per90 | per_90 | 14.665 | 11.849 | 18.037 | 38 | 1.000 |
| shots_on_target_per90 | per_90 | 6.843 | 5.049 | 7.828 | 38 | 1.000 |
| goals_per90 | per_90 | 1.955 | 1.208 | 3.911 | 38 | 1.000 |
| open_play_shots_per90 | per_90 | 8.700 | 6.770 | 11.539 | 38 | 1.000 |
| set_play_shots_per90 | per_90 | 5.867 | 4.834 | 7.824 | 38 | 1.000 |
| pressures_per90 | per_90 | 121.587 | 90.494 | 135.734 | 38 | 1.000 |
| tackles_per90 | per_90 | 16.534 | 12.571 | 19.114 | 38 | 1.000 |
| interceptions_per90 | per_90 | 6.374 | 4.890 | 10.426 | 38 | 1.000 |
| recoveries_per90 | per_90 | 44.496 | 41.078 | 50.057 | 38 | 1.000 |
| high_regains_per90 | per_90 | 12.020 | 9.683 | 14.677 | 38 | 1.000 |
| turnovers_leading_to_shot_per90 | per_90 | 0.967 | 0.000 | 1.941 | 38 | 1.000 |
| counter_attack_shots_per90 | per_90 | 0.474 | 0.000 | 0.978 | 38 | 1.000 |
| xg_per90 | xG_per_90 | 2.247 | 1.686 | 2.861 | 38 | 1.000 |

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
