import { useEffect, useMemo, useState } from "react";
import { analysisApi } from "./api";
import type { FootballShapeConcept, FootballShapeProfile, PitchClipResponse, PitchFrameResponse, ShapeFrameReference } from "./types";

const footballPhase = (value: string | null) => value ? value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()) : "All tracked play";
const providerName = (provider: string | null) => provider === "skillcorner_open_data" ? "SkillCorner" : (provider ?? "Tracking provider");

export function ShapePitch({ frame, teamId, highlight }: { frame: PitchFrameResponse; teamId: string | number; highlight: ShapeFrameReference["highlight"] }) {
  const length = frame.pitch.length_m;
  const width = frame.pitch.width_m;
  const selected = frame.players.filter(player => String(player.team_id) === String(teamId));
  const others = frame.players.filter(player => String(player.team_id) !== String(teamId));
  const sx = (x: number) => x + length / 2;
  const sy = (y: number) => width / 2 - y;
  const outfield = selected.filter(player => !String(player.position ?? "").toLowerCase().includes("goalkeeper"));
  const defenders = outfield.filter(player => /back|defender/i.test(String(player.position_group ?? player.position ?? "")));
  const midfielders = outfield.filter(player => /midfield/i.test(String(player.position_group ?? player.position ?? "")));
  const median = (values: number[]) => {
    const ordered = [...values].sort((a, b) => a - b);
    if (!ordered.length) return null;
    const middle = Math.floor(ordered.length / 2);
    return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
  };
  const xs = outfield.map(player => player.x);
  const ys = outfield.map(player => player.y);
  const defenceX = median(defenders.map(player => player.x));
  const midfieldX = median(midfielders.map(player => player.x));
  const widthX = median(xs) ?? 0;
  return <figure className="shape-pitch-figure">
    <svg className="shape-pitch" viewBox={`-2 -2 ${length + 4} ${width + 4}`} role="img" aria-label={`Observed tracking frame ${frame.frame}`}>
      <rect x="0" y="0" width={length} height={width} className="shape-pitch-grass" />
      <path d={`M ${length / 2} 0 V ${width} M 0 13.84 H 16.5 V ${width - 13.84} H 0 M ${length} 13.84 H ${length - 16.5} V ${width - 13.84} H ${length}`} className="shape-pitch-marking" />
      <circle cx={length / 2} cy={width / 2} r="9.15" className="shape-pitch-marking" />
      {highlight === "width" && ys.length > 1 && <g className="shape-highlight"><line x1={sx(widthX)} y1={sy(Math.min(...ys))} x2={sx(widthX)} y2={sy(Math.max(...ys))} /><text x={sx(widthX) + 1.5} y={sy(Math.max(...ys)) + 2}>team width</text></g>}
      {highlight === "length" && xs.length > 1 && <g className="shape-highlight"><line x1={sx(Math.min(...xs))} y1={sy(0)} x2={sx(Math.max(...xs))} y2={sy(0)} /><text x={sx(Math.min(...xs))} y={sy(0) - 2}>back-to-front shape</text></g>}
      {highlight === "team_position" && xs.length > 1 && <g className="shape-highlight"><line x1={sx(median(xs) ?? 0)} y1="3" x2={sx(median(xs) ?? 0)} y2={width - 3} /><text x={sx(median(xs) ?? 0) + 1} y="7">team position</text></g>}
      {(highlight === "defensive_line" || highlight === "defence_midfield_gap") && defenceX != null && <g className="shape-line"><line x1={sx(defenceX)} y1="3" x2={sx(defenceX)} y2={width - 3} /><text x={sx(defenceX) + 1} y="7">defence</text></g>}
      {(highlight === "midfield_line" || highlight === "defence_midfield_gap") && midfieldX != null && <g className="shape-line midfield"><line x1={sx(midfieldX)} y1="3" x2={sx(midfieldX)} y2={width - 3} /><text x={sx(midfieldX) + 1} y={width - 4}>midfield</text></g>}
      {highlight === "defence_midfield_gap" && defenceX != null && midfieldX != null && <g className="shape-highlight"><line x1={sx(defenceX)} y1={sy(0)} x2={sx(midfieldX)} y2={sy(0)} /></g>}
      {others.map(player => <circle key={`other-${player.player_id}`} cx={sx(player.x)} cy={sy(player.y)} r="1.15" className={`shape-player opponent ${player.is_detected === false ? "extrapolated" : ""}`} />)}
      {selected.map(player => <g key={`team-${player.player_id}`}><circle cx={sx(player.x)} cy={sy(player.y)} r="1.45" className={`shape-player selected ${player.is_detected === false ? "extrapolated" : ""}`} /><text x={sx(player.x)} y={sy(player.y) + .55} className="shape-shirt">{player.player_number ?? ""}</text></g>)}
      {frame.ball?.is_observed && frame.ball.x != null && frame.ball.y != null && <circle cx={sx(frame.ball.x)} cy={sy(frame.ball.y)} r=".75" className="shape-ball" />}
    </svg>
    <figcaption>Observed match frame · Period {frame.period} · {frame.timestamp ?? `${frame.elapsed_seconds.toFixed(1)}s`}</figcaption>
  </figure>;
}

export function RealTrackingClip({ reference, teamId }: { reference: ShapeFrameReference; teamId: string | number }) {
  const [frame, setFrame] = useState<PitchFrameResponse | null>(null);
  const [clip, setClip] = useState<PitchClipResponse | null>(null);
  const [clipIndex, setClipIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loadingClip, setLoadingClip] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setFrame(null); setClip(null); setPlaying(false); setError(null);
    analysisApi.rawFrame(reference.match_id, reference.frame, reference.period)
      .then(result => { if (active) setFrame(result); })
      .catch(reason => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [reference.match_id, reference.frame, reference.period]);
  useEffect(() => {
    if (!playing || !clip) return;
    const playbackRate = Math.max(1, (clip.playback_frame_rate_hz ?? 10) * speed);
    const timer = window.setInterval(() => setClipIndex(index => {
      if (index >= clip.frames.length - 1) { setPlaying(false); return index; }
      return index + 1;
    }), 1000 / playbackRate);
    return () => window.clearInterval(timer);
  }, [playing, clip, speed]);
  const loadClip = () => {
    if (clip) {
      if (clipIndex >= clip.frames.length - 1) setClipIndex(0);
      setPlaying(value => !value);
      return;
    }
    setLoadingClip(true); setError(null);
    analysisApi.rawClip(reference.match_id, reference.frame, reference.period, reference.clip_before_seconds, reference.clip_after_seconds)
      .then(result => { setClip(result); setClipIndex(0); setPlaying(true); })
      .catch(reason => setError(String(reason)))
      .finally(() => setLoadingClip(false));
  };
  if (error) return <p className="shape-frame-state">The observed tracking could not be loaded.</p>;
  if (!frame) return <p className="shape-frame-state">Loading observed shape…</p>;
  const visibleFrame = clip?.frames[clipIndex] ?? frame;
  const hasExtrapolated = visibleFrame.players.some(player => player.is_detected === false);
  return <div className="tracking-clip">
    <div className="tracking-clip-heading"><span>Full-team tracking · both teams</span><small>{clip ? `${clip.actual_duration_seconds.toFixed(1)}-second evidence window` : "Representative frame"}</small></div>
    <ShapePitch frame={visibleFrame} teamId={teamId} highlight={reference.highlight} />
    <div className="tracking-legend"><span><i className="team-dot" />Selected team</span><span><i className="opponent-dot" />Opposition</span><span><i className="ball-dot" />Ball</span>{hasExtrapolated && <span><i className="estimated-dot" />Extrapolated by source</span>}</div>
    <div className="tracking-controls">
      <button type="button" onClick={loadClip} disabled={loadingClip}>{loadingClip ? "Loading movement…" : playing ? "Pause" : clip ? "Play" : `Watch ${reference.clip_before_seconds + reference.clip_after_seconds}s evidence window`}</button>
      {clip && <>
        <button type="button" onClick={() => { setPlaying(false); setClipIndex(Math.max(0, clipIndex - 1)); }} aria-label="Previous tracking frame">−</button>
        <input aria-label="Tracking clip position" type="range" min="0" max={clip.frames.length - 1} value={clipIndex} onChange={event => { setPlaying(false); setClipIndex(Number(event.target.value)); }} />
        <button type="button" onClick={() => { setPlaying(false); setClipIndex(Math.min(clip.frames.length - 1, clipIndex + 1)); }} aria-label="Next tracking frame">+</button>
        <button type="button" className="tracking-speed" onClick={() => setSpeed(value => value === 1 ? .5 : value === .5 ? 2 : 1)}>{speed}×</button>
        <span className={visibleFrame.frame === reference.frame ? "focus active" : "focus"}>{visibleFrame.frame === reference.frame ? "Evidence moment" : `${clipIndex + 1}/${clip.frames.length}`}</span>
      </>}
    </div>
    <p className="tracking-clip-note">{reference.clip_reason} Real player and ball positions only; source-extrapolated players are outlined.</p>
  </div>;
}

function ShapeConceptCard({ concept, teamId }: { concept: FootballShapeConcept; teamId: string | number }) {
  const [selected, setSelected] = useState(0);
  const frame = concept.representative_frames[selected];
  return <article className="shape-concept-card" id={`shape-${concept.concept_id}`}>
    <span className="shape-source">Tracking-derived</span>
    <h3>{concept.headline}</h3>
    <p>{concept.explanation}</p>
    <div className="football-looks"><strong>What this looks like</strong><span>{concept.what_this_looks_like}</span></div>
    {concept.representative_frames.length > 0 && <div className="shape-examples">
      {concept.representative_frames.length > 1 && <div className="shape-frame-tabs">{concept.representative_frames.map((item, index) => <button className={selected === index ? "active" : ""} key={`${item.match_id}-${item.frame}`} onClick={() => setSelected(index)}>{item.label} {index + 1}</button>)}</div>}
      {frame && <RealTrackingClip reference={frame} teamId={teamId} />}
    </div>}
    <details className="shape-evidence"><summary>Why TactIQ says this</summary>
      {concept.evidence.map(item => <section key={`${item.metric}-${item.possession_status}-${item.tactical_phase}`}>
        <strong>{item.metric_label}</strong><span>{item.median_metres.toFixed(1)} m</span>
        <small>{footballPhase(item.possession_status)} · {footballPhase(item.tactical_phase)} · usual range {item.q25_metres.toFixed(1)}–{item.q75_metres.toFixed(1)} m</small>
        <small>{item.contributing_matches} match{item.contributing_matches === 1 ? "" : "es"} · {item.tracked_frame_count.toLocaleString()} observed frames</small>
        <details><summary>Tracking provenance</summary><p>{providerName(item.provider)} · capabilities: {item.required_capabilities.join(", ")}</p></details>
      </section>)}
      {concept.limitations.map(item => <p className="football-limitation" key={item}>{item}</p>)}
    </details>
  </article>;
}

function ConceptSection({ title, intro, concepts, teamId, empty }: { title: string; intro: string; concepts: FootballShapeConcept[]; teamId: string | number; empty?: string }) {
  return <section className="football-style-section shape-section"><header><div><small>Tracking-derived structure</small><h2>{title}</h2></div><p>{intro}</p></header>
    {concepts.length ? <div className="shape-concept-grid">{concepts.map(item => <ShapeConceptCard key={item.concept_id} concept={item} teamId={teamId} />)}</div> : <p className="football-empty">{empty ?? "This concept is not supported by the available tracking evidence."}</p>}
  </section>;
}

export function FootballShapeProfileView({ profile, technicalHref }: { profile: FootballShapeProfile; technicalHref: string }) {
  const allConcepts = useMemo(() => [...profile.with_ball, ...profile.without_ball, ...profile.transitions], [profile]);
  if (!profile.available) return <main className="shell football-shape-profile"><header className="football-profile-header"><div><p className="eyebrow">TactIQ / Team Shape</p><h1>{profile.team_name}</h1></div></header><section className="shape-unavailable"><h2>Detailed team shape requires tracking data</h2><p>TactIQ will not estimate width, defensive height or compactness from event locations.</p></section></main>;
  return <main className="shell football-shape-profile">
    <header className="football-profile-header"><div><p className="eyebrow">TactIQ / Team Shape & Structure</p><h1>{profile.team_name}</h1><p>How their shape looks with and without the ball.</p></div><div><strong>Tracking-derived structure</strong><small>{providerName(profile.provider)} · observed player positions</small><a href={technicalHref}>Open technical evidence</a></div></header>
    <section className="shape-intro"><small>Observed structure</small><h2>{allConcepts.length} supported football patterns from real tracking frames.</h2><p>These descriptions explain where the players were positioned. They do not infer intention or estimate shape from event data.</p></section>
    <ConceptSection title="With the ball" intro="How the team occupies the pitch while attacks develop." concepts={profile.with_ball} teamId={profile.team_id} />
    <ConceptSection title="Without the ball" intro="How the team's lines are positioned while defending." concepts={profile.without_ball} teamId={profile.team_id} />
    <ConceptSection title="Transitions" intro="How the lines move immediately after possession changes." concepts={profile.transitions} teamId={profile.team_id} empty="Transition movement is not shown until a validated possession-change timing rule is available for this tracking sample." />
    <section className="football-profile-notes"><div><small>Current limits</small>{profile.limitations.map(item => <p key={item}>{item}</p>)}</div><details><summary>Unsupported shape concepts</summary><p>{profile.unsupported_concepts.join(" · ")}</p></details></section>
  </main>;
}
