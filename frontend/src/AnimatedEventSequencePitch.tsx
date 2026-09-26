import { StatsBombEventPitch } from "./StatsBombEventPitch";
import type { MomentSequenceEvent, RepresentativeMomentDetail } from "./types";

function clock(event: MomentSequenceEvent) {
  return `${event.minute}:${String(event.second).padStart(2, "0")}`;
}

function RecordedActionTimeline({ events }: { events: MomentSequenceEvent[] }) {
  return <ol className="recorded-action-timeline">{events.map(event => <li className={event.is_focal ? "focal" : ""} key={event.event_id}>
    <time>{clock(event)}</time><div><strong>{event.event_type}{event.event_subtype ? ` · ${event.event_subtype}` : ""}</strong><span>{event.team_name ?? "Team unavailable"}{event.outcome ? ` · ${event.outcome}` : ""}</span></div>
  </li>)}</ol>;
}

/** Event-only data is never animated as though it contains team movement. */
export function AnimatedEventSequencePitch({ detail }: { detail: RepresentativeMomentDetail }) {
  const context = detail.moment_360_context;
  const events = detail.sequence_events;
  if (!events.length) return <div className="visual-sequence-empty">No recorded action sequence is available for this example.</div>;

  if (!context.available || context.spatial_context_mode === "event_only") {
    return <section className="spatial-example-unavailable">
      <div className="spatial-example-message"><span aria-hidden="true">◎</span><div><strong>Whole-team positions were not recorded</strong><p>This source records the actions on the ball, but not where both complete teams were standing. TactIQ will not invent player positions or turn the ball path into a team-shape animation.</p></div></div>
      <RecordedActionTimeline events={events}/>
      <footer><span>Event-only evidence</span><a href="/#analysis-library">Choose a tracking-backed Team Shape profile →</a></footer>
    </section>;
  }

  return <section className="partial-spatial-example">
    <header><strong>Partial 360 snapshot</strong><span>{context.snapshot_players.length} visible players · one instant only</span></header>
    <StatsBombEventPitch events={[]} snapshotPlayers={context.snapshot_players}/>
    <p>{context.evidence_wording} This is not a complete-team view and no movement is interpolated.</p>
    <RecordedActionTimeline events={events}/>
  </section>;
}
