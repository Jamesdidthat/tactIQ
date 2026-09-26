# Representative Moment Detail

The detail layer expands one historical `RepresentativeMoment` into a bounded,
ordered event sequence and a native StatsBomb pitch view. It remains an event
view—not reconstructed tracking.

## Sequence rule

When the focal event has a possession ID, context is restricted to that exact
match, period, and possession. The response includes up to six preceding relevant
events, the focal event, and at most one following relevant event. It never
crosses a known possession boundary.

When possession ID is unavailable, the fallback is explicitly labelled
`bounded_time_window` and uses only the same period, ten seconds before, and
three seconds after the focal event. All limits are configurable in the analysis
function.

Events remain in provider event-index order and preserve their source UUIDs.
Missing coordinates remain `null`; those events appear in the timeline but are
not plotted.

## Detail contract

The response provides:

- focal event and ordered context events;
- event/possession team identity and player ID where supplied;
- start/end native coordinates;
- event type, provider subtype, and outcome;
- shot xG;
- verified score state with its explicit team perspective;
- StatsBomb play pattern only when present, labelled as event-derived rather
  than a tracking-derived tactical phase;
- `statsbomb_120x80` provenance and video availability;
- limitations forbidding inference about player positions, defensive shape,
  passing lanes, pressure structure, or off-ball movement.

## Pitch component

The reusable SVG component draws only supplied event coordinates:

- passes as arrows;
- carries as paths;
- shots as circular markers;
- interceptions as diamonds and ball recoveries as squares;
- the x=80 final-third boundary and x=102, y=18–62 penalty-area boundary;
- a highlighted focal event and ordered event numbers.

StatsBomb 360 is not read by this component and is never represented as
continuous tracking.

## API

`GET /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority_id}/moments/{event_id}`

The frontend opens this endpoint when an analyst selects `Open moment detail`.
It displays the pitch, event timeline, deterministic description, possession and
play-pattern context, provenance, limitations, and video status.
