# Barcelona 2015/16 Match Story product QA

## Scope

This audit reviews five deliberately contrasting Barcelona matches. It evaluates the current deterministic output as a product narrative; it does not change thresholds, ranking, redundancy, archetype, or relationship logic. Scores below are internal deterministic priority scores, not probabilities or statistical confidence.

## Season-wide shortlist coverage

- Analysed matches: **38**
- Matches with zero qualifying story points: **5** — 266166, 267611, 266424, 266106, 265958
- Matches with only one qualifying story point: **5** — 3825637, 266670, 265894, 266664, 267506
- Five-match audit sample: **266961, 266620, 266653, 3825627, 266166**

## Match 266961 — Home vs RC Deportivo La Coruña

**Date:** 2015-12-12  
**Recorded score:** 2–2  
**Selection reason:** Four-point mixed story spanning a relationship, archetype, and single metrics.

| Order | Story point | Source | Score | Evidence | Supporting metrics |
| --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more penalty-area pass entries than expected | relationship | 0.851 | Moderate | passes_into_final_third_per90, passes_into_penalty_area_per90 |
| 2 | High shot volume, lower xG per shot | archetype | 0.612 | Exploratory | shots_per90, xg_per_shot |
| 3 | Barcelona's shots came from farther out | single-metric | 0.956 | Strong | average_shot_distance |
| 4 | Barcelona had more turnovers followed by an opposition shot | single-metric | 0.764 | Limited | turnovers_leading_to_shot_per90 |

### Manual product review

| Check | Assessment |
| --- | --- |
| Coherent | Partial |
| Redundant | Yes — the shot-volume/xG-per-shot archetype and longer-shot-distance point both describe shot quality from related angles. |
| Too statistical | Partial — ‘expected’ needs its season-relationship comparator visible to a football user. |
| Missing obvious context | Opponent, result, venue and match-state context are absent; the turnover-exposure point feels detached from the three attacking points. |
| Misleadingly strong | Possible — Strong means robust season deviation, not certainty or tactical importance. |

**QA verdict:** Useful attacking outline, but one semantic duplicate remains and the fourth point does not form a continuous narrative.


## Match 266620 — Home vs Granada

**Date:** 2016-01-09  
**Recorded score:** 4–0  
**Selection reason:** Relationship-led story with two archetypes and progression-related overlap risk.

| Order | Story point | Source | Score | Evidence | Supporting metrics |
| --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more progressive passes than expected | relationship | 0.854 | Moderate | possession_share_estimate, progressive_passes_per90 |
| 2 | High progression and chance creation | archetype | 0.727 | Moderate | progressive_passes_per90, xg_per90 |
| 3 | High-regain and pressure activity | archetype | 0.633 | Exploratory | high_regains_per90, pressures_per90 |
| 4 | Penalty-area access was unusually high | single-metric | 0.982 | Strong | passes_into_penalty_area_per90 |

### Manual product review

| Check | Assessment |
| --- | --- |
| Coherent | Partial |
| Redundant | Yes — progression appears in both the relationship residual and an archetype, despite the metrics not crossing the current overlap threshold. |
| Too statistical | Yes — multiple robust relationship/archetype concepts require the expanded evidence to understand. |
| Missing obvious context | No opponent, score, home/away or match-state explanation; the story does not say whether progression translated into territory or chances in plain sequence order. |
| Misleadingly strong | Possible — high component scores can make an internally overlapping story look more conclusive than it is. |

**QA verdict:** Evidence-rich but cognitively dense; it exposes semantic redundancy that metric-set overlap alone does not suppress.


## Match 266653 — Away vs Rayo Vallecano

**Date:** 2016-03-03  
**Recorded score:** 1–5  
**Selection reason:** Maximum-length five-point story with transition/direct-attack evidence.

| Order | Story point | Source | Score | Evidence | Supporting metrics |
| --- | --- | --- | --- | --- | --- |
| 1 | Barcelona recorded more explicitly tagged counter-attack shots than expected | relationship | 0.835 | Moderate | high_regains_per90, counter_attack_shots_per90 |
| 2 | High progression and chance creation | archetype | 0.771 | Moderate | progressive_passes_per90, xg_per90 |
| 3 | Lower possession with explicit counter attacks | archetype | 0.621 | Exploratory | possession_share_estimate, counter_attack_shots_per90 |
| 4 | Barcelona produced more set-play shots | single-metric | 0.750 | Limited | set_play_shots_per90 |
| 5 | Barcelona circulated at a lower volume | single-metric | 0.722 | Limited | passes_attempted_per90 |

### Manual product review

| Check | Assessment |
| --- | --- |
| Coherent | Partial |
| Redundant | Yes — two archetypes plus a relationship and single metrics create a long list with overlapping transition/direct-attack themes. |
| Too statistical | Yes — five points is heavy, and relationship residuals plus rule strengths compete for attention. |
| Missing obvious context | No sequence timing, opponent shape, score state, or explicit explanation tying high regains to the attacking observations. |
| Misleadingly strong | Possible — the full five-point story looks comprehensive although every statement remains descriptive and season-relative. |

**QA verdict:** Shows the value of diversity, but also the current upper-bound problem: five qualified points can still be too much for a coherent match story.


## Match 3825627 — Home vs Rayo Vallecano

**Date:** 2015-10-17  
**Recorded score:** 5–2  
**Selection reason:** Strong chance-conversion residual but no qualifying archetype.

| Order | Story point | Source | Score | Evidence | Supporting metrics |
| --- | --- | --- | --- | --- | --- |
| 1 | Chance creation was higher than shot volume would normally suggest | relationship | 0.989 | Strong | shots_per90, xg_per90 |
| 2 | Barcelona made more interceptions | single-metric | 1.000 | Strong | interceptions_per90 |
| 3 | Barcelona had less of the event-derived possession timeline | single-metric | 1.000 | Strong | possession_share_estimate |

### Manual product review

| Check | Assessment |
| --- | --- |
| Coherent | Partial |
| Redundant | No material metric duplication; the points are instead weakly connected. |
| Too statistical | Partial — the shots→xG expectation is meaningful but needs a football-readable comparator in the collapsed view. |
| Missing obvious context | The chance-creation, interception and possession observations are not joined by match phase, score state, or chronology. |
| Misleadingly strong | Yes, potentially — all three are Strong robust deviations, which can read like three confirmed tactical conclusions. |

**QA verdict:** The leading point is useful; the remaining points are notable facts rather than a coherent story arc.


## Match 266166 — Away vs Atlético Madrid

**Date:** 2015-09-12  
**Recorded score:** 1–2  
**Selection reason:** Zero-point control case for empty-state and threshold behavior.

*No story point passed the deterministic qualification and redundancy gates.*

### Manual product review

| Check | Assessment |
| --- | --- |
| Coherent | Not applicable — no point passed the evidence and redundancy gates. |
| Redundant | No. |
| Too statistical | No visible story, but the empty state should explain that ordinary does not mean uneventful. |
| Missing obvious context | The zero-point result gives no account of the match and cannot distinguish ‘typical relative to baseline’ from unavailable or tactically uneventful. |
| Misleadingly strong | No; the fail-closed behavior is appropriately cautious. |

**QA verdict:** Correctly unpadded. Product copy must avoid implying that no unusual season-relative metric means there was no match story.


## Cross-match failure modes

1. **Semantic redundancy is broader than metric overlap.** Related shot-quality or progression observations can survive because their exact metric sets differ.
2. **Diversity does not guarantee narrative coherence.** Points from attacking output, defensive activity and possession can be individually valid while lacking a joined match story.
3. **Relationship and archetype evidence remains cognitively statistical.** Collapsed cards need observed-versus-expected wording; robust z-scores and rule strengths belong in expanded evidence.
4. **Evidence labels can be over-read.** `Strong` currently describes robust season-relative deviation and coverage, not causal certainty, tactical importance, or repeatability.
5. **Match context is absent.** Opponent, result, venue, score state and chronology are not inputs to story selection, so the assembler cannot explain when or why observations occurred.
6. **Maximum-length stories can still feel overfilled.** Five diverse qualified points may be less useful than a tighter two- or three-point account.
7. **Zero-point behavior is cautious but ambiguous.** It correctly avoids padding, yet users need to understand that ‘no unusual season-relative evidence’ does not mean ‘nothing happened’.

## Product conclusion

The layer reliably produces traceable observations and fails closed, but it is not yet consistently a coherent *story*. The most important next design questions are semantic redundancy, context-aware linking, and whether source diversity should remain subordinate to narrative unity. No ranking changes were made during this audit.
