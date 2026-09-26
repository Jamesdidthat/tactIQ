# Dataset inventory and provider expansion plan

**Inventory schema:** `tactiq.dataset-inventory.v1`

This inventory distinguishes raw match availability, canonical-adapter readiness, and the stricter period-consistent readiness required by the current Team Profile. It does not add tactical metrics or infer unavailable provider capabilities.

## Provider coverage

| provider | matches_available | teams_available | matches_canonical_adapter_ready | matches_team_profile_ready | continuous tracking | ball tracking | verified roles | attacking direction | events | phases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| metrica_public_sample | 1 | 2 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 0 |
| skillcorner_open_data | 10 | 12 | 10 | 6 | 10 | 10 | 10 | 10 | 10 | 10 |

## Team coverage

| provider | competition | season | team | matches_available | matches_team_profile_ready | has_continuous_tracking | has_verified_roles | has_attacking_direction | has_events | has_tactical_phases | canonical_adapter_can_process_today |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| skillcorner_open_data | A-League | 2024/2025 | Auckland FC | 4 | 2 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Melbourne Victory Football Club | 2 | 2 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Western United | 2 | 2 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Melbourne City FC | 2 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Sydney Football Club | 2 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Wellington Phoenix FC | 2 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| metrica_public_sample | Metrica Public Sample | Unspecified | Metrica Away | 1 | 1 | Yes | No | Yes | No | No | Yes |
| metrica_public_sample | Metrica Public Sample | Unspecified | Metrica Home | 1 | 1 | Yes | No | Yes | No | No | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Brisbane Roar FC | 1 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Macarthur FC | 1 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Perth Glory Football Club | 1 | 1 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Adelaide United Football Club | 1 | 0 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Central Coast Mariners Football Club | 1 | 0 | Yes | Yes | Yes | Yes | Yes | Yes |
| skillcorner_open_data | A-League | 2024/2025 | Newcastle United Jets FC | 1 | 0 | Yes | Yes | Yes | Yes | Yes | Yes |

## Current exclusions

| provider | match_id | team | canonical_adapter_ready | exclusion_reason |
| --- | --- | --- | --- | --- |
| skillcorner_open_data | 1886347 | Auckland FC | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1886347 | Newcastle United Jets FC | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1899585 | Auckland FC | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1899585 | Wellington Phoenix FC | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1953632 | Central Coast Mariners Football Club | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1953632 | Melbourne City FC | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1996435 | Sydney Football Club | Yes | canonical tactical-phase and tracking periods disagree |
| skillcorner_open_data | 1996435 | Adelaide United Football Club | Yes | canonical tactical-phase and tracking periods disagree |

## Capability-limited but processable matches

| provider | match_id | team | capability_limitations |
| --- | --- | --- | --- |
| metrica_public_sample | metrica_sample_game_1 | Metrica Home | verified roles, events, and tactical phases are unavailable |
| metrica_public_sample | metrica_sample_game_1 | Metrica Away | verified roles, events, and tactical phases are unavailable |

## Expansion decision

- Highest current Team Profile-ready match count for one team: **2**.
- Teams with at least five profile-ready matches: **0**.
- SkillCorner remains the only locally configured source with verified roles, events, tactical phases, and continuous tracking together.
- Metrica validates the provider-independent tracking contract, but its one sample match lacks verified roles and mapped canonical events/phases, so it cannot expand stable team profiles.
- StatsBomb Open Data is not installed or configured locally. It is a prospective event-profile source; 360 data must remain explicitly snapshot-based and cannot be presented as continuous tracking.

**Planning conclusion:** the local repository cannot currently reach the 5-10 match range for any team. External data acquisition is the next bottleneck. The fastest useful expansion is either more period-consistent SkillCorner matches for repeated teams or a separately capability-labelled event-profile track from a multi-match event provider.
