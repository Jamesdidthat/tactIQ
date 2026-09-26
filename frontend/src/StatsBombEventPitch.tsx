import type { MomentSequenceEvent, SnapshotPlayer } from "./types";

const point = (coordinates: [number, number] | null) => coordinates ? { x: coordinates[0], y: coordinates[1] } : null;

export function StatsBombEventPitch({ events, snapshotPlayers = [] }: { events: MomentSequenceEvent[]; snapshotPlayers?: SnapshotPlayer[] }) {
  const renderable = events.filter(event => event.pitch_renderable && event.start_coordinates);
  return <figure className="event-pitch-figure">
    <svg className="event-pitch" viewBox="-3 -3 126 86" role="img" aria-label="StatsBomb event sequence on native 120 by 80 coordinates">
      <defs><marker id="event-arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4 Z" fill="currentColor"/></marker></defs>
      <rect x="0" y="0" width="120" height="80" className="pitch-surface"/>
      <path d="M60 0V80 M102 18V62H120 M0 18H18V62H0" className="pitch-line"/>
      <path d="M80 0V80" className="pitch-line final-third-boundary"/>
      <circle cx="60" cy="40" r="9.15" className="pitch-line"/><circle cx="60" cy="40" r=".7" className="pitch-fill"/>
      {snapshotPlayers.map(player => <g key={`snapshot-${player.snapshot_player_index}`} className={`snapshot-player ${player.affiliation} ${player.actor ? "actor" : ""}`}>
        <circle cx={player.location_x} cy={player.location_y} r={player.actor ? 2.1 : 1.55}/>
        {player.keeper && <text x={player.location_x} y={player.location_y + .8}>K</text>}
      </g>)}
      {renderable.map((event, index) => {
        const start = point(event.start_coordinates)!;
        const end = point(event.end_coordinates);
        const className = `event-mark event-${event.event_type.toLowerCase().replaceAll(" ", "-").replace("*", "")} ${event.is_focal ? "focal" : ""}`;
        return <g key={event.event_id} className={className}>
          {event.is_focal && <circle cx={start.x} cy={start.y} r="3.2" className="focal-halo"/>}
          {event.event_type === "Pass" && end && <line x1={start.x} y1={start.y} x2={end.x} y2={end.y} markerEnd="url(#event-arrow)"/>}
          {event.event_type === "Carry" && end && <path d={`M${start.x} ${start.y} L${end.x} ${end.y}`} className="carry-path"/>}
          {event.event_type === "Shot" && <circle cx={start.x} cy={start.y} r="1.8" className="shot-marker"/>}
          {event.event_type === "Interception" && <path d={`M${start.x} ${start.y - 2} L${start.x + 2} ${start.y} L${start.x} ${start.y + 2} L${start.x - 2} ${start.y} Z`} className="regain-marker"/>}
          {event.event_type === "Ball Recovery" && <rect x={start.x - 1.5} y={start.y - 1.5} width="3" height="3" className="regain-marker"/>}
          <text x={start.x + 1.8} y={start.y - 1.8}>{index + 1}</text>
        </g>;
      })}
    </svg>
    <figcaption>Native StatsBomb 120×80 coordinates. Dashed: final-third boundary. Blue/white markers are event-linked 360 teammates/opponents when available; they are one partial snapshot and are never interpolated.</figcaption>
  </figure>;
}
