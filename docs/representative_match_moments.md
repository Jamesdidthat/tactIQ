# Representative Match Moments

Representative Match Moments provide concrete historical event examples for a
deterministic pre-match review priority. They illustrate the source definition;
they do not explain why a matchup contrast exists and are not tactical advice.

## Contract

Each `RepresentativeMoment` contains match and team identity, opponent, date,
period, minute/second, stable provider event ID, event type, metric/family,
deterministic description, relevant xG and coordinate values, verified score
state with its team perspective, provider provenance, video availability, the
evidence side, and a deterministic selection reason.

StatsBomb Open Data moments retain `statsbomb_120x80` coordinates. They are not
presented as metres. Video is explicitly reported as unavailable; event IDs are
preserved for a future licensed-video integration.

## Initial query mappings

| Metric | Historical event query |
|---|---|
| Penalty-area entries | Completed passes or carries starting outside and ending inside x>=102, y=18–62 |
| Final-third entries | Completed passes or carries crossing from x<80 to x>=80 |
| Shots | StatsBomb Shot events |
| xG | Shot events, prioritizing the highest-xG shot from distinct matches |
| xG per shot | Shot events near lower quartile, median, upper quartile, and maximum shot xG |
| Interceptions | Interception events excluding configured failed outcomes |
| High regains | Successful Ball Recovery or Interception at x>=80 |
| Explicit counter attacks | Shot events with `play_pattern=From Counter` |
| Set-play shots | Existing set-play play-pattern or shot-type classification |

General comparisons draw examples from both team histories. Directional
interactions draw attacking-production examples from the attacking team's
season and conceded examples from opposition events in the defending team's
historical season. They never query a future matchup.

Selection is deterministic and match-diverse. Ordinary count metrics use match
examples around lower-quartile, typical, upper-quartile, and high match values.
xG uses high-value shots across distinct matches. Shot quality uses several
parts of the season shot-xG distribution. Score-state variety is preferred where
available and score state is omitted unless the event goal timeline reconciles
with the final score.

## API

`GET /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority_id}/moments`

The response includes `supported`, `representative_moments`, `query_mappings`,
and limitations. Unsupported metrics return a clear empty state rather than a
substitute event type.

The frontend loads moments only when the analyst opens `Review moments`. It
shows match, opponent, date/time, description, evidence values, selection reason,
score-state perspective, and expanded event provenance.
