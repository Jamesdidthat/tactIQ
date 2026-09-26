import { useEffect, useMemo, useState } from "react";
import { opponentComparisonApi } from "./api";
import { metricLabel } from "./presentation";
import { StatsBombEventPitch } from "./StatsBombEventPitch";
import type {
  EventMetricUnit, MatchupInteraction, MatchupInteractionFinding,
  OpponentComparisonFinding, OpponentComparisonSummary, OpponentMetricComparison,
  MomentPattern, MomentPatternAssignment, MomentSequenceFeatures, MomentSequencePattern, PreMatchEvidencePack, PreMatchReviewPriority,
  RepresentativeMoment, RepresentativeMomentDetail,
} from "./types";

const fields = ["provider", "team_id", "competition_id", "season_id"] as const;
const familyOrder = ["possession_circulation", "progression", "final_third_access", "penalty_area_access", "shot_volume_xg", "shot_quality", "defensive_activity", "high_regains", "turnover_to_shot_exposure", "explicit_counter_attack_shots"];

const formatValue = (value: number | null, unit: EventMetricUnit) => {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  if (unit === "proportion") return `${(value * 100).toFixed(1)}%`;
  if (unit === "native_120x80_units") return `${value.toFixed(1)} units`;
  if (unit === "count") return value.toFixed(Number.isInteger(value) ? 0 : 1);
  if (unit === "xG" || unit === "xG_per_90") return value.toFixed(2);
  return value.toFixed(1);
};

function SetupForm({ query }: { query: URLSearchParams }) {
  const input = (side: "target" | "opponent", field: typeof fields[number], fallback = "") => (
    <label key={`${side}-${field}`}>{metricLabel(field)}<input name={`${side}_${field}`} defaultValue={query.get(`${side}_${field}`) ?? fallback} required /></label>
  );
  return <main className="shell opponent-setup">
    <header className="profile-header"><div><p className="eyebrow">TactIQ / Pre-match</p><h1>Opponent comparison</h1><p>Compare compatible match-weighted event Team Profiles.</p></div></header>
    <form method="get" action="/opponent-comparison" className="panel comparison-form">
      <section><h2>Target team-season</h2>{fields.map(field => input("target", field, field === "provider" ? "statsbomb_open_data" : ""))}</section>
      <section><h2>Opponent team-season</h2>{fields.map(field => input("opponent", field, field === "provider" ? "statsbomb_open_data" : ""))}</section>
      <button type="submit">Build comparison</button>
    </form>
    <p className="comparison-disclaimer">Only explicitly compatible metrics with adequate match coverage are compared. No match prediction or tactical recommendation is generated.</p>
  </main>;
}

function TeamSeasonCard({ identity, side }: { identity: OpponentComparisonSummary["target"]; side: string }) {
  return <article className="comparison-team-card">
    <small>{side}</small><h2>{identity.team_name}</h2>
    <p>{identity.competition_name ?? `Competition ${identity.competition_id}`} · {identity.season_name ?? `Season ${identity.season_id}`}</p>
    <strong>{identity.analysed_match_count} analysed matches</strong>
    <span>{identity.provider} · {identity.coordinate_system ?? "Coordinate context unavailable"}</span>
  </article>;
}

function MomentDetailView({ priority, moment, target, opponent, onClose }: { priority: PreMatchReviewPriority; moment: RepresentativeMoment; target: string[]; opponent: string[]; onClose: () => void }) {
  const [detail, setDetail] = useState<RepresentativeMomentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDetail(null); setError(null);
    opponentComparisonApi.reviewPriorityMomentDetail(target, opponent, priority.priority_id, moment.event_id)
      .then(response => response.detail ? setDetail(response.detail) : setError(response.limitations.join(" ")))
      .catch(reason => setError(String(reason)));
  }, [priority.priority_id, moment.event_id, target.join("|"), opponent.join("|")]);
  const contextLabel = (mode: RepresentativeMomentDetail["moment_360_context"]["spatial_context_mode"]) => mode === "event_plus_360_snapshot" ? "Event + 360 snapshot" : mode === "continuous_tracking" ? "Continuous tracking" : "Event only";
  return <section className="moment-detail-view">
    <div className="moment-detail-heading"><div><small>Representative moment detail</small><h4>{moment.team_name} vs {moment.opponent_name} · {moment.minute}:{String(moment.second).padStart(2, "0")}</h4></div><button type="button" onClick={onClose}>Close</button></div>
    {error && <p className="profile-warning">Detail unavailable: {error}</p>}
    {!error && !detail && <p className="muted">Loading event sequence…</p>}
    {detail && <>
      <p>{moment.description}</p>
      <div className={`spatial-context-badge ${detail.moment_360_context.spatial_context_mode}`}>{contextLabel(detail.moment_360_context.spatial_context_mode)}</div>
      <StatsBombEventPitch events={detail.sequence_events} snapshotPlayers={detail.moment_360_context.snapshot_players}/>
      {detail.moment_360_context.available && <section className="snapshot-context-panel">
        <div><strong>Partial 360 spatial context</strong><small>{detail.moment_360_context.evidence_wording}</small></div>
        <dl>
          <div><dt>Visible teammates</dt><dd>{detail.moment_360_context.visible_teammate_count}</dd></div>
          <div><dt>Visible opponents</dt><dd>{detail.moment_360_context.visible_opponent_count}</dd></div>
          <div><dt>Nearest opponent</dt><dd>{detail.moment_360_context.nearest_opponent_distance == null ? "Unavailable" : `${detail.moment_360_context.nearest_opponent_distance.toFixed(1)} units`}</dd></div>
          <div><dt>Nearest teammate</dt><dd>{detail.moment_360_context.nearest_teammate_distance == null ? "Unavailable" : `${detail.moment_360_context.nearest_teammate_distance.toFixed(1)} units`}</dd></div>
          <div><dt>Visible width range</dt><dd>{detail.moment_360_context.visible_player_width_range == null ? "Unavailable" : `${detail.moment_360_context.visible_player_width_range.toFixed(1)} units`}</dd></div>
          <div><dt>Visible depth range</dt><dd>{detail.moment_360_context.visible_player_depth_range == null ? "Unavailable" : `${detail.moment_360_context.visible_player_depth_range.toFixed(1)} units`}</dd></div>
        </dl>
        <details><summary>360 definitions and visibility limits</summary>
          <p>Opponents within 5 / 10 / 15 units: {["5.0", "10.0", "15.0"].map(radius => detail.moment_360_context.opponents_within_radius[radius] ?? 0).join(" / ")}.</p>
          <p>Teammates within 5 / 10 / 15 units, excluding the actor: {["5.0", "10.0", "15.0"].map(radius => detail.moment_360_context.teammates_within_radius[radius] ?? 0).join(" / ")}.</p>
          <p>Visible players ahead / behind the event location: {detail.moment_360_context.visible_players_ahead_of_event ?? "Unavailable"} / {detail.moment_360_context.visible_players_behind_event ?? "Unavailable"}.</p>
          <p>Visible teammates / opponents inside the attacking penalty area: {detail.moment_360_context.visible_teammates_in_penalty_area ?? "Unavailable"} / {detail.moment_360_context.visible_opponents_in_penalty_area ?? "Unavailable"}.</p>
          <p>Event inside visible-player hull: {detail.moment_360_context.event_location_inside_visible_player_hull == null ? "Unavailable" : detail.moment_360_context.event_location_inside_visible_player_hull ? "Yes" : "No"}. Event inside provider visible area: {detail.moment_360_context.event_location_inside_provider_visible_area == null ? "Unavailable" : detail.moment_360_context.event_location_inside_provider_visible_area ? "Yes" : "No"}.</p>
          {detail.moment_360_context.visibility_limitations.map(item => <p key={item}>{item}</p>)}
        </details>
      </section>}
      <ol className="event-sequence-timeline">{detail.sequence_events.map(event => <li key={event.event_id} className={event.is_focal ? "focal" : ""}>
        <span>{event.minute}:{String(event.second).padStart(2, "0")}</span>
        <div><strong>{event.event_type}{event.event_subtype ? ` · ${event.event_subtype}` : ""}</strong><small>{event.team_name ?? "Team unavailable"}{event.outcome ? ` · ${event.outcome}` : ""}{event.xg != null ? ` · ${event.xg.toFixed(2)} xG` : ""}</small><code>{event.event_id}</code></div>
      </li>)}</ol>
      <div className="moment-detail-context"><p>Possession: {detail.possession_team_name ?? "Unavailable"} · Context: {metricLabel(detail.context_mode)}</p>{detail.phase_context && <p>Event-derived play pattern: {detail.phase_context.label}. {detail.phase_context.interpretation}</p>}<p>Coordinates: {detail.coordinate_system} · {metricLabel(detail.video_availability_status)}</p></div>
      {detail.limitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}
    </>}
  </section>;
}

function ReviewMoments({ priority, target, opponent }: { priority: PreMatchReviewPriority; target: string[]; opponent: string[] }) {
  const [moments, setMoments] = useState<RepresentativeMoment[] | null>(null);
  const [supported, setSupported] = useState(true);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [patterns, setPatterns] = useState<MomentPattern[]>([]);
  const [assignments, setAssignments] = useState<MomentPatternAssignment[]>([]);
  const [patternLimitations, setPatternLimitations] = useState<string[]>([]);
  const [selectedPatternId, setSelectedPatternId] = useState<string | null>(null);
  const [sequenceFeatures, setSequenceFeatures] = useState<MomentSequenceFeatures[]>([]);
  const [sequencePatterns, setSequencePatterns] = useState<MomentSequencePattern[]>([]);
  const [sequenceLimitations, setSequenceLimitations] = useState<string[]>([]);
  const [selectedSequencePatternId, setSelectedSequencePatternId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedMoment, setSelectedMoment] = useState<RepresentativeMoment | null>(null);
  const load = () => {
    if (moments !== null || error) return;
    opponentComparisonApi.reviewPriorityMoments(target, opponent, priority.priority_id)
      .then(response => { setMoments(response.representative_moments); setSupported(response.supported); setLimitations(response.limitations); setPatterns(response.moment_patterns); setAssignments(response.moment_pattern_assignments); setPatternLimitations(response.pattern_limitations); setSequenceFeatures(response.moment_sequence_features); setSequencePatterns(response.moment_sequence_patterns); setSequenceLimitations(response.moment_sequence_limitations); })
      .catch(reason => setError(String(reason)));
  };
  const visibleMoments = moments?.filter(moment =>
    (selectedPatternId === null || assignments.some(assignment => assignment.event_id === moment.event_id && assignment.pattern_ids.includes(selectedPatternId)))
    && (selectedSequencePatternId === null || sequenceFeatures.some(feature => feature.event_id === moment.event_id && feature.sequence_pattern_id === selectedSequencePatternId))
  ) ?? [];
  return <details className="review-moments" onToggle={event => event.currentTarget.open && load()}>
    <summary>Review moments</summary>
    {error && <p className="profile-warning">Moments unavailable: {error}</p>}
    {!error && moments === null && <p className="muted">Loading historical event moments…</p>}
    {!error && moments !== null && !supported && <p className="muted">No representative-event mapping is available for this metric yet.</p>}
    {!error && moments !== null && supported && !moments.length && <p className="muted">No qualifying historical events were found.</p>}
    {moments && moments.length > 0 && patterns.length > 0 && <section className="moment-pattern-summary" aria-label="Representative moment patterns">
      <div><strong>Patterns in retrieved moments</strong><small>Explicit event-only labels; one moment may have more than one.</small></div>
      <div className="moment-pattern-filters">
        <button type="button" className={selectedPatternId === null ? "selected" : ""} onClick={() => setSelectedPatternId(null)}>All · {moments.length}</button>
        {patterns.map(pattern => <button type="button" key={pattern.pattern_id} title={pattern.deterministic_definition} className={selectedPatternId === pattern.pattern_id ? "selected" : ""} onClick={() => setSelectedPatternId(pattern.pattern_id)}>{pattern.moment_count}/{pattern.eligible_moment_count} {pattern.pattern_name.toLowerCase()}</button>)}
      </div>
      <div className="pattern-context-list">{patterns.map(pattern => <details key={`context-${pattern.pattern_id}`}>
        <summary>{pattern.pattern_name} · {pattern.moment_count}/{pattern.eligible_moment_count} event examples</summary>
        <div className="pattern-context-columns">
          <section><small>Season pattern</small><strong>{pattern.moment_count} event-derived examples</strong><p>{(pattern.share_of_eligible_moments * 100).toFixed(0)}% of the retrieved eligible event sample across {pattern.contributing_matches.length} matches.</p><p>{pattern.deterministic_definition}</p></section>
          <section><small>360-observed context</small><strong>{pattern.context_summary.snapshot_360_subset_count}/{pattern.context_summary.full_event_sample_count} examples · {(pattern.context_summary.snapshot_360_coverage * 100).toFixed(0)}% coverage</strong><p>{pattern.context_summary.scope_statement}</p>
            {pattern.context_summary.spatial_summary_available && <dl>{pattern.context_summary.metric_summaries.map(metric => <div key={metric.metric}><dt>{metric.metric_label}</dt><dd>{metric.median == null ? "Unavailable" : `${metric.median.toFixed(1)} (${metric.q25?.toFixed(1)}–${metric.q75?.toFixed(1)}) ${metric.unit === "native_statsbomb_units" ? "units" : "players"}`}<span>N={metric.sample_count} · {(metric.coverage * 100).toFixed(0)}%</span></dd></div>)}</dl>}
          </section>
        </div>
        <p className="pattern-context-caveat">360 context is subset-only and is not extrapolated to the season or full event sample.</p>
        <details className="pattern-context-provenance"><summary>Scope, capabilities and limitations</summary><p>Event patterns require events. Spatial summaries additionally require exact event-linked 360 snapshots. Continuous tracking is not used.</p>{pattern.context_summary.limitations.map(item => <p key={item}>{item}</p>)}</details>
      </details>)}</div>
    </section>}
    {moments && moments.length > 0 && sequencePatterns.length > 0 && <section className="sequence-pattern-summary" aria-label="Event sequence patterns">
      <div><strong>Event-sequence patterns</strong><small>Transparent grouping from event order, action, coordinates and explicit provider labels.</small></div>
      <div className="sequence-pattern-filters">
        <button type="button" className={selectedSequencePatternId === null ? "selected" : ""} onClick={() => setSelectedSequencePatternId(null)}>All sequences · {moments.length}</button>
        {sequencePatterns.map(pattern => <button type="button" key={pattern.pattern_id} className={selectedSequencePatternId === pattern.pattern_id ? "selected" : ""} onClick={() => setSelectedSequencePatternId(pattern.pattern_id)}>{pattern.count}/{moments.length} {pattern.pattern_label.toLowerCase()}</button>)}
      </div>
      <div className="sequence-pattern-list">{sequencePatterns.map(pattern => <details key={`sequence-${pattern.pattern_id}`}>
        <summary>{pattern.pattern_label} · {pattern.count} example{pattern.count === 1 ? "" : "s"}</summary>
        <p>{(pattern.share_of_retrieved_moments * 100).toFixed(0)}% of retrieved moments · {pattern.contributing_matches.length} contributing match{pattern.contributing_matches.length === 1 ? "" : "es"}.</p>
        <p>Representative event IDs: <code>{pattern.representative_event_ids.join(" · ")}</code></p>
        <dl>{Object.entries(pattern.defining_features).filter(([, value]) => typeof value !== "object").map(([key, value]) => <div key={key}><dt>{metricLabel(key)}</dt><dd>{String(value ?? "Unavailable")}</dd></div>)}</dl>
        {pattern.limitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}
      </details>)}</div>
    </section>}
    {moments && moments.length > 0 && !visibleMoments.length && <p className="muted">No retrieved moments match this pattern.</p>}
    {visibleMoments.length > 0 && <div className="review-moment-list">{visibleMoments.map(moment => <article key={`${moment.evidence_side}-${moment.match_id}-${moment.event_id}`}>
      <div><strong>{moment.team_name} vs {moment.opponent_name}</strong><span>{moment.match_date} · {moment.minute}:{String(moment.second).padStart(2, "0")} · Period {moment.period}</span></div>
      <p>{moment.description}</p>
      <small>{metricLabel(moment.evidence_side)} · {metricLabel(moment.reason_selected)}{moment.score_state_verified && moment.score_state ? ` · ${moment.score_state_team_name} ${metricLabel(moment.score_state).toLowerCase()}` : " · Score state unavailable"}</small>
      <small>{moment.relevant_values.xg != null ? `xG ${moment.relevant_values.xg.toFixed(2)} · ` : ""}{moment.relevant_values.start_coordinates ? `Start ${moment.relevant_values.start_coordinates.join(", ")} · ` : ""}{moment.relevant_values.end_coordinates ? `End ${moment.relevant_values.end_coordinates.join(", ")}` : ""}</small>
      <button type="button" className="moment-detail-button" onClick={() => setSelectedMoment(moment)}>Open moment detail</button>
      <details><summary>Event provenance</summary><p>Event ID: <code>{moment.event_id}</code></p><p>{metricLabel(moment.video_availability_status)}</p></details>
    </article>)}</div>}
    {selectedMoment && <MomentDetailView priority={priority} moment={selectedMoment} target={target} opponent={opponent} onClose={() => setSelectedMoment(null)}/>} 
    {patternLimitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}
    {sequenceLimitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}
    {limitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}
  </details>;
}

export function EvidencePackView({ priority, target, opponent, onClose, initialEventId = null, onMomentChange, closeLabel = "Close" }: { priority: Pick<PreMatchReviewPriority, "priority_id" | "title">; target: string[]; opponent: string[]; onClose: () => void; initialEventId?: string | null; onMomentChange?: (eventId: string | null) => void; closeLabel?: string }) {
  const [pack, setPack] = useState<PreMatchEvidencePack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  useEffect(() => {
    setPack(null); setError(null); setSelectedEventId(null);
    opponentComparisonApi.reviewPriorityEvidencePack(target, opponent, priority.priority_id)
      .then(response => setPack(response.evidence_pack))
      .catch(reason => setError(String(reason)));
  }, [priority.priority_id, target.join("|"), opponent.join("|")]);
  useEffect(() => {
    if (!pack) return;
    setSelectedEventId(
      initialEventId && pack.representative_moments.some(moment => moment.event_id === initialEventId)
        ? initialEventId : null,
    );
  }, [pack, initialEventId]);
  const selectedMoment = pack?.representative_moments.find(moment => moment.event_id === selectedEventId) ?? null;
  const selectedDetail = pack?.representative_moment_details.find(detail => detail.event_id === selectedEventId) ?? null;
  return <section className="evidence-pack-view" aria-label="Pre-match evidence pack">
    <div className="evidence-pack-heading"><div><p className="eyebrow">Evidence Pack</p><h2>{priority.title}</h2></div><button type="button" onClick={onClose}>{closeLabel}</button></div>
    {error && <p className="profile-warning">Evidence Pack unavailable: {error}</p>}
    {!error && !pack && <p className="muted">Assembling existing deterministic evidence…</p>}
    {pack && <>
      <section className="evidence-pack-section"><small>1 · Review question</small><h3>{pack.priority.review_question}</h3><p>{metricLabel(pack.priority.direction)} · {metricLabel(pack.primary_source_role)}</p></section>
      <section className="evidence-pack-section"><small>2 · Why this was selected</small><p>{pack.why_selected.description}</p><p>Evidence support: {pack.why_selected.evidence_support}</p></section>
      <section className="evidence-pack-section"><small>3 · Team-vs-opponent evidence</small>
        <div className="evidence-pack-baselines">
          {[pack.season_baselines.target, pack.season_baselines.opponent].map(baseline => <article key={`${baseline.team_id}-${baseline.metric}`}><strong>{baseline.team_name}</strong><span>{metricLabel(baseline.role)}</span><b>{formatValue(baseline.median, baseline.unit)}</b><small>Typical match range {formatValue(baseline.q25, baseline.unit)}–{formatValue(baseline.q75, baseline.unit)}</small></article>)}
        </div>
        <p>{pack.distribution_summary.distributions_materially_overlap == null ? "Usual match-range comparison unavailable." : pack.distribution_summary.distributions_materially_overlap ? "The teams' usual match ranges overlap." : "The teams' usual match ranges overlap only slightly."}</p>
        {pack.supporting_tendencies.length > 0 && <p className="muted">{pack.supporting_tendencies.length} supporting season tendency record{pack.supporting_tendencies.length === 1 ? "" : "s"} available in technical provenance.</p>}
      </section>
      <section className="evidence-pack-section"><small>4 · Recurring sequence patterns</small><p>{pack.sequence_pattern_summaries.denominator_statement}</p>
        <div className="evidence-pack-patterns">{pack.sequence_pattern_summaries.event_sequence_groups.map(pattern => <article key={pattern.pattern_id}><strong>{pattern.pattern_label}</strong><span>{pattern.count}/{pack.sequence_pattern_summaries.retrieved_sample_count} retrieved moments · {pattern.contributing_matches.length} matches</span></article>)}</div>
        {!pack.sequence_pattern_summaries.event_sequence_groups.length && <p className="muted">No supported sequence grouping is available.</p>}
      </section>
      <section className="evidence-pack-section"><small>5 · Representative moments</small>
        <div className="evidence-pack-moments">{pack.representative_moments.map(moment => <button type="button" key={moment.event_id} className={selectedEventId === moment.event_id ? "selected" : ""} onClick={() => { setSelectedEventId(moment.event_id); onMomentChange?.(moment.event_id); }}><strong>{moment.team_name} vs {moment.opponent_name}</strong><span>{moment.match_date} · {moment.minute}:{String(moment.second).padStart(2, "0")}</span><small>{moment.description}</small></button>)}</div>
        {!pack.representative_moments.length && <p className="muted">No representative events are available for this evidence type.</p>}
      </section>
      <section className="evidence-pack-section"><small>6 · Moment detail / pitch view</small>
        {selectedMoment && selectedDetail ? <><button type="button" className="evidence-back" onClick={() => { setSelectedEventId(null); onMomentChange?.(null); }}>Back to Evidence Pack</button><h3>{selectedMoment.team_name} vs {selectedMoment.opponent_name} · {selectedMoment.minute}:{String(selectedMoment.second).padStart(2, "0")}</h3><StatsBombEventPitch events={selectedDetail.sequence_events} snapshotPlayers={selectedDetail.moment_360_context.snapshot_players}/><ol className="event-sequence-timeline">{selectedDetail.sequence_events.map(event => <li key={event.event_id} className={event.is_focal ? "focal" : ""}><span>{event.minute}:{String(event.second).padStart(2, "0")}</span><div><strong>{event.event_type}</strong><small>{event.team_name ?? "Team unavailable"}{event.outcome ? ` · ${event.outcome}` : ""}</small></div></li>)}</ol></> : <p className="muted">Choose a representative moment above to inspect its event sequence.</p>}
      </section>
      <section className="evidence-pack-section"><small>7 · Optional 360 context</small><p>{pack.optional_360_context.scope}</p><p>{pack.optional_360_context.observed_moment_count}/{pack.optional_360_context.representative_moment_count} representative moments have aligned 360 snapshots.</p>
        {selectedDetail?.moment_360_context.available ? <dl><div><dt>Visible teammates</dt><dd>{selectedDetail.moment_360_context.visible_teammate_count}</dd></div><div><dt>Visible opponents</dt><dd>{selectedDetail.moment_360_context.visible_opponent_count}</dd></div><div><dt>Nearest opponent</dt><dd>{selectedDetail.moment_360_context.nearest_opponent_distance?.toFixed(1) ?? "Unavailable"} units</dd></div></dl> : <p className="muted">The selected moment is event-only; no matching 360 snapshot is available.</p>}
      </section>
      <section className="evidence-pack-section"><small>8 · Limitations and provenance</small><p className="video-status">{pack.video_status.message}</p>{pack.limitations.map(item => <p className="moment-limitation" key={item}>{item}</p>)}<details><summary>Technical provenance</summary><pre>{JSON.stringify(pack.technical_provenance, null, 2)}</pre></details></section>
    </>}
  </section>;
}

function ReviewPriorities({ priorities, target, opponent }: { priorities: PreMatchReviewPriority[]; target: string[]; opponent: string[] }) {
  const [selectedPriority, setSelectedPriority] = useState<PreMatchReviewPriority | null>(null);
  return <section className="panel review-priorities">
    <div className="panel-heading"><div><p className="eyebrow">Pre-match review</p><h2>Review priorities</h2></div><span>{priorities.length} qualified themes</span></div>
    <p className="evidence-support-help">Evidence support reflects sample adequacy and season-relative evidence quality. It does not measure tactical importance, causality, or prediction confidence.</p>
    {priorities.length ? <div className="review-priority-list">{priorities.map(priority => (
      <article key={priority.priority_id}>
        <span className="review-priority-rank">{priority.rank}</span>
        <div>
          <div className="review-priority-meta">
            <small>{metricLabel(priority.football_family)} · {metricLabel(priority.direction)} · {metricLabel(priority.primary_source_role)}</small>
            <span className={`evidence-band ${priority.evidence_basis === "High" ? "established" : priority.evidence_basis === "Moderate" ? "developing" : "provisional"}`}>Evidence support: {priority.evidence_basis}</span>
          </div>
          <h3>{priority.title}</h3><p>{priority.review_question}</p>
          <button type="button" className="evidence-pack-open" onClick={() => setSelectedPriority(priority)}>Open Evidence Pack</button>
          <dl>
            <div><dt>{priority.target_baseline.team_name}</dt><dd>{formatValue(priority.target_baseline.median, priority.target_baseline.unit)}</dd></div>
            <div><dt>{priority.opponent_baseline.team_name}</dt><dd>{formatValue(priority.opponent_baseline.median, priority.opponent_baseline.unit)}</dd></div>
          </dl>
          <details><summary>Evidence coverage</summary>
            <p>Primary source: {metricLabel(priority.primary_source_role)}.</p>
            {priority.supporting_evidence.some(item => item.source_role === "supporting_tendency") && <p>Additional context: Supporting tendency.</p>}
            <p>{Object.entries(priority.match_counts).map(([key, value]) => `${metricLabel(key)}: ${value}`).join(" · ")}</p>
            <p>{Object.entries(priority.coverage).map(([key, value]) => `${metricLabel(key)}: ${(value * 100).toFixed(0)}%`).join(" · ")}</p>
            {priority.limitations.map(item => <p key={item}>{item}</p>)}
          </details>
          <ReviewMoments priority={priority} target={target} opponent={opponent}/>
        </div>
      </article>
    ))}</div> : <div className="review-priority-empty"><strong>No review themes passed the evidence threshold.</strong><span>This does not mean the matchup lacks important tactical questions.</span></div>}
    {selectedPriority && <EvidencePackView priority={selectedPriority} target={target} opponent={opponent} onClose={() => setSelectedPriority(null)}/>} 
  </section>;
}

function FindingCard({ finding }: { finding: OpponentComparisonFinding }) {
  return <article className="comparison-finding"><span className="comparison-rank">{finding.rank}</span><div>
    <div className="comparison-finding-meta"><small>{metricLabel(finding.finding_family)}</small><span className={`evidence-band ${finding.evidence_basis === "High" ? "established" : finding.evidence_basis === "Moderate" ? "developing" : "provisional"}`}>Evidence support: {finding.evidence_basis}</span></div>
    <h3>{finding.title}</h3><p>{finding.description}</p>
    <dl><div><dt>Target median</dt><dd>{formatValue(finding.target_value, finding.unit)}</dd></div><div><dt>Opponent median</dt><dd>{formatValue(finding.opponent_value, finding.unit)}</dd></div><div><dt>Opponent − target</dt><dd>{finding.signed_difference > 0 ? "+" : ""}{formatValue(finding.signed_difference, finding.unit)}</dd></div></dl>
    <details><summary>Evidence and limitations</summary><p>Standardized difference: {finding.combined_standardized_difference > 0 ? "+" : ""}{finding.combined_standardized_difference.toFixed(2)} combined robust season scales.</p><p>{finding.contributing_matches_target} target matches · {finding.contributing_matches_opponent} opponent matches.</p>{finding.limitations.map(item => <p key={item}>{item}</p>)}</details>
  </div></article>;
}

function InteractionDirection({ rows, findings }: { rows: MatchupInteraction[]; findings: MatchupInteractionFinding[] }) {
  if (!rows.length) return null;
  const attack = rows[0].attacking_team_name;
  const defence = rows[0].defending_team_name;
  return <section className="panel profile-section interaction-direction">
    <div className="panel-heading"><div><p className="eyebrow">Directional interaction</p><h2>{attack} attack vs {defence} defence</h2></div><span>{rows.length} supported interactions</span></div>
    {findings.length ? <div className="interaction-finding-list">{findings.map(finding => <article key={finding.finding_id}><span>{finding.rank_within_direction}</span><div>
      <div><small>{metricLabel(finding.interaction_family)}</small><strong>Evidence support: {finding.evidence_basis}</strong></div>
      <h3>{finding.title}</h3><p>{finding.description}</p>
      <details><summary>Evidence and limitations</summary><p>Interaction strength {finding.interaction_strength_score.toFixed(2)} · standardized mismatch {finding.combined_standardized_mismatch > 0 ? "+" : ""}{finding.combined_standardized_mismatch.toFixed(2)} robust scales.</p><p>{finding.attacking_contributing_matches} attacking-team matches · {finding.defending_contributing_matches} defending-team matches.</p>{finding.limitations.map(item => <p key={item}>{item}</p>)}</details>
    </div></article>)}</div> : <p className="muted">No directional mismatch passed the deterministic finding threshold.</p>}
    <table><thead><tr><th>Interaction</th><th>{attack} production</th><th>{defence} conceded</th><th>Mismatch</th><th>Overlap</th><th>Strength</th></tr></thead><tbody>{rows.map(row => <tr key={row.interaction_family}>
      <td>{metricLabel(row.interaction_family)}<small className="table-note">{metricLabel(row.production_metric)} vs {metricLabel(row.exposure_metric)}</small></td>
      <td>{formatValue(row.attacking_median, row.unit)}<small className="table-note">{formatValue(row.attacking_q25, row.unit)}–{formatValue(row.attacking_q75, row.unit)} · {row.attacking_contributing_matches} matches · {(row.attacking_coverage * 100).toFixed(0)}%</small></td>
      <td>{formatValue(row.defending_exposure_median, row.unit)}<small className="table-note">{formatValue(row.defending_exposure_q25, row.unit)}–{formatValue(row.defending_exposure_q75, row.unit)} · {row.defending_contributing_matches} matches · {(row.defending_coverage * 100).toFixed(0)}%</small></td>
      <td>{row.review_priority_compatibility === "unsupported_cross_metric" ? "Not comparable" : <>{row.signed_mismatch != null && row.signed_mismatch > 0 ? "+" : ""}{formatValue(row.signed_mismatch, row.unit)}<small className="table-note">{row.combined_standardized_mismatch == null ? "Standardized unavailable" : `${row.combined_standardized_mismatch > 0 ? "+" : ""}${row.combined_standardized_mismatch.toFixed(2)} robust scales`}</small></>}</td>
      <td>{row.iqr_overlap_ratio == null ? <span className="overlap-label material">Not assessed</span> : <><span className={`overlap-label ${row.distributions_materially_overlap ? "material" : "limited"}`}>{row.distributions_materially_overlap ? "Material" : "Limited"}</span><small className="table-note">IQR overlap {(row.iqr_overlap_ratio * 100).toFixed(0)}%</small></>}</td>
      <td>{row.interaction_strength_score == null ? "Not scored" : row.interaction_strength_score.toFixed(2)}<small className="table-note">{metricLabel(row.review_priority_compatibility)}</small></td>
    </tr>)}</tbody></table>
    <details className="interaction-definitions"><summary>Interaction definitions and comparability</summary>{rows.map(row => <div key={row.interaction_family}><strong>{metricLabel(row.interaction_family)}</strong><p>Production: {row.production_definition}</p><p>Exposure: {row.exposure_definition}</p><small>Review compatibility: {metricLabel(row.review_priority_compatibility)}. {row.comparability_basis}</small></div>)}</details>
  </section>;
}

export function OpponentComparisonPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search), []);
  const target = fields.map(field => query.get(`target_${field}`) ?? "");
  const opponent = fields.map(field => query.get(`opponent_${field}`) ?? "");
  const configured = [...target, ...opponent].every(Boolean);
  const [summary, setSummary] = useState<OpponentComparisonSummary | null>(null);
  const [metrics, setMetrics] = useState<OpponentMetricComparison[]>([]);
  const [excluded, setExcluded] = useState<Array<{ family: string; metric: string; reason: string }>>([]);
  const [findings, setFindings] = useState<OpponentComparisonFinding[]>([]);
  const [interactions, setInteractions] = useState<MatchupInteraction[]>([]);
  const [interactionFindings, setInteractionFindings] = useState<MatchupInteractionFinding[]>([]);
  const [reviewPriorities, setReviewPriorities] = useState<PreMatchReviewPriority[]>([]);
  const [excludedInteractions, setExcludedInteractions] = useState<Array<{ direction_id: string; attacking_team_id: string | number; defending_team_id: string | number; interaction_family: string; reason: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!configured) return;
    Promise.all([
      opponentComparisonApi.summary(target, opponent), opponentComparisonApi.metrics(target, opponent),
      opponentComparisonApi.findings(target, opponent), opponentComparisonApi.interactions(target, opponent),
      opponentComparisonApi.interactionFindings(target, opponent), opponentComparisonApi.reviewPriorities(target, opponent),
    ]).then(([s, m, f, i, interactionResponse, reviewResponse]) => {
      setSummary(s); setMetrics(m.metric_comparisons); setExcluded(m.excluded_metrics);
      setFindings(f.ranked_comparison_findings); setInteractions(i.directional_interactions);
      setExcludedInteractions(i.excluded_interactions); setInteractionFindings(interactionResponse.ranked_interaction_findings);
      setReviewPriorities(reviewResponse.review_priorities);
    }).catch(reason => setError(String(reason)));
  }, [configured, target.join("|"), opponent.join("|")]);

  if (!configured) return <SetupForm query={query} />;
  if (error) return <main className="state"><h1>Opponent comparison unavailable</h1><p>{error}</p><a href="/opponent-comparison">Change team-seasons</a></main>;
  if (!summary) return <main className="state"><div className="spinner"/><h1>Building opponent comparison</h1><p>Checking metric definitions, coverage, and season distributions.</p></main>;

  const grouped = familyOrder.map(family => ({ family, rows: metrics.filter(row => row.family === family) })).filter(group => group.rows.length);
  const directions = Array.from(new Set(interactions.map(row => row.direction_id)));
  return <main className="shell opponent-comparison">
    <header className="profile-header"><div><p className="eyebrow">TactIQ / Pre-match / Event evidence</p><h1>{summary.target.team_name} vs {summary.opponent.team_name}</h1><p>Descriptive season comparison · match-level historical evidence</p></div><div className="profile-status"><span className="evidence-band established">Comparable context</span><small>{summary.compatibility.provider_rule.replaceAll("_", " ")} · {summary.compatibility.coordinate_system}</small><a href={`/pre-match-briefing?${query.toString()}`}>Open briefing</a><a href="/opponent-comparison">Change comparison</a></div></header>
    <section className="comparison-team-grid"><TeamSeasonCard identity={summary.target} side="Target"/><TeamSeasonCard identity={summary.opponent} side="Opponent"/></section>
    <section className="profile-caution event-context"><strong>{summary.compared_metric_count} adequately covered metrics</strong><span>Minimum {summary.configuration.minimum_contributing_matches} matches and {(summary.configuration.minimum_coverage * 100).toFixed(0)}% coverage on each side · differences are opponent minus target</span></section>
    <ReviewPriorities priorities={reviewPriorities} target={target} opponent={opponent}/>
    <section className="interaction-layer"><div className="interaction-layer-heading"><p className="eyebrow">Matchup interaction evidence</p><h2>Attacking production vs opposition defensive exposure</h2><p>Each direction is calculated and retained separately.</p></div>{directions.map(direction => <InteractionDirection key={direction} rows={interactions.filter(row => row.direction_id === direction)} findings={interactionFindings.filter(row => row.direction_id === direction)}/>)}{!directions.length && <section className="panel profile-section"><p className="muted">No directional interactions passed the two-sided evidence requirements.</p></section>}</section>
    <section className="panel profile-section comparison-findings"><div className="panel-heading"><h2>Clearest season contrasts</h2><span>One per family · limited IQR overlap</span></div>{findings.length ? findings.map(finding => <FindingCard key={finding.finding_id} finding={finding}/>) : <p className="muted">No contrasts passed the deterministic clarity threshold. This does not mean the teams have identical tendencies.</p>}</section>
    {grouped.map(group => <section className="panel profile-section comparison-family" key={group.family}><div className="panel-heading"><h2>{metricLabel(group.family)}</h2><span>Median · Q25–Q75 across matches</span></div><table><thead><tr><th>Metric</th><th>{summary.target.team_name}</th><th>{summary.opponent.team_name}</th><th>Difference</th><th>Standardized</th><th>Distribution overlap</th></tr></thead><tbody>{group.rows.map(row => <tr key={row.metric}>
      <td>{metricLabel(row.metric)}<small className="table-note">{row.definition}</small></td>
      <td>{formatValue(row.target_median, row.unit)}<small className="table-note">{formatValue(row.target_q25, row.unit)}–{formatValue(row.target_q75, row.unit)} · {row.target_contributing_matches} matches · {(row.target_coverage * 100).toFixed(0)}%</small></td>
      <td>{formatValue(row.opponent_median, row.unit)}<small className="table-note">{formatValue(row.opponent_q25, row.unit)}–{formatValue(row.opponent_q75, row.unit)} · {row.opponent_contributing_matches} matches · {(row.opponent_coverage * 100).toFixed(0)}%</small></td>
      <td>{row.signed_difference > 0 ? "+" : ""}{formatValue(row.signed_difference, row.unit)}<small className="table-note">{row.relative_difference == null ? "Relative unavailable" : `${row.relative_difference > 0 ? "+" : ""}${(row.relative_difference * 100).toFixed(1)}% relative to target`}</small></td>
      <td>{row.combined_standardized_difference == null ? "Unavailable" : `${row.combined_standardized_difference > 0 ? "+" : ""}${row.combined_standardized_difference.toFixed(2)}`}<small className="table-note">Target scale {row.standardized_by_target_variability?.toFixed(2) ?? "—"} · opponent scale {row.standardized_by_opponent_variability?.toFixed(2) ?? "—"}</small></td>
      <td><span className={`overlap-label ${row.distributions_materially_overlap ? "material" : "limited"}`}>{row.distributions_materially_overlap ? "Material overlap" : "Limited overlap"}</span><small className="table-note">IQR overlap ratio {(row.iqr_overlap_ratio * 100).toFixed(0)}%</small></td>
    </tr>)}</tbody></table></section>)}
    {(excluded.length > 0 || excludedInteractions.length > 0) && <section className="panel profile-section"><details><summary>{excluded.length + excludedInteractions.length} metrics or interactions excluded by comparability and evidence rules</summary>{excluded.map(row => <p className="profile-warning" key={`${row.family}-${row.metric}`}>{metricLabel(row.metric)} · {row.reason}</p>)}{excludedInteractions.map(row => <p className="profile-warning" key={`${row.direction_id}-${row.interaction_family}`}>{metricLabel(row.interaction_family)} · {row.direction_id.replaceAll("_", " ")} · {row.reason}</p>)}</details></section>}
    <p className="comparison-disclaimer">These are separate season distributions. They do not predict the head-to-head match, establish causes, identify weaknesses, or recommend a tactical plan.</p>
  </main>;
}
