# Tactical geometry feature set: dataset-expansion readiness

**Status:** frozen at the current ball-to-goal / passing-lane feature set.  This
document records the input contract; it does not add an adapter, substitute
provider fields, or relax validation.

## Current feature boundary

The frozen feature set comprises native and attack-normalised team shape and
line structure, ball-relative local defensive context, attacker allocation,
and ball-to-goal / direct passing-lane geometry.  The geometry layer needs a
tracked ball and all available players at the same frame.  It deliberately
uses a *nearest-attacker-to-ball carrier proxy*, not an inferred possession
player.

The current default geometry thresholds are parameters, not provider facts:

| Definition | Default |
| --- | ---: |
| Pitch | 105 x 68 m |
| Ball-to-goal corridor half-width | 3 m |
| Passing-lane defender clearances | 1 m, 2 m, 3 m |
| Carrier central-route clearance | 2 m |
| Attacking penalty corridor | final 16.5 m; `abs(y) <= 20.16 m` |

All geometry is calculated in attack-normalised coordinates: attacking goal
centre is `(pitch_length / 2, 0)` and increasing x points toward that goal.

## Source-field inventory

| Source | Mandatory for core geometry | Mandatory for temporal shot/control analysis | Optional / enrichment-only | SkillCorner-specific representation |
| --- | --- | --- | --- | --- |
| Tracking | `frame`, `period`, per-frame `player_data[].player_id`, `x`, `y`; `ball_data.x`, `ball_data.y` | Frame/time continuity at 10 Hz (or known sampling rate), `timestamp`/elapsed time | `is_detected`; raw timestamp string | JSONL nesting as `player_data` / `ball_data`; `tracking_extrapolated` file name |
| Match metadata | match/team IDs; roster mapping `players[].id -> team_id`; goalkeeper/position-group role; pitch length/width; attacking direction by period | Match ID and both team IDs, period-direction map | Player names, shirt number, acronym, date | `home_team_side`; `player_role.name`, `player_role.position_group`; home/away object shape |
| Phases of play | Not required for a single-frame geometric calculation | `match_id`, `period`, `frame_start`, `frame_end`, possession team ID, out-of-possession phase label; interval rule `start <= frame < end` | Short names; interval duration; possession lead-to-shot/goal | SkillCorner phase taxonomy and `team_in_possession_*` / `team_out_of_possession_*` columns; supplied lead flags |
| Dynamic events | Not required | Event ID, match/team/period, shot event label, shot frame (`frame_end`), event time where used for alignment | `start_type`, `carry`, `quick_pass`, `high_pass`, `pass_range`, `pass_direction`, `n_opponents_bypassed`, player/team names | `event_type=player_possession`, `end_type=shot`, Dynamic Events action taxonomy and exact flag semantics |

### Minimum viable contracts

**Core geometry** needs synchronized player and ball coordinates, player-to-team
identity, an explicit goalkeeper flag/role, pitch dimensions, both team IDs,
and a direction value for every analysed team-period.  Without the direction
value, distances still work, but goal-side, penalty-corridor, ball-to-goal,
and line-position features cannot be consistently normalised.

**Temporal shot analysis** additionally needs a reliably aligned shot instant,
continuous (or explicitly sampled) frames spanning at least five seconds
before it, period-consistent phase intervals, possession team, and a way to
select comparable non-shot controls from the same defensive context.  The
current implementation assumes 10 Hz; a provider adapter must expose a
sampling rate and convert time windows rather than hard-code ten frames/s.

## Provider-agnostic canonical schema

An adapter should produce these logical tables.  Field names are proposed
canonical names, not a claim that every provider supplies every field.

### `matches`

`match_id`, `match_datetime`, `pitch_length_m`, `pitch_width_m`

### `teams`

`match_id`, `team_id`, `team_name`, `team_code`, `home_away` (optional)

### `players`

`match_id`, `player_id`, `team_id`, `player_name` (optional), `shirt_number`
(optional), `position`, `position_group`, `is_goalkeeper`

### `team_period_directions`

`match_id`, `period`, `team_id`, `attacking_x_sign`

`attacking_x_sign` must be `+1` or `-1`, such that `tactical_x = native_x *
attacking_x_sign` always increases toward the opponent goal.  This is more
portable than a home-team-only side field.

### `tracking_frames`

`match_id`, `frame_id`, `period`, `elapsed_seconds`, `sample_rate_hz`

### `player_positions`

`match_id`, `frame_id`, `period`, `player_id`, `team_id`, `x_m`, `y_m`,
`is_observed`

### `ball_positions`

`match_id`, `frame_id`, `period`, `x_m`, `y_m`, `is_observed`

### `possession_phase_intervals`

`match_id`, `period`, `frame_start`, `frame_end_exclusive`,
`possession_team_id`, `attacking_phase_type` (nullable),
`defending_phase_type` (nullable), `leads_to_shot` (nullable),
`leads_to_goal` (nullable), `phase_provider`

### `events`

`match_id`, `event_id`, `period`, `team_id`, `player_id` (nullable),
`event_type`, `end_type`, `frame_start` (nullable), `frame_end` (nullable),
`elapsed_start_s` (nullable), `elapsed_end_s` (nullable), `is_shot`, and an
`attributes` object for provider-specific qualifiers.

An adapter must validate unique `(match_id, frame_id, player_id)` rows, one
ball row per `(match_id, frame_id)`, player-team membership, pitch bounds,
direction coverage, and period agreement across tracking, phases, and events.

## Portability and data gaps

| Capability | Full tracking provider such as Metrica | StatsBomb event + 360 snapshots | SkillCorner dependency |
| --- | --- | --- | --- |
| Team shape, lines, local defender distances, ball-to-goal route | Reproducible when player roles, ball, direction, and synchronized frames exist | Reproducible only at available 360 event snapshots; not continuously | None beyond current coordinate/roster layout |
| Passing-lane clearance and open options | Reproducible frame-by-frame with all players and ball | Reproducible only for a snapshot with ball/player locations; coverage is event-dependent | None beyond supplied tracking completeness |
| Five-second trajectories and matched controls | Reproducible if continuous tracking/event clock supports it | Not reproducible from 360 alone: snapshots do not supply a continuous five-second trajectory | Current 10 Hz convention must become provider sampling-rate metadata |
| Shot identification and generic event sequences | Reproducible if events contain shots, times, teams, and periods | Reproducible from events; 360 can enrich selected frames | SkillCorner's `player_possession` plus `end_type=shot` rule is not portable verbatim |
| Carry / quick-pass / high-pass descriptors | Only where equivalent event qualifiers exist | Carry/pass can often be mapped where supplied; exact quick/high semantics require a documented mapping | Exact Dynamic Events flags and their definitions |
| Tactical phase labels (`finish`, `quick_break`, `low_block`, etc.) | Not directly available unless independently labelled | Not directly available; a new classifier/rule set would be needed | SkillCorner phases taxonomy |
| Possession lead-to-shot / lead-to-goal flags | Can be derived under an explicitly chosen possession definition | Can be derived from event possessions, but may differ | SkillCorner supplied interval outcome flags |

Consequently, the provider-independent product core is **geometry on a
time-synchronised tracking frame**.  SkillCorner phase labels and Dynamic
Events descriptors should be retained as provenance-tagged enrichment, rather
than treated as universal ground truth or silently mapped to another vendor's
labels.

## Skipped SkillCorner matches and recovery ceiling

All ten local match directories have the required source files.  Four are
excluded by strict phase/tracking period validation, not by missing data.  The
numbers below are an upper-bound recovery estimate: they count raw
`player_possession -> shot` events and supplied possession-phase intervals
whose global frame range intersects tracking.  They are **not** a promise that
every candidate will pass the later five-second tracking, phase, and matched-
control filters.

| Match ID | Phase intervals | Candidate shot events | Phase/tracking mismatching frame-pairs | Recovery if a lossless period reconciliation is proven |
| ---: | ---: | ---: | ---: | --- |
| 1886347 | 454 | 23 | 69 | up to 454 compact defending intervals; up to 23 shot candidates |
| 1899585 | 460 | 22 | 11 | up to 460 compact defending intervals; up to 22 shot candidates |
| 1953632 | 431 | 15 | 67 | up to 431 compact defending intervals; up to 15 shot candidates |
| 1996435 | 448 | 29 | 74 | up to 448 compact defending intervals; up to 29 shot candidates |
| **Total** | **1,793** | **89** | **221** | **up to 1,793 intervals and 89 shot candidates** |

For all 89 candidate shots, a raw tracking row and a global-frame phase
interval exist.  The blocker is period disagreement on some phase/tracking
frame pairs, including boundary-adjacent cases; the current pipeline is right
to keep them excluded until a deterministic, lossless convention is proven.
No remapping is applied by this report.

## Readiness decision

The geometry feature set is ready for an adapter only after a source can meet
the core canonical tracking contract.  A provider with sparse freeze frames
can support a separately labelled snapshot-geometry product, but must not be
mixed with continuous 5-second trajectory estimates.  Provider-specific phase
and event fields should enter through explicit mapping tables and be reported
with their source taxonomy.
