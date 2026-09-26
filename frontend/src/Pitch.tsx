import type { PitchFrameResponse } from "./types";

export function Pitch({ frame }: { frame: PitchFrameResponse | null }) {
  if (!frame) return <div className="pitch-empty">Select a representative moment to inspect its canonical pitch frame.</div>;
  const { length_m: length, width_m: width } = frame.pitch;
  const point = (x: number, y: number) => ({ left: `${((x + length / 2) / length) * 100}%`, top: `${((width / 2 - y) / width) * 100}%` });
  return <section className="pitch-panel"><div className="pitch-meta">Frame {frame.frame} · Period {frame.period} · {frame.timestamp ?? `${frame.elapsed_seconds.toFixed(1)}s`}</div><div className="pitch">
    <div className="halfway" />
    {frame.players.map(player => <span key={`${player.team_id}-${player.player_id}`} title={`${player.team_acronym ?? player.team_id} · ${player.position ?? "Unknown"} · Player ID: ${player.player_id}${player.player_number == null ? ' · Shirt number unavailable' : ''}`} className={`marker ${player.team_acronym === "MEL" ? "home" : "away"}`} style={point(player.x, player.y)}>{player.player_number ?? String(player.player_id).replace("Player", "")}</span>)}
    {frame.ball?.is_observed && <span className="ball" style={point(frame.ball.x ?? 0, frame.ball.y ?? 0)} />}
  </div><div className="pitch-key"><span><i className="key-dot home" /> Home</span><span><i className="key-dot away" /> Away</span><span><i className="key-ball" /> Ball</span></div></section>;
}
