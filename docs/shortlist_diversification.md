# Deterministic shortlist diversification

Diversification is applied after the existing evidence score and redundancy
suppression. It does not recalculate or modify any priority component. The
complete priorities table retains every finding, including duplicate-suppressed
and quality-gated rows, and adds a `finding_family` audit column.

## Families and default caps

| Family | Finding types | Default cap |
| --- | --- | ---: |
| `phase_shape` | `phase_shape_variability` | 4 |
| `team_shape_extreme` | `team_shape_extreme` | 2 |
| `shot_sequence_local_context` | `shot_sequence_density`, `shot_local_context` | 2 |
| `other` | Any future/unmapped type | 2 |

`prioritize_findings` accepts a `family_caps` mapping to override individual
defaults. Caps must be positive integers.

## Selection rule

1. Exclude redundancy-suppressed findings from shortlist selection.
2. Apply the default quality gates: priority score at least 0.35 and evidence
   strength at least 0.55. Both are configurable. Gating changes selection only.
3. Seed the best eligible finding from each family, visiting family leaders in
   original score order. Record `top_phase_shape`, `top_team_shape_extreme`,
   `top_shot_sequence`, or `top_other`.
4. Fill remaining slots in original priority order, subject to family caps.
   Record `priority_fill`.
5. If exactly one family passes the gates, permit that family to exceed its cap
   to fill available slots. Record `single_family_fallback` for cap-exceeding
   selections. Weak findings never become eligible through this fallback.
6. Present selected findings in their original priority-score order, with
   finding ID as the deterministic tie-breaker.

The v1 shortlist and finding-detail responses expose `selection_reason` while
preserving `priority_score` and its component values.

## Match 2017461

The current real-match run contains 40 underlying findings and returns six
shortlisted findings:

- four phase-shape findings (one `top_phase_shape`, three `priority_fill`);
- two team-shape extremes (one `top_team_shape_extreme`, one `priority_fill`).

The two shot-sequence density findings remain in the priorities table but do
not pass the 0.35 minimum priority gate. Their previous scores were roughly
0.23, so diversification does not promote them for the sake of category variety.
