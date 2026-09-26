# Pre-Match Briefing Export QA

Frozen QA across 12 contrasting matchups. No analytical logic, rankings, thresholds, priority identities, ordering, or Evidence Pack contents were changed.

| Matchup | Priorities | Packs | Moments | Static pitches | Order | Export | Result |
|---|---:|---:|---:|---:|---|---:|---|
| Levante UD vs Málaga | 0 | 0 | 0 | 0 | Preserved | 200 | Pass |
| Málaga vs Real Sociedad | 0 | 0 | 0 | 0 | Preserved | 200 | Pass |
| Valencia vs Celta Vigo | 0 | 0 | 0 | 0 | Preserved | 200 | Pass |
| Valencia vs Real Sociedad | 0 | 0 | 0 | 0 | Preserved | 200 | Pass |
| Sevilla vs Athletic Club | 1 | 1 | 3 | 3 | Preserved | 200 | Pass |
| Celta Vigo vs Eibar | 1 | 1 | 3 | 3 | Preserved | 200 | Pass |
| Espanyol vs Sporting Gijón | 1 | 1 | 3 | 3 | Preserved | 200 | Pass |
| Real Sociedad vs Real Madrid | 3 | 3 | 9 | 9 | Preserved | 200 | Pass |
| Getafe vs Real Madrid | 3 | 3 | 9 | 9 | Preserved | 200 | Pass |
| Valencia vs Atlético Madrid | 3 | 3 | 9 | 9 | Preserved | 200 | Pass |
| Atlético Madrid vs Barcelona | 5 | 5 | 15 | 15 | Preserved | 200 | Pass |
| Barcelona vs Levante UD | 5 | 5 | 15 | 15 | Preserved | 200 | Pass |

## Export contract

- Dedicated action: Pass
- Dedicated deep link route: Pass
- Browser print action: Pass
- A4 page rule: Pass
- Print controls hidden: Pass
- Grayscale pitch: Pass
- Page break protection: Pass
- Deterministic priority order: Pass
- Static pitch renderer reused: Pass
- Generation timestamp: Pass
- Explicit video status: Pass
- Technical appendix separate: Pass
- Empty state present: Pass
- Live deep links present: Pass
- No ai generation: Pass

## Outcome

- Frozen matchups passed: **12/12**
- Evidence Packs loaded: **22**
- Representative moments selected for export: **66**
- Selected moments with static pitch data: **66**
- Empty, one-, three-, and five-priority briefing cases all rendered through the same deterministic export route.

## QA boundary

Production SPA routes and live API evidence were exercised. No installed browser automation runtime was available for pixel-level PDF pagination or physical-printer testing.
