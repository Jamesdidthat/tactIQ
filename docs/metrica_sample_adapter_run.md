# Metrica Sample Game 1: provider-independent geometry run

The minimal adapter converts Metrica's public Sample Game 1 home/away tracking
CSVs into the canonical `matches`, `teams`, `player_positions`, and
`ball_positions` logical tables.  It does not convert the companion event CSV
into phases or Dynamic Events.

## Coordinate and identity decisions

Metrica normalized source coordinates are converted to centred metres:

`x_m = (source_x - 0.5) * 105`

`y_m = (0.5 - source_y) * 68`

The y inversion changes the top-down source convention into the native pitch
convention used by the geometry engine.  The public sample has no supplied
roster positions or goalkeeper flags.  The demonstration uses an explicit,
replaceable Sample Game 1 role map solely to exercise line metrics; its
provenance is recorded as `sample_game_1_demonstration_assumption` and it is
not tactical ground truth.  Home attacking direction is configured as
left-to-right in period 1 and right-to-left in period 2.

## Executed output

The source's 25 Hz tracking was converted with `frame_stride=5`, yielding a
declared 5 Hz canonical view.  The whole match was adapted, then the full
provider-independent stack was executed over frames 1001–2501 (301 sampled
frames, about 60 seconds): pitch visualization, Team Shape, defensive line
structure, local defensive context, and ball-to-goal/passing-lane geometry.

| Invariant / coverage check | Result |
| --- | ---: |
| Canonical player rows | 638,046 |
| Canonical frame rows | 29,002 |
| Observed ball frames | 17,654 |
| Duplicate player-frame rows | 0 |
| Duplicate ball-frame rows | 0 |
| Window Team Shape team-frames | 602 |
| Negative Team Shape spans | 0 |
| Complete mapped line-structure team-frames | 602 |
| Team-frames with observed ball in local context | 236 |
| Negative ball-to-goal distances | 0 |
| Invalid observed ball-to-goal angles | 0 |
| Passing-lane attacker rows retained | 196 |

The pitch output is available at
[metrica_sample_game_1_frame_1001.png](C:\Users\HP\tactIQ\artifacts\metrica_sample_game_1_frame_1001.png).

## Comparison with the SkillCorner pipeline

The following are provider-independent invariants and behaved consistently:

| Invariant | SkillCorner pipeline | Metrica adapter result |
| --- | --- | --- |
| Centred metres, x as pitch length / y as pitch width | Required | Converted explicitly from normalized top-down coordinates |
| One player position per player-frame | Required | 0 duplicates |
| At most one ball position per frame | Required | 0 duplicates |
| Missing ball remains missing | Required | 11,348 sampled frames remain unavailable; no imputation |
| Native Team Shape spans non-negative | Required | 0 invalid spans |
| Goal geometry evaluated only with a ball | Required | All observed distances/angles valid |
| Attack-normalised direction per period | Metadata-driven | Configured adapter direction; not supplied as a standalone source field |

The two important non-parities are intentional: Metrica's public sample lacks
the verified role metadata used by SkillCorner line mapping, and it has no
SkillCorner phase taxonomy or Dynamic Events semantics.  It must therefore not
enter phase-conditioned or shot/control trajectory analysis until separate,
provider-specific mappings are designed and validated.

Some Metrica observations sit slightly outside the nominal 105 x 68 m pitch.
The adapter preserves them and validates them against a documented 6 m
tolerance instead of clipping coordinates.  This protects source fidelity and
makes any future provider-specific cleaning decision explicit.
