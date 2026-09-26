# StatsBomb 360 coverage and product-readiness audit

Audit date: 2026-09-12

## Outcome

The local checkout contains **382 event-enabled matches** but only **1 match with an actual 360 snapshot file**. No team-season satisfies the conservative stable-pattern-context readiness definition.

The current product minimum remains **3 aligned 360 examples per pattern**. Thresholds of 5 and 10 are audit comparisons only.

## Repository coverage

| Metric | Count |
|---|---:|
| Indexed matches | 3961 |
| Matches with events | 382 |
| Matches with any 360 | 1 |
| Materialized event blobs | 382 |
| Materialized 360 blobs | 1 |
| Competition-seasons | 80 |
| Team-seasons | 922 |
| Stable 360 team-seasons | 0 |

The partial clone's Git tree advertises additional blobs, but they are not counted as usable because they are not locally readable without hydration.

## Coverage by supported moment family

| Family | Eligible events | Aligned 360 | Coverage | Pattern groups N>=3 | N>=5 | N>=10 |
|---|---:|---:|---:|---:|---:|---:|
| Penalty Area Entries | 11327 | 24 | 0.2% | 3 | 3 | 1 |
| Final Third Entries | 36085 | 94 | 0.3% | 4 | 4 | 4 |
| Shots | 9212 | 15 | 0.2% | 5 | 4 | 2 |
| Interceptions | 7578 | 27 | 0.4% | 1 | 1 | 1 |
| High Regains | 8662 | 9 | 0.1% | 2 | 2 | 0 |
| Counter Attacks | 403 | 2 | 0.5% | 0 | 0 | 0 |
| Set Play Shots | 3546 | 3 | 0.1% | 1 | 0 | 0 |

## Best-supported competition-seasons

| Rank | Competition-season | Event matches | 360 matches | Match coverage | Aligned moments | Alignment | Patterns N>=3 / 5 / 10 | Stable team-seasons |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | La Liga - 2020/2021 | 1 | 1 | 100.0% | 164 | 95.9% | 16 / 14 / 8 | 0 |
| 2 | La Liga - 2017/2018 | 1 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | 0 |
| 3 | La Liga - 2015/2016 | 380 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | 0 |

## Best-supported team-seasons

| Rank | Team-season | Event matches | 360 matches | Match coverage | Aligned moments | Alignment | Patterns N>=3 / 5 / 10 | Ready |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | Barcelona - La Liga 2020/2021 | 1 | 1 | 100.0% | 104 | 95.4% | 13 / 11 / 6 | No |
| 2 | Elche - La Liga 2020/2021 | 1 | 1 | 100.0% | 60 | 96.8% | 12 / 10 / 2 | No |
| 3 | Athletic Club - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 4 | Atlético Madrid - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 5 | Barcelona - La Liga 2017/2018 | 1 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 6 | Barcelona - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 7 | Celta Vigo - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 8 | Eibar - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 9 | Espanyol - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |
| 10 | Getafe - La Liga 2015/2016 | 38 | 0 | 0.0% | 0 | 0.0% | 0 / 0 / 0 | No |

## Product-validation shortlist

**No team-season in the local checkout is suitable for stable 360 pattern-context validation.** A requested 5-10 item shortlist cannot be produced honestly from one 360-enabled match.

Best available single-match pilots (not stable team-season validation):
- Barcelona - La Liga 2020/2021: 1/1 matches with 360, 95.4% event-moment alignment.
- Elche - La Liga 2020/2021: 1/1 matches with 360, 96.8% event-moment alignment.

## Readiness definition and limitations

A team-season is marked stable only with at least five 360-enabled matches, at least 25% distinct eligible-event alignment, and at least three family-pattern combinations containing ten aligned examples. This is an audit-only definition and does not change the current product minimum of three.

- Only physically materialized blobs available in the local repository checkout are audited; Git tree promises are reported separately and are not treated as readable data.
- Events from matches without a local 360 blob are never treated as spatially observed.
- Pattern thresholds count family-plus-pattern combinations and may overlap because moment labels can be multi-label.
- StatsBomb 360 is partial event-linked visible-area context, not continuous tracking.

The JSON artifact contains exhaustive competition-season, team-season, and family-level records. Spatial coverage is never extrapolated from matches without 360.
