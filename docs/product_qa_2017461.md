# Product QA — SkillCorner match 2017461

Run date: 2026-09-06  
Source: real local SkillCorner Open Data match `2017461` through the v1 localhost API.  
Match: Melbourne Victory (MEL) 0–1 Auckland FC (AUC), 2025-05-17.

## API and coverage

The real analysis completed successfully: 33 deterministic findings were
generated and eight non-duplicate findings were eligible for the product
shortlist. The UI therefore has eight findings, rather than ten. This is
expected from the current duplicate-suppression rule, not an API failure.

`team_shape`, `phase_shape_analysis`, `local_defensive_context`, and
`temporal_shot_analysis` ran. Pitch visualisation, defensive-line structure,
and ball-goal geometry were supported by the source capabilities but are not
yet implemented in the match orchestrator. No warnings were returned.

All required endpoints responded using the unchanged v1 payload shapes:

- `GET /matches/2017461/summary`
- `GET /matches/2017461/findings`
- `GET /matches/2017461/coverage`
- `GET /matches/2017461/findings/{finding_id}`
- `GET /matches/2017461/findings/{finding_id}/moments/0/frame`

Each representative-frame response contained 22 players and a ball. A request
with `Origin: http://127.0.0.1:5173` correctly received the matching local CORS
header.

## Ranked findings in UI order

There are only eight eligible observations for the ten-slot shortlist. “Clear”
means understandable by a football analyst from the UI text alone; it does not
claim that the description demonstrates causation. “Frame support” assesses a
single current pitch snapshot, not the underlying numerical evidence pack.

| Rank | Finding | Evidence strength | Sample | Clear | Frame support | Limitations surfaced |
| ---: | --- | ---: | ---: | --- | --- | --- |
| 1 | AUC variable create shape | 0.85 | 3,477 frames | Yes | No — a single frame cannot establish IQR/variation | Yes |
| 2 | AUC variable defending_direct shape | 0.85 | 828 frames | Yes | No — a single frame cannot establish IQR/variation | Yes |
| 3 | MEL variable build_up shape | 0.85 | 1,573 frames | Yes | No — a single frame cannot establish IQR/variation | Yes |
| 4 | MEL variable chaotic shape | 0.85 | 2,769 frames | Mostly — “chaotic” is a provider phase label | No — a single frame cannot establish IQR/variation | Yes |
| 5 | AUC high-tail outfield length | 0.85 | 40,404 frames | Yes | Partly — positions are visible, but no length overlay is drawn | Yes |
| 6 | MEL high-tail outfield length | 0.85 | 40,404 frames | Yes | Partly — positions are visible, but no length overlay is drawn | Yes |
| 7 | AUC dense pre-shot event sequences | 0.55 | 13 shots | Yes | No — pitch positions do not show ten-second event density | Yes |
| 8 | MEL dense pre-shot event sequences | 0.55 | 10 shots | Yes | No — pitch positions do not show ten-second event density | Yes |

The detail view exposes the exact metrics, comparator, source frame/time
references, provider capabilities, coverage, and the limitation text for each
row. The limitation wording appropriately keeps all outputs descriptive and
non-causal.

## QA observations

1. The ranking order is deterministic, but the first four findings are tied on
   priority score (0.917). They are distinct team/phase/possession contexts,
   yet their similar “variable shape” wording can feel repetitive in a short
   analyst list.
2. Representative pitch frames are technically correct (22 players plus ball)
   but are not sufficient visual evidence for distributional findings such as
   IQR or pre-shot event density. A future presentation improvement would be a
   small range/trajectory or metric-overlay view. This is a UI evidence issue,
   not a problem with the v1 contract or analysis result.
3. The `chaotic` label is provider supplied. It is retained transparently, but
   a UI tooltip explaining that it is a SkillCorner phase label would reduce
   ambiguity.
4. First access to a real match is computationally heavy. The local service now
   caches both the completed `MatchAnalysisResult` and the resolved canonical
   match bundle, so subsequent summary, detail, and frame calls do not reload
   the tracking data or rerun analysis. The frontend already has a loading
   state; a future progress indicator would make the first-run wait clearer.
5. The frontend remains mock-first by default. For the live run it must be
   started with `VITE_USE_MOCK=false`, `VITE_API_BASE_URL=http://127.0.0.1:8000`,
   and `VITE_MATCH_ID=2017461`, alongside the localhost API process.

## Verification

- Product-service tests: 5 passed, including the new resolved-bundle cache
  regression test.
- Frontend production build: passed from `frontend/`.
- Live HTTP checks: summary, rankings, coverage, all eight details, all eight
  representative frames, and local-development CORS passed.
