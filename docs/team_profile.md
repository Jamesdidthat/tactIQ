# Provider-independent Team Profile

`build_team_profile` accepts canonical match bundles plus an explicit
`TeamProfileIdentity`. The identity maps the product-level team to its ID in
each provider, preventing coincidentally equal provider IDs from being treated
as the same club.

The result preserves:

- included and excluded matches with reasons;
- capability coverage across included matches;
- observed periods and elapsed-time-derived sample duration;
- one value per match, metric, and tactical context;
- median, Q25, and Q75 across those match-level values;
- each match's signed deviation from its own provider/capability baseline;
- finding families recurring in at least two matches.

Frames are never concatenated or pooled across matches. Aggregates are grouped
by provider and the capabilities required by that metric, so incompatible
provider/capability samples cannot silently share a baseline.

Metric families currently include:

- full-team shape with continuous tracking;
- outfield and phase-specific shape with verified roles, and tactical phases
  for phase-specific values;
- attack-normalised defensive-line depth and line spacing with verified roles
  and attacking direction;
- shots for and conceded shots with canonical events;
- recurring deterministic finding families from supplied or freshly generated
  `MatchAnalysisResult`s.

All outputs remain descriptive. Deviation labels such as `wider`, `deeper`, or
`more_stretched` compare a match only with the team's own median across
compatible contributing matches; they do not imply tactical quality, cause,
or a recommended response.
