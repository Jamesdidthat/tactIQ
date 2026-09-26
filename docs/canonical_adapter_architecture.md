# Canonical provider-adapter architecture

Every provider adapter now returns one `CanonicalMatchBundle`.  It carries
typed capability metadata plus schema-validated canonical tables rather than
exposing provider-native file conventions to analysis code.

| Canonical table | Required identity / geometry fields |
| --- | --- |
| `matches` | `match_id`, pitch length and width in metres |
| `teams` | `match_id`, `team_id`, code |
| `roster` | player/team IDs, position, position group, goalkeeper flag |
| `player_positions` | match/frame/period/time, player/team IDs, centred metre x/y |
| `ball_positions` | match/frame/period/time, centred metre ball x/y |
| `attacking_directions` | match/period/team, `attacking_x_sign` in `{-1, +1}` |
| `events` | match/event/period/team, event type, `is_shot` |
| `tactical_phases` | match/period, `[frame_start, frame_end_exclusive)`, possession team |

`validate_canonical_bundle` checks match identity, uniqueness of player and
ball frame keys, team references, declared capability/table consistency, phase
interval validity, and direction signs.

## Capability gate

`supported_analyses(bundle)` reports support and reasons for every analysis;
`require_analysis_support(bundle, analysis)` raises before execution.  The
current requirements are:

| Analysis | Required capabilities |
| --- | --- |
| Pitch visualization | continuous tracking, ball tracking |
| Team Shape | continuous tracking, verified roles |
| Defensive lines | continuous tracking, verified roles, direction |
| Local defensive context / ball-goal geometry | continuous tracking, ball tracking, verified roles, direction |
| Temporal shot analysis | continuous tracking, ball tracking, events, tactical phases |
| Phase Shape | continuous tracking, verified roles, tactical phases |

SkillCorner Open Data declares all current capabilities.  Metrica Sample Game
1 declares continuous player/ball tracking and configured direction, but not
verified roles, events, or tactical phases.

Metrica's public CSV does not contain positions/goalkeeper roles.  Its sample
role map is therefore unavailable by default.  It can only be activated with
`allow_assumed_roles=True`; capabilities retain `has_verified_roles=False` and
record `has_assumed_roles=True`.  Role-dependent analyses remain blocked unless
their caller explicitly passes the same development override to the support
gate.  This makes the assumption visible in code and prevents it leaking into
normal analysis runs.
