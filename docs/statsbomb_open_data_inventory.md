# StatsBomb Open Data canonical-ingestion inventory

**Schema:** `tactiq.statsbomb-inventory.v1`  
**Provider:** `statsbomb_open_data`

## Canonical boundary

- Events: available for 3,961 matches.
- Lineups: available for 3,961 matches.
- 360 snapshots: available for 426 matches and stored only as event-linked snapshots.
- Continuous tracking: **not available** and always declared `False`.
- StatsBomb's 120 x 80 locations retain explicit `statsbomb_120x80` coordinate provenance; they are not labelled as metres.

## Coverage summary

| Measure | Count |
| --- | ---: |
| Competition-season datasets | 80 |
| Matches | 3,961 |
| Distinct team IDs | 354 |
| Competition-season-team samples with 5+ matches | 289 |
| Competition-season-team samples with 10+ matches | 209 |
| Competition-season-team samples with 20+ matches | 189 |
| Global teams with 5+ matches | 252 |
| Global teams with 10+ matches | 197 |
| Global teams with 20+ matches | 168 |

## Repository asset audit

| asset_type | repository_blobs | indexed_matches | unindexed_blobs | indexed_matches_missing_blob |
| --- | --- | --- | --- | --- |
| events | 4235 | 3961 | 274 | 0 |
| lineups | 4235 | 3961 | 274 | 0 |
| three-sixty | 426 | 426 | 0 | 3535 |

The official Git tree contains 274 event and
lineup blobs that are not present in the current match metadata index. They are
reported here but excluded from competition/team coverage because their team
and competition identity cannot be resolved authoritatively from the configured
metadata.

## Largest competition-season datasets

| competition_name | season_name | matches_available | teams_available | teams_at_least_5 | teams_at_least_10 | teams_at_least_20 | matches_with_360 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| La Liga | 2015/2016 | 380 | 20 | 20 | 20 | 20 | 0 |
| Premier League | 2015/2016 | 380 | 20 | 20 | 20 | 20 | 0 |
| Serie A | 2015/2016 | 380 | 20 | 20 | 20 | 20 | 0 |
| Ligue 1 | 2015/2016 | 377 | 20 | 20 | 20 | 20 | 0 |
| Liga F | 2023/2024 | 240 | 16 | 16 | 16 | 16 | 0 |
| NWSL | 2023 | 137 | 12 | 12 | 12 | 12 | 0 |
| FA Women's Super League | 2023/2024 | 132 | 12 | 12 | 12 | 12 | 0 |
| Frauen Bundesliga | 2023/2024 | 132 | 12 | 12 | 12 | 12 | 0 |
| FA Women's Super League | 2020/2021 | 131 | 12 | 12 | 12 | 12 | 0 |
| Serie A Women | 2023/2024 | 130 | 10 | 10 | 10 | 10 | 0 |
| Indian Super league | 2021/2022 | 115 | 11 | 11 | 11 | 11 | 0 |
| FA Women's Super League | 2018/2019 | 107 | 11 | 11 | 11 | 5 | 0 |
| FA Women's Super League | 2019/2020 | 87 | 12 | 12 | 12 | 0 | 0 |
| FIFA World Cup | 2018 | 64 | 32 | 8 | 0 | 0 | 0 |
| FIFA World Cup | 2022 | 64 | 32 | 8 | 0 | 0 | 64 |
| Women's World Cup | 2023 | 64 | 32 | 8 | 0 | 0 | 64 |
| African Cup of Nations | 2023 | 52 | 24 | 8 | 0 | 0 | 1 |
| Women's World Cup | 2019 | 52 | 24 | 8 | 0 | 0 | 0 |
| UEFA Euro | 2020 | 51 | 24 | 8 | 0 | 0 | 51 |
| UEFA Euro | 2024 | 51 | 24 | 8 | 0 | 0 | 51 |

## Largest team samples within one competition-season

| competition_name | season_name | team | matches_available | matches_with_360 | at_least_5_matches | at_least_10_matches | at_least_20_matches |
| --- | --- | --- | --- | --- | --- | --- | --- |
| La Liga | 2014/2015 | Barcelona | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Athletic Club | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Atlético Madrid | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Barcelona | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Celta Vigo | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Eibar | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Espanyol | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Getafe | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Granada | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Las Palmas | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Levante UD | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Málaga | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | RC Deportivo La Coruña | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Rayo Vallecano | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Real Betis | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Real Madrid | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Real Sociedad | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Sevilla | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Sporting Gijón | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Valencia | 38 | 0 | True | True | True |
| La Liga | 2015/2016 | Villarreal | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | AS Monaco | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Angers | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Guingamp | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Lille | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Lorient | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Lyon | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Montpellier | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | Nantes | 38 | 0 | True | True | True |
| Ligue 1 | 2015/2016 | OGC Nice | 38 | 0 | True | True | True |

## Local checkout configuration

The official repository is configured as a partial clone at `external_data\statsbomb_open_data`. All competition and match metadata are materialized for complete coverage counts. Representative match `3764440` includes events, lineups, and 360; match `9880` includes events and lineups without 360. Other event/lineup blobs remain available from the official Git tree and can be materialized on demand without changing the adapter.

This report proves ingestion and coverage only. It adds no tactical metrics and makes no claim that sparse 360 freeze frames form a continuous trajectory.
