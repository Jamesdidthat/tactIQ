# Pre-Match Briefing Usability QA

Frozen product QA across 12 matchups. Analytical logic, priority identities, ranking, thresholds, and ordering were unchanged.

| Matchup | Priorities | Briefing | Pack | Moment | Deep link | Refresh | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Levante UD vs Málaga | 0 | 200 | — | — | 200 | 200 | Pass |
| Málaga vs Real Sociedad | 0 | 200 | — | — | 200 | 200 | Pass |
| Valencia vs Celta Vigo | 0 | 200 | — | — | 200 | 200 | Pass |
| Valencia vs Real Sociedad | 0 | 200 | — | — | 200 | 200 | Pass |
| Sevilla vs Athletic Club | 1 | 200 | 200 | 200 | 200 | 200 | Pass |
| Celta Vigo vs Eibar | 1 | 200 | 200 | 200 | 200 | 200 | Pass |
| Espanyol vs Sporting Gijón | 1 | 200 | 200 | 200 | 200 | 200 | Pass |
| Real Sociedad vs Real Madrid | 3 | 200 | 200 | 200 | 200 | 200 | Pass |
| Getafe vs Real Madrid | 3 | 200 | 200 | 200 | 200 | 200 | Pass |
| Valencia vs Atlético Madrid | 3 | 200 | 200 | 200 | 200 | 200 | Pass |
| Atlético Madrid vs Barcelona | 5 | 200 | 200 | 200 | 200 | 200 | Pass |
| Barcelona vs Levante UD | 5 | 200 | 200 | 200 | 200 | 200 | Pass |

## State and navigation

- Human readable selectors: Pass
- Ids preserved as hidden api identity: Pass
- Priority in url: Pass
- Moment in url: Pass
- Popstate restoration: Pass
- Back to evidence pack: Pass
- Back to briefing: Pass
- Technical provenance collapsed: Pass
- Football facing range wording: Pass

## Outcome

**12/12 matchups passed.** Available profile count: 20. Manual URL editing required: no.

## QA boundary

- Linked video remains unavailable in StatsBomb Open Data.
- This environment has no installed browser automation runtime; QA exercised the production SPA route, live API/CORS boundary, persisted deep-link contract, refresh round-trip, and compiled interaction states rather than pixel-level rendering or accessibility automation.
