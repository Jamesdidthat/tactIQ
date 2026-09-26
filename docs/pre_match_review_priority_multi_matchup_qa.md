# Pre-Match Review Priority multi-matchup product QA

**Audit date:** 2026-09-11  
**Provider:** StatsBomb Open Data  
**Competition-season:** La Liga 2015/16 (`competition_id=11`, `season_id=27`)  
**Scope:** 20 team profiles, 38 matches per team, 380 source matches, zero processing exclusions  
**Pairings screened:** all 190 possible team pairs  
**Pairings manually reviewed:** 10  
**Ranking or threshold changes during audit:** none

The machine-readable evidence is in
`artifacts/pre_match_review_priority_qa_v1.json`. It contains every priority's
full contract, baseline quartiles, coverage, match counts, source finding IDs,
selection reason, and candidate-selection audit. Pairing selection was based on
measured season medians rather than team reputation.

## Selection coverage

| # | Deliberate profile contrast | Pairing | Measured selection basis | Comparable metrics | Qualified directional interactions | Final priorities |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | Dominant possession vs dominant possession | Barcelona vs Real Madrid | Event-derived possession 65.2% vs 57.9% | 19 | 9 | 5 |
| 2 | Dominant possession vs low possession | Barcelona vs Sporting Gijón | 65.2% vs 43.9% | 19 | 4 | 5 |
| 3 | Dominant possession vs low possession, secondary | Real Madrid vs Eibar | 57.9% vs 45.5% | 19 | 4 | 5 |
| 4 | High shot volume vs low shot volume | Real Madrid vs Villarreal | 17.56 vs 8.65 shots/90 | 19 | 4 | 5 |
| 5 | High regain vs low regain | Atlético Madrid vs Las Palmas | 12.57 vs 7.74 high regains/90 | 19 | 2 | 3 |
| 6 | High regain vs low regain, secondary | Barcelona vs Valencia | 12.02 vs 8.15 high regains/90 | 19 | 4 | 5 |
| 7 | Closely matched teams | Levante UD vs Málaga | Robust multimetric distance 0.515 | 19 | 2 | 1 |
| 8 | Closely matched teams, secondary | Málaga vs Real Sociedad | Robust multimetric distance 0.535 | 19 | 2 | 1 |
| 9 | Fewest qualified interactions | Valencia vs Celta Vigo | 0 comparison findings; 2 interaction findings | 19 | 2 | 1 |
| 10 | Fewest qualified interactions | Valencia vs Real Sociedad | 0 comparison findings; 2 interaction findings | 19 | 2 | 1 |

No pairing among the 190 had zero qualified directional interaction findings;
the observed minimum was two. The final four cases therefore exercise the
closest available low-finding condition. Each produces a one-item shortlist.

Across all 190 screened pairs, qualified directional interaction counts were:
146 pairs with 2, 16 with 3, 12 with 4, 8 with 5, 6 with 6, 1 with 8, and 1
with 9. Qualified ordinary comparison findings ranged from zero to seven; 78
pairs had zero. These distributions are stored in the evidence artifact.

## Ordered shortlist evidence

Direction values are serialized exactly as the product contract uses them.
`Overlap` is the IQR overlap ratio; zero means the two interquartile intervals
do not intersect. All source IDs are retained in full in the JSON artifact.

### 1. Barcelona vs Real Madrid

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding(s) |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Real Madrid vs Barcelona: Defensive activity | `opponent_vs_target_season_tendency` | defensive activity | 0.830 | High | 0.00 | opponent comparison: `interceptions_per90` |
| 2 | Real Madrid attack vs Barcelona defence: Shot volume | `opponent_attack_vs_target_defence` | chance creation | 0.810 | Moderate | 0.00 | interaction: `shot_volume`; supporting `xg_production` |
| 3 | Barcelona attack vs Real Madrid defence: Penalty-area access | `target_attack_vs_opponent_defence` | penalty-area access | 0.806 | Moderate | 0.00 | interaction: `penalty_area_access` |
| 4 | Real Madrid attack vs Barcelona defence: Penalty-area access | `opponent_attack_vs_target_defence` | penalty-area access | 0.797 | Moderate | 0.00 | interaction: `penalty_area_access` |
| 5 | Barcelona attack vs Real Madrid defence: xG production | `target_attack_vs_opponent_defence` | chance creation | 0.777 | Moderate | 0.00 | interaction: `xg_production` |

Manual assessment: directional provenance is correct and the two penalty-area
items are genuinely opposite directions, not duplicates. Points 2–5 are useful
review targets, but shot volume/xG and the two access points create some thematic
density. Point 1 is detached and too broad: the primary evidence is interceptions,
while the title says defensive activity. The shortlist misses the obvious
possession/circulation contrast implied by the selection category. Evidence is
adequate and wording is non-prescriptive, but coherence is only moderate.

### 2. Barcelona vs Sporting Gijón

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Sporting Gijón vs Barcelona: Possession and circulation | `opponent_vs_target_season_tendency` | possession/circulation | 0.934 | High | 0.00 | opponent comparison: `pass_completion_rate` |
| 2 | Sporting Gijón vs Barcelona: Shot quality | `opponent_vs_target_season_tendency` | shot quality | 0.870 | High | 0.00 | opponent comparison: `shots_on_target_per90` |
| 3 | Sporting Gijón vs Barcelona: Penalty-area access | `opponent_vs_target_season_tendency` | penalty-area access | 0.839 | High | 0.00 | opponent comparison: `passes_into_penalty_area_per90` |
| 4 | Sporting Gijón vs Barcelona: Defensive activity | `opponent_vs_target_season_tendency` | defensive activity | 0.835 | High | 0.00 | opponent comparison: `interceptions_per90` |
| 5 | Sporting Gijón vs Barcelona: Shot and xG production | `opponent_vs_target_season_tendency` | chance creation | 0.797 | Moderate | 0.00 | opponent comparison: `xg_per90` |

Manual assessment: all five cards are statistically supported season contrasts,
but the section reads like a general team-profile comparison rather than a
pre-match matchup review. None of four qualified attack-versus-defence findings
survives. Points 1, 2, and 4 over-broaden their source metrics: pass completion
is not the whole circulation pattern, shots on target/90 is not shot quality,
and interceptions are not all defensive activity. Football usefulness is
mixed; points 3 and 5 are concrete, while the others are generic. The five-item
fill feels over-complete rather than selective.

### 3. Real Madrid vs Eibar

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Eibar vs Real Madrid: Possession and circulation | `opponent_vs_target_season_tendency` | possession/circulation | 0.929 | High | 0.00 | opponent comparison: `pass_completion_rate` |
| 2 | Eibar vs Real Madrid: Shot and xG production | `opponent_vs_target_season_tendency` | chance creation | 0.830 | High | 0.00 | opponent comparison: `shots_per90` |
| 3 | Real Madrid attack vs Eibar defence: Shot volume | `target_attack_vs_opponent_defence` | chance creation | 0.828 | High | 0.00 | interaction: `shot_volume` |
| 4 | Eibar vs Real Madrid: Progression | `opponent_vs_target_season_tendency` | progression | 0.818 | Moderate | 0.00 | opponent comparison: `progressive_carries_per90` |
| 5 | Eibar vs Real Madrid: Penalty-area access | `opponent_vs_target_season_tendency` | penalty-area access | 0.722 | Moderate | 0.00 | opponent comparison: `passes_into_penalty_area_per90` |

Manual assessment: direction is correct. Points 2 and 3 are distinct in formal
provenance but feel partly redundant to an analyst because both foreground shot
volume. Point 3 is the clearest matchup-specific question. Points 1 and 4 are
too generic for their actual source metrics. Evidence is adequate and there is
no causal overstatement, but the opponent's attacking production against Real
Madrid's exposure is absent.

### 4. Real Madrid vs Villarreal

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding(s) |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Villarreal vs Real Madrid: Shot and xG production | `opponent_vs_target_season_tendency` | chance creation | 0.861 | High | 0.00 | opponent comparison: `shots_per90` |
| 2 | Villarreal vs Real Madrid: Possession and circulation | `opponent_vs_target_season_tendency` | possession/circulation | 0.855 | High | 0.00 | opponent comparison: `pass_completion_rate` |
| 3 | Real Madrid attack vs Villarreal defence: xG production | `target_attack_vs_opponent_defence` | chance creation | 0.810 | Moderate | 0.00 | interaction: `xg_production`; supporting `shot_volume` |
| 4 | Villarreal vs Real Madrid: Progression | `opponent_vs_target_season_tendency` | progression | 0.783 | Moderate | 0.00 | opponent comparison: `progressive_carries_per90` |
| 5 | Villarreal vs Real Madrid: Penalty-area access | `opponent_vs_target_season_tendency` | penalty-area access | 0.772 | Moderate | 0.00 | opponent comparison: `passes_into_penalty_area_per90` |

Manual assessment: point 3 is strong and matchup-specific. Points 1 and 3 are
related enough to feel repetitive even though one compares team seasons and the
other compares production with concession. The remaining season comparisons
are readable but broad; pass completion and progressive carries are hidden
behind larger football-family labels. The high-vs-low shot-volume theme is
captured, but the five-point result lacks a single coherent review arc.

### 5. Atlético Madrid vs Las Palmas

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Las Palmas vs Atlético Madrid: Defensive activity | `opponent_vs_target_season_tendency` | defensive activity | 0.749 | Moderate | 0.00 | opponent comparison: `tackles_per90` |
| 2 | Las Palmas vs Atlético Madrid: High regains | `opponent_vs_target_season_tendency` | transition activity | 0.660 | Moderate | 0.11 | opponent comparison: `high_regains_per90` |
| 3 | Atlético Madrid attack vs Las Palmas defence: High regains and turnover exposure | `target_attack_vs_opponent_defence` | transition activity | 0.595 | High | 0.00 | cross-metric interaction: `high_regain_turnover_exposure` |

Manual assessment: the three-item length is appropriately restrained, and the
high-regain season contrast directly reflects the measured selection category.
However, points 2 and 3 are thematically repetitive. Point 3 feels misleading:
high-regain counts and turnover-to-shot exposure counts are different event
concepts with different natural frequencies, so zero distribution overlap and
a High evidence label do not make their numerical mismatch a meaningful
football interaction. Point 1 is also broader than its tackle-only evidence.

### 6. Barcelona vs Valencia

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Valencia vs Barcelona: Possession and circulation | `opponent_vs_target_season_tendency` | possession/circulation | 0.942 | High | 0.00 | opponent comparison: `pass_completion_rate` |
| 2 | Valencia vs Barcelona: Defensive activity | `opponent_vs_target_season_tendency` | defensive activity | 0.820 | Moderate | 0.00 | opponent comparison: `interceptions_per90` |
| 3 | Valencia vs Barcelona: Penalty-area access | `opponent_vs_target_season_tendency` | penalty-area access | 0.811 | High | 0.00 | opponent comparison: `passes_into_penalty_area_per90` |
| 4 | Valencia vs Barcelona: Shot quality | `opponent_vs_target_season_tendency` | shot quality | 0.773 | Moderate | 0.00 | opponent comparison: `shots_on_target_per90` |
| 5 | Valencia vs Barcelona: Shot and xG production | `opponent_vs_target_season_tendency` | chance creation | 0.754 | Moderate | 0.00 | opponent comparison: `xg_per90` |

Manual assessment: all five points are general season contrasts; none of four
qualified directional interactions survives. The selected list therefore does
not express the intended high-regain matchup contrast at all. Points 1, 2, and
4 are too generic for their source metrics, and “shot quality” from shots on
target/90 is potentially misleading. Direction and evidence coverage are
correct, but football usefulness as a pre-match shortlist is limited.

### 7. Levante UD vs Málaga

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Levante UD attack vs Málaga defence: High regains and turnover exposure | `target_attack_vs_opponent_defence` | transition activity | 0.588 | High | 0.00 | cross-metric interaction: `high_regain_turnover_exposure` |

Manual assessment: the one-item length is cautious, but the content is not. The
only selected point is the cross-metric comparison whose raw distributions are
not directly interpretable against one another. It should not become the sole
reason to review a close matchup merely because it clears the current score by
0.008. A zero-item shortlist would have been more trustworthy. No exact
duplicate survives and direction serialization is correct.

### 8. Málaga vs Real Sociedad

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Real Sociedad attack vs Málaga defence: High regains and turnover exposure | `opponent_attack_vs_target_defence` | transition activity | 0.597 | High | 0.00 | cross-metric interaction: `high_regain_turnover_exposure` |

Manual assessment: identical failure mode to pairing 7. The shortlist is short,
directionally correct, and non-prescriptive, but its only question is not a
sound like-for-like mismatch. It is not sufficiently useful to justify shortlist
placement, and the High evidence basis can be misread as semantic validity.

### 9. Valencia vs Celta Vigo

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Celta Vigo attack vs Valencia defence: High regains and turnover exposure | `opponent_attack_vs_target_defence` | transition activity | 0.595 | High | 0.00 | cross-metric interaction: `high_regain_turnover_exposure` |

Manual assessment: zero comparison findings and only two interaction findings
make a one-item or empty result appropriate. The layer chooses one item, but it
is again the cross-metric construct. The count is cautious; the content and High
label are not. No more obvious theme qualifies under the frozen rules, so the
correct product behavior would likely be an explicit low-evidence state rather
than filling with this comparison.

### 10. Valencia vs Real Sociedad

| Rank | Priority | Direction | Family | Score | Basis | Overlap | Source finding |
| ---: | --- | --- | --- | ---: | --- | ---: | --- |
| 1 | Real Sociedad attack vs Valencia defence: High regains and turnover exposure | `opponent_attack_vs_target_defence` | transition activity | 0.597 | High | 0.00 | cross-metric interaction: `high_regain_turnover_exposure` |

Manual assessment: the result repeats pairing 9's failure mode. Direction is
correct, the one-item cap is restrained, and no duplicate survives. Nevertheless,
the sole item compares different event concepts and is not a useful enough video
review question to justify selection. An empty state would be more credible.

## Cross-pair manual assessment matrix

| Pair | Coherence | Redundancy | Direction | Football usefulness | Evidence adequacy | Overstatement | Missing themes | Shortlist caution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Barcelona–Real Madrid | Moderate | Some thematic density | Correct | Mostly useful | Adequate | Low | Possession contrast | Five feels heavy |
| Barcelona–Sporting | Low as matchup narrative | No exact; broad profile sweep | Correct | Mixed | Adequate | Broad labels overstate metric scope | Directional interactions | Too full |
| Real Madrid–Eibar | Moderate | Shot-volume theme repeats | Correct | Mixed-good | Adequate | Low | Reverse interaction view | Too full |
| Real Madrid–Villarreal | Moderate | Chance creation repeats | Correct | Mixed-good | Adequate | Low | Defensive side of matchup | Too full |
| Atlético–Las Palmas | Moderate | High-regain theme repeats | Correct | Mixed | Numerically adequate | Cross-metric meaning overstated | Exact interaction | Count appropriate |
| Barcelona–Valencia | Low as matchup narrative | Broad profile sweep | Correct | Limited | Adequate | Shot-quality label too broad | Intended high-regain theme | Too full |
| Levante–Málaga | Single point | None | Correct | Low | Numerically adequate | Cross-metric High label misleading | No qualified exact theme | Short count, wrong content |
| Málaga–Real Sociedad | Single point | None | Correct | Low | Numerically adequate | Cross-metric High label misleading | No qualified exact theme | Short count, wrong content |
| Valencia–Celta Vigo | Single point | None | Correct | Low | Numerically adequate | Cross-metric High label misleading | No qualified exact theme | Empty would be safer |
| Valencia–Real Sociedad | Single point | None | Correct | Low | Numerically adequate | Cross-metric High label misleading | No qualified exact theme | Empty would be safer |

## Recurring failure modes

1. **Cross-metric high-regain/turnover comparisons are the largest correctness
   risk.** They survive in five of ten audits and are the only selected item in
   all four close/low-finding cases. The existing 0.65 comparability penalty is
   insufficient. High regains and turnovers followed by shots have different
   event meanings and natural rates; subtracting their medians and treating IQR
   separation as matchup strength feels misleading.
2. **Evidence basis can be confused with semantic validity.** Every selected
   cross-metric item says High because sample, coverage, and standardized
   separation are high. That label does not communicate that the two metrics
   are conceptually different.
3. **Season comparisons often crowd out matchup interactions.** Three five-item
   lists contain only general target/opponent season contrasts, despite having
   four qualified directional interactions. They read like abbreviated Team
   Profiles rather than pre-match review priorities.
4. **Football-family wording is broader than primary evidence.** “Defensive
   activity” can be based only on interceptions or tackles; “possession and
   circulation” can be based only on pass completion; “shot quality” can be
   based on shots on target/90. The collapsed card therefore sometimes promises
   more than its source metric supports.
5. **Exact duplicate suppression works, but analyst-perceived redundancy
   remains.** No pairing retained duplicate `(direction, football_family)` keys.
   However, season shot-volume contrasts and directional shot/xG interactions
   can occupy separate cards while expressing nearly the same review topic.
6. **The maximum is filled too readily in strong-contrast matchups.** Five of
   the first six cases return five points. Several fourth/fifth items are valid
   comparisons but too generic to deserve scarce shortlist space.
7. **Selection-category fidelity is inconsistent.** The high-regain Barcelona–
   Valencia case contains no high-regain priority, while dominant-possession
   pairings can be led by pass completion or omit possession entirely.
8. **Question grammar needs a presentation pass.** Plural subjects currently
   produce text such as “patterns differs.” This does not affect calculations,
   but reduces analyst trust.

## What worked

- All ten pairings used 19 definition-compatible metrics and full 38-match
  samples; there were no hidden coverage failures.
- Directional IDs and configured target/opponent baselines were correct in all
  inspected priorities.
- No exact semantic duplicate survived the deterministic deduplication key.
- No priority predicted an outcome, called a team weak, or prescribed a tactical
  action.
- Shortlists did contract to one item when exact evidence was sparse; the
  remaining problem is which item survived, not the ability to return fewer.

This audit documents failure modes only. Ranking weights, evidence thresholds,
deduplication rules, and product selection behavior were not changed.
