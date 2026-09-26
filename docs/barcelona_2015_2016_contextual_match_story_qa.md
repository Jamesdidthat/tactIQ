# Barcelona 2015/16 context-aware Match Story QA

## Audit constraints

This is a frozen product audit of the context-aware assembler. No qualification,
ranking, topic, merge, context, chronology, selection, or wording logic was changed
during the audit. Internal scores are recorded for traceability and are not
probabilities or confidence estimates.

## Coverage

- Full season: **38 matches**
- Full-season story-length distribution: **0 points: 5 · 1 point: 19 · 2 points: 7 · 3 points: 7 · 4 points: 0**
- Audit sample: **10 matches**
- Audit story-length distribution: **0 points: 1 · 1 point: 2 · 2 points: 4 · 3 points: 3 · 4 points: 0**
- Source coverage: relationship-led, archetype-led, single-metric-only, and zero-point states are all represented.
- Score-state coverage: long-leading wins, all-drawing match, long-trailing loss, mixed-state matches, and one safely unavailable timeline are represented.

## Match 266961

**Home vs RC Deportivo La Coruña · team-relative score 2–2 · 2015-12-12**  
Score-state exposure: leading 50% · drawing 50% · trailing 0% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more penalty-area pass entries than expected | Relationship | territorial access | 1.000 | High | passes_into_final_third_per90, passes_into_penalty_area_per90 | 0′–94′ |
| 2 | High shot volume, lower xG per shot | Archetype | shot quality | 0.612 | Limited | shots_per90, xg_per_shot | 4′–80′ |
| 3 | Barcelona's shots came from farther out | Single-metric | shot location | 0.956 | High | average_shot_distance | 4′–80′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Yes |
| Semantic redundancy | Low |
| Football readability | High |
| Does context materially help? | Yes — the 2–2 result and equal leading/drawing exposure make the observations easier to situate. |
| Natural ordering | Natural: territorial access → shot-quality combination → shot location. |
| Detached point | None; shot location adds a concrete dimension to the shot-quality point. |
| Could evidence basis be misread? | Moderate risk — the relationship-led point displays High after merging a stronger same-topic single metric, although the relationship residual itself was Moderate. |


## Match 266620

**Home vs Granada · team-relative score 4–0 · 2016-01-09**  
Score-state exposure: leading 92% · drawing 8% · trailing 0% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more progressive passes than expected | Relationship | progression | 0.855 | Moderate | possession_share_estimate, progressive_passes_per90 | 0′–90′ |
| 2 | Penalty-area access was unusually high | Single-metric | territorial access | 0.982 | High | passes_into_penalty_area_per90 | 1′–90′ |
| 3 | High progression and chance creation | Archetype | chance creation | 0.727 | Moderate | progressive_passes_per90, xg_per90 | 1′–90′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Mostly |
| Semantic redundancy | Moderate — progressive passes appear in both the relationship and chance-creation archetype across adjacent topics. |
| Football readability | Moderate to high |
| Does context materially help? | Yes — Barcelona led for 92% of a 4–0, which is important descriptive context for the sustained attacking profile. |
| Natural ordering | Natural: progression → penalty-area access → chance creation. |
| Detached point | The archetype partly repeats the progression point, but adds xG. |
| Could evidence basis be misread? | Moderate risk: one High and two lower-basis points are distinguishable, but users may still equate basis with importance. |


## Match 266653

**Away vs Rayo Vallecano · team-relative score 5–1 · 2016-03-03**  
Score-state exposure: leading 77% · drawing 23% · trailing 0% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more explicitly tagged counter-attack shots than expected | Relationship | transition counter attack | 0.839 | Moderate | high_regains_per90, counter_attack_shots_per90, possession_share_estimate | 0′–91′ |
| 2 | High progression and chance creation | Archetype | chance creation | 0.771 | Moderate | progressive_passes_per90, xg_per90 | 1′–90′ |
| 3 | Barcelona produced more set-play shots | Single-metric | shot quantity | 0.750 | Limited | set_play_shots_per90 | 21′–82′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Partial |
| Semantic redundancy | Low at the exact-topic level; conceptual overlap remains between counter attacks and high progression/chance creation. |
| Football readability | Moderate |
| Does context materially help? | Yes — an away 5–1 with 77% leading exposure helps frame the large attacking outputs without explaining them. |
| Natural ordering | Mostly natural, but the set-play-shot point follows an open/transition sequence awkwardly. |
| Detached point | Set-play shot volume feels detached from the transition-led story. |
| Could evidence basis be misread? | Moderate risk: three separate basis labels are useful, but the complete three-point display can look more unified than the evidence is. |


## Match 266254

**Home vs Celta Vigo · team-relative score 6–1 · 2016-02-14**  
Score-state exposure: leading 49% · drawing 51% · trailing 0% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | High-regain and pressure activity | Archetype | transition counter attack | 0.903 | High | high_regains_per90, pressures_per90 | 0′–92′ |
| 2 | High progression and chance creation | Archetype | chance creation | 0.870 | High | progressive_passes_per90, xg_per90 | 1′–91′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Mostly |
| Semantic redundancy | Low — the two archetypes use distinct metric combinations. |
| Football readability | High |
| Does context materially help? | Yes — the 6–1 result and roughly equal drawing/leading exposure show that much of the match was not simply played with a long-established lead. |
| Natural ordering | Natural as defensive activity/transition → progression/chance creation. |
| Detached point | No clearly detached point, but aggregate chronology cannot prove the two patterns belonged to the same passages. |
| Could evidence basis be misread? | Moderate to high risk: both archetypes display High and may look like established match identities rather than unusually strong season-relative combinations. |


## Match 3825617

**Away vs Sevilla · team-relative score 1–2 · 2015-10-03**  
Score-state exposure: leading 0% · drawing 55% · trailing 45% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more penalty-area pass entries than expected | Relationship | territorial access | 0.994 | High | passes_into_final_third_per90, passes_into_penalty_area_per90 | 1′–93′ |
| 2 | Barcelona produced more set-play shots | Single-metric | shot quantity | 0.997 | High | set_play_shots_per90, shots_per90, open_play_shots_per90 | 3′–94′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Partial |
| Semantic redundancy | Low by topic, though penalty-area access and set-play shot volume are both routes to attacking territory. |
| Football readability | High |
| Does context materially help? | Yes — the away 1–2 loss and 45% trailing exposure materially temper a purely attacking reading. |
| Natural ordering | Broadly natural: territorial relationship before shot-source quantity. |
| Detached point | Set-play shots are not clearly connected to the final-third→penalty-area relationship. |
| Could evidence basis be misread? | Moderate risk — both display High, and the relationship point inherits that basis after same-topic merging even though its residual alone was weaker. |


## Match 266670

**Away vs Espanyol · team-relative score 0–0 · 2016-01-02**  
Score-state exposure: leading 0% · drawing 100% · trailing 0% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona produced fewer open-play shots | Single-metric | shot quantity | 0.728 | Limited | open_play_shots_per90 | 47′–55′ |
| 2 | Barcelona recorded fewer shots on target | Single-metric | shot quality | 0.862 | Moderate | shots_on_target_per90 | 63′–76′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Yes |
| Semantic redundancy | Low — shot quantity and on-target output are adjacent but distinct stages. |
| Football readability | High |
| Does context materially help? | Yes — 100% drawing exposure in a 0–0 strongly contextualizes the low attacking-output observations. |
| Natural ordering | Natural: open-play shot quantity → shots on target. |
| Detached point | None. |
| Could evidence basis be misread? | Low risk; the labels describe basis rather than certainty, though both points can still be mistaken for explanations of the draw. |


## Match 267327

**Home vs Real Betis · team-relative score 4–0 · 2015-12-30**  
Score-state exposure: leading Unavailable · drawing Unavailable · trailing Unavailable · source `event_goal_timeline_final_score_mismatch`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona registered fewer high regains | Single-metric | transition counter attack | 0.870 | Moderate | high_regains_per90 | 6′–62′ |
| 2 | Barcelona produced more set-play shots | Single-metric | shot quantity | 0.965 | High | set_play_shots_per90 | 6′–83′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | No |
| Semantic redundancy | Low — the metrics differ, but diversity is not coherence. |
| Football readability | High |
| Does context materially help? | Partly — opponent, venue and 4–0 score help, but score-state exposure is correctly unavailable because the event tally did not reconcile. |
| Natural ordering | Syntactically ordered from high regains to shots, but no evidence connects fewer high regains with more set-play shots. |
| Detached point | Both selected points feel detached from each other. |
| Could evidence basis be misread? | Moderate risk: two qualified points can look like a narrative despite the absence of a relationship or archetype connecting them. |


## Match 3825627

**Home vs Rayo Vallecano · team-relative score 5–2 · 2015-10-17**  
Score-state exposure: leading 66% · drawing 26% · trailing 8% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Chance creation was higher than shot volume would normally suggest | Relationship | chance creation | 0.989 | High | shots_per90, xg_per90 | 2′–77′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Yes — as a deliberately single-point story. |
| Semantic redundancy | None |
| Football readability | High |
| Does context materially help? | Yes — the 5–2 and mixed score-state exposure are useful context, while the assembler avoids attaching unrelated possession/interception points. |
| Natural ordering | Natural; there is only one leading observation. |
| Detached point | None. |
| Could evidence basis be misread? | Moderate risk: Evidence basis: High may still be read as certainty, but limitations and expected-value evidence are available. |


## Match 266664

**Away vs Real Sociedad · team-relative score 0–1 · 2016-04-09**  
Score-state exposure: leading 0% · drawing 4% · trailing 96% · source `event_goal_timeline_verified`

| # | Story point | Source | Topic | Internal score | Evidence basis | Supporting metrics | Event span |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Barcelona made more recoveries | Single-metric | defensive activity | 0.739 | Limited | recoveries_per90 | 2′–91′ |

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Yes — as a single observation, not a complete account. |
| Semantic redundancy | None |
| Football readability | High |
| Does context materially help? | Yes — trailing for 96% of a 0–1 loss makes recovery volume easier to inspect, without supporting a causal explanation. |
| Natural ordering | Natural; one point. |
| Detached point | None, but the observation alone is too narrow to summarize the match. |
| Could evidence basis be misread? | Low risk: Limited accurately tempers the single defensive-activity observation, though it does not indicate narrative completeness. |


## Match 266166

**Away vs Atlético Madrid · team-relative score 2–1 · 2015-09-12**  
Score-state exposure: leading 17% · drawing 79% · trailing 4% · source `event_goal_timeline_verified`

**State:** `no_qualifying_patterns`  
**Product wording:** No unusual season-relative patterns qualified. This does not mean the match lacked important events.

### Manual product assessment

| Question | Assessment |
| --- | --- |
| Narrative coherence | Appropriately absent |
| Semantic redundancy | None |
| Football readability | High |
| Does context materially help? | Yes — the away 2–1 win and mixed score state remain visible even though no unusual pattern qualifies. |
| Natural ordering | Not applicable. |
| Detached point | No point is invented; the explicit state correctly distinguishes no qualifying pattern from no important events. |
| Could evidence basis be misread? | No finding label is shown, so there is no certainty overstatement. |


## Explicit comparison with first-QA failure modes

| Previous failure mode | Current status | Observed improvement | Remaining risk |
| --- | --- | --- | --- |
| Semantic redundancy exceeded exact metric overlap | Improved | One selected point per semantic topic; same-topic metrics are merged. | Cross-topic overlap remains, notably progression inside a chance-creation archetype in 266620. |
| Source diversity did not ensure coherence | Improved | Selection now chooses a topical narrative component; source diversity is secondary. | 266653 and 267327 still combine points that are ordered but not demonstrably connected. |
| Relationship/archetype language was too statistical | Improved | Collapsed cards use observed-versus-expected evidence and football-readable titles. | ‘Expected’ and multi-metric archetypes still require expanded definitions for full understanding. |
| Strong evidence could be read as certainty | Improved, not eliminated | Cards now say Evidence basis: High/Moderate/Limited. | High can still be mistaken for tactical importance; a merged topic can also inherit High from a single metric when its relationship residual was only Moderate. |
| Opponent, result, venue, score state and chronology absent | Materially improved | All are attached where verified; compact event spans are shown. | Context organizes interpretation but does not connect aggregate findings to the same passage of play; five score-state timelines remain unavailable. |
| Five-point stories felt overfilled | Resolved in this season | Default cap is four; no Barcelona story currently exceeds three points. | Three points can still be too many when unity is weak, as in 266653. |
| Zero-point state was ambiguous | Resolved | Explicit wording says no unusual season-relative pattern qualified and does not deny important events. | The state still cannot provide a match account, by design. |

## Overall product judgment

The refactor materially improved shortlist length, exact semantic duplication,
context visibility, and fail-closed behavior. The strongest outputs are 266961,
266620, 266670 and the deliberately single-point 3825627. The principal remaining
failure mode is **false narrative unity**: topical adjacency and broad chronology
can organize observations but cannot prove that they arose from the same match
passages. Match 267327 is the clearest failure, while 266653 remains partially
overfilled by a detached set-play point. Evidence-basis wording is safer than the
old confidence-like label, but `High` still needs its visible definition as
season-relative evidence adequacy rather than tactical certainty. Merged points
can also inherit the highest basis from a secondary candidate, potentially
overstating the basis of the relationship used as the point's title.
