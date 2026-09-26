# Frozen Pre-Match Briefing End-to-End Product QA

## Scope

Audited **12** contrasting 2015/16 La Liga matchups and traversed **22** complete priority workflows. No selection, ranking, grouping, threshold, or analytical logic changed.

Shortlist distribution: 0 priorities: 4, 1 priorities: 3, 3 priorities: 3, 5 priorities: 2.

## Outcome summary

| Check | Result |
|---|---:|
| Complete matchup workflows | 12/12 |
| Briefing load failures | 0 |
| Broken Evidence Pack links | 0 |
| Evidence Pack load failures | 0 |
| Empty Evidence Packs | 0 |
| Briefing/evidence wording mismatches | 0 |
| Pitch-detail failures | 0 |
| Priority order failures | 0 |
| Representative moments/details | 176 / 176 |

## Matchup audit

| # | Matchup | Priorities | Workflow | Moments | Details | Assessment |
|---:|---|---:|---|---:|---:|---|
| 1 | Levante UD vs Málaga | 0 | Pass | 0 | 0 | Clear cautious empty state |
| 2 | Málaga vs Real Sociedad | 0 | Pass | 0 | 0 | Clear cautious empty state |
| 3 | Valencia vs Celta Vigo | 0 | Pass | 0 | 0 | Clear cautious empty state |
| 4 | Valencia vs Real Sociedad | 0 | Pass | 0 | 0 | Clear cautious empty state |
| 5 | Sevilla vs Athletic Club | 1 | Pass | 8 | 8 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 6 | Celta Vigo vs Eibar | 1 | Pass | 8 | 8 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 7 | Espanyol vs Sporting Gijón | 1 | Pass | 8 | 8 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 8 | Real Sociedad vs Real Madrid | 3 | Pass | 24 | 24 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 9 | Getafe vs Real Madrid | 3 | Pass | 24 | 24 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 10 | Valencia vs Atlético Madrid | 3 | Pass | 24 | 24 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 11 | Atlético Madrid vs Barcelona | 5 | Pass | 40 | 40 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |
| 12 | Barcelona vs Levante UD | 5 | Pass | 40 | 40 | Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms. |

## Analyst path assessment

For non-empty briefings, the path is explicit: the ranked card states the review question and compact evidence comparison, `Open Evidence Pack` opens the matching source evidence, the first representative moment is selected automatically, and its ordered event sequence is drawn on the native StatsBomb pitch. Empty briefings stop cleanly without inventing themes.

Baseline values appear once in the briefing and again in the detailed Evidence Pack. This repetition functions as orientation and does not introduce a second or conflicting claim. Technical provenance remains collapsed.

## Remaining friction

- Evidence Pack and moment detail remain inline on the briefing page; URL state now makes both levels refreshable and shareable.
- Scroll restoration is explicit when returning from an Evidence Pack and browser-native for history navigation, but exact pixel restoration remains browser-dependent.
- Main briefing copy uses usual match range and usual conceded median; exact quartiles remain available in evidence values.
- Provider, raw identity, coordinate system, and capability keys are confined to expanded Technical provenance.
- Linked source video is unavailable for every audited briefing, so the workflow ends at event and pitch evidence rather than footage.

## UI states

- `dedicated_briefing_route`: present
- `briefing_loading_state`: present
- `briefing_error_state`: present
- `briefing_empty_state`: present
- `briefing_to_full_comparison_link`: present
- `priority_to_evidence_pack_control`: present
- `evidence_pack_loading_state`: present
- `evidence_pack_error_state`: present
- `evidence_pack_empty_moment_state`: present
- `pitch_detail_empty_state`: missing
- `evidence_pack_close_control`: present
- `technical_provenance_collapsed`: present
- `raw_selection_reason_hidden_from_briefing`: present
- `human_readable_profile_selectors`: present
- `artifact_catalog_drives_selectors`: present
- `priority_deep_link_state`: present
- `moment_deep_link_state`: present
- `browser_back_state_restoration`: present
- `moment_to_pack_back_control`: present
- `pack_to_briefing_back_control`: present
- `technical_fields_demoted`: present

## Audit limitation

UI states and navigation controls were inspected from the compiled React path and source contract; the audit does not claim browser-level visual or accessibility automation.

## Conclusion

The deterministic workflow is contract-complete when every link, pack, moment, and pitch-detail check passes. Remaining friction is presentation/navigation related and does not alter the underlying evidence.

No product or analytical logic was changed during this audit.
