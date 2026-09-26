import { useEffect, useMemo, useRef, useState } from "react";
import { opponentComparisonApi } from "./api";
import { StatsBombEventPitch } from "./StatsBombEventPitch";
import { metricLabel } from "./presentation";
import type { PreMatchBriefing, PreMatchBriefingPriority, PreMatchEvidencePack, RepresentativeMoment } from "./types";

const identityFields = ["provider", "team_id", "competition_id", "season_id"] as const;
interface LoadedPriority { priority: PreMatchBriefingPriority; pack: PreMatchEvidencePack; }

const formatNumber = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1);
const formatValue = (value: number, unit: string) => unit === "proportion" ? `${(value * 100).toFixed(1)}%` : unit === "count" ? formatNumber(value) : `${formatNumber(value)}${unit === "per90" ? " per 90" : unit === "xg" ? " xG" : ""}`;
const clock = (moment: RepresentativeMoment) => `${moment.minute}:${String(moment.second).padStart(2, "0")}`;
const footballEvidenceSummary = (summary: string) => summary
  .replaceAll("defensive-exposure median", "usual conceded median")
  .replace("the season interquartile ranges have limited overlap.", "their usual match ranges overlap only slightly.")
  .replace("the season interquartile ranges materially overlap.", "their usual match ranges overlap.");

function PrintMoment({ moment, pack, liveHref }: { moment: RepresentativeMoment; pack: PreMatchEvidencePack; liveHref: string }) {
  const detail = pack.representative_moment_details.find(item => item.event_id === moment.event_id);
  return <article className="print-moment">
    <div className="print-moment-heading"><div><strong>{moment.team_name} vs {moment.opponent_name}</strong><span>{moment.match_date} · {clock(moment)} · Period {moment.period}</span></div><a href={liveHref}>Open live detail</a></div>
    <p>{moment.description}</p>
    {detail?.sequence_events.some(event => event.pitch_renderable) ? <StatsBombEventPitch events={detail.sequence_events} snapshotPlayers={detail.moment_360_context.snapshot_players}/> : <p className="print-unavailable">A static pitch view is unavailable because this event sequence has no usable coordinates.</p>}
    <small>{moment.reason_selected}</small>
  </article>;
}

function PrioritySection({ loaded, baseQuery }: { loaded: LoadedPriority; baseQuery: URLSearchParams }) {
  const { priority, pack } = loaded;
  const moments = pack.representative_moments.slice(0, 3);
  const target = pack.season_baselines.target;
  const opponent = pack.season_baselines.opponent;
  const priorityQuery = new URLSearchParams(baseQuery); priorityQuery.set("priority", priority.priority_id);
  return <section className="print-priority">
    <div className="print-priority-heading"><span className="print-rank">{priority.rank}</span><div><small>{metricLabel(priority.direction)} · {metricLabel(priority.primary_source_role)}</small><h2>{priority.title}</h2></div><strong>Evidence support: {priority.evidence_support}</strong></div>
    <p className="print-review-question">{priority.review_question}</p><p>{footballEvidenceSummary(priority.evidence_summary)}</p>
    <div className="print-baselines" aria-label="Compact target and opponent baseline comparison">
      {[target, opponent].map((baseline, index) => <article key={`${baseline.team_id}-${baseline.role}`}><small>{index === 0 ? "Target baseline" : "Opponent baseline"}</small><strong>{baseline.team_name}: {formatValue(baseline.median, baseline.unit)}</strong><span>Typical match range {formatValue(baseline.q25, baseline.unit)}–{formatValue(baseline.q75, baseline.unit)}</span><span>{metricLabel(baseline.metric)} · {metricLabel(baseline.role)}</span></article>)}
    </div>
    <div className="print-priority-link"><a href={`/pre-match-briefing?${priorityQuery}`}>Open this Evidence Pack in TactIQ</a></div>
    <h3>Representative moments</h3>
    {moments.length === 0 ? <p className="print-unavailable">No faithful event-level representative moment is available for this priority.</p> : moments.map(moment => { const momentQuery = new URLSearchParams(priorityQuery); momentQuery.set("moment", moment.event_id); return <PrintMoment key={moment.event_id} moment={moment} pack={pack} liveHref={`/pre-match-briefing?${momentQuery}`}/>; })}
    <div className="print-priority-limitations"><strong>Material limitations</strong>{pack.limitations.slice(0, 2).map(item => <p key={item}>{item}</p>)}</div>
  </section>;
}

export function PreMatchBriefingPrintPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search), []);
  const target = identityFields.map(field => query.get(`target_${field}`) ?? "");
  const opponent = identityFields.map(field => query.get(`opponent_${field}`) ?? "");
  const complete = [...target, ...opponent].every(Boolean);
  const [briefing, setBriefing] = useState<PreMatchBriefing | null>(null);
  const [loadedPriorities, setLoadedPriorities] = useState<LoadedPriority[]>([]);
  const [error, setError] = useState<string | null>(null);
  const generatedAt = useRef(new Date().toISOString());
  const baseQuery = useMemo(() => new URLSearchParams([...query].filter(([key]) => !["priority", "moment"].includes(key))), [query]);
  useEffect(() => {
    if (!complete) return;
    let cancelled = false;
    const load = async () => { try {
      const response = await opponentComparisonApi.briefing(target, opponent);
      if (cancelled) return;
      setBriefing(response.briefing);
      const loaded: LoadedPriority[] = [];
      for (const priority of response.briefing.review_priorities) {
        const detail = await opponentComparisonApi.reviewPriorityEvidencePack(target, opponent, priority.priority_id);
        loaded.push({ priority, pack: detail.evidence_pack });
        if (!cancelled) setLoadedPriorities([...loaded]);
      }
    } catch (reason) { if (!cancelled) setError(String(reason)); } };
    load(); return () => { cancelled = true; };
  }, [complete]);
  if (!complete) return <main className="state"><h1>Export setup incomplete</h1><p>Choose a target team and opponent from the briefing page first.</p><a href="/pre-match-briefing">Choose matchup</a></main>;
  if (error) return <main className="state"><h1>Briefing export unavailable</h1><p>{error}</p><a href={`/pre-match-briefing?${baseQuery}`}>Return to live briefing</a></main>;
  if (!briefing || loadedPriorities.length < briefing.review_priorities.length) return <main className="state"><div className="spinner"/><h1>Preparing printable briefing</h1><p>Loading evidence packs and static representative moments ({loadedPriorities.length}/{briefing?.review_priorities.length ?? "…"}).</p></main>;
  const competition = briefing.competition.shared ? briefing.competition.target.name ?? "Competition unavailable" : "Different competition contexts";
  const season = briefing.season.shared ? briefing.season.target.name ?? "Season unavailable" : "Different season contexts";
  return <main className="shell briefing-print">
    <nav className="print-controls" aria-label="Export controls"><a href={`/pre-match-briefing?${baseQuery}`}>Back to live briefing</a><button type="button" onClick={() => window.print()}>Print / Save as PDF</button></nav>
    <header className="print-header"><div><p className="eyebrow">TactIQ / Pre-Match Briefing</p><h1>{briefing.target_team.team_name} <span>vs</span> {briefing.opponent_team.team_name}</h1><p>{competition} · {season}</p></div><div><small>Generated</small><time dateTime={generatedAt.current}>{new Date(generatedAt.current).toLocaleString()}</time></div></header>
    <section className="print-executive"><small>Executive summary</small><h2>{briefing.briefing_summary}</h2><p>Deterministic summary of selected evidence only. No tactical recommendations or predictions are included.</p></section>
    {briefing.review_priorities.length === 0 && <section className="print-empty"><h2>No review themes passed the evidence threshold.</h2><p>This does not mean the matchup lacks important tactical questions.</p></section>}
    {loadedPriorities.map(item => <PrioritySection key={item.priority.priority_id} loaded={item} baseQuery={baseQuery}/>)}
    <section className="print-notes"><div><small>Data capability note</small><h2>{briefing.data_capabilities.comparable ? "Comparable season event profiles" : "Data contexts are not directly comparable"}</h2><p>{briefing.target_team.analysed_match_count} {briefing.target_team.team_name} matches · {briefing.opponent_team.analysed_match_count} {briefing.opponent_team.team_name} matches.</p><p>Event evidence is available. Continuous player tracking was not used.</p></div><div><small>Video availability</small><h2>{metricLabel(briefing.video_availability.status)}</h2><p>{briefing.video_availability.message}</p></div><div className="print-limitations"><small>Briefing limitations</small>{briefing.limitations.map(item => <p key={item}>{item}</p>)}</div></section>
    <section className="print-appendix"><h2>Technical appendix</h2><p>Technical provenance is kept separate from the analyst-facing briefing.</p><dl><dt>Matchup ID</dt><dd>{briefing.matchup_identity.id}</dd><dt>Target / opponent IDs</dt><dd>{briefing.target_team.team_id} / {briefing.opponent_team.team_id}</dd><dt>Providers</dt><dd>{briefing.target_team.provider} / {briefing.opponent_team.provider}</dd><dt>Competition / season IDs</dt><dd>{briefing.competition.target.id} / {briefing.season.target.id}</dd><dt>Coordinate system</dt><dd>{briefing.data_capabilities.coordinate_system ?? "Unavailable"}</dd><dt>Required capabilities</dt><dd>{briefing.data_capabilities.required_capabilities.join(", ") || "None"}</dd></dl>{loadedPriorities.map(item => {
      const selected = item.pack.representative_moments.slice(0, 3);
      const definitions = Object.entries(item.pack.primary_interaction_or_comparison).filter(([key, value]) => key.includes("definition") && typeof value === "string").map(([key, value]) => `${metricLabel(key)}: ${String(value)}`);
      return <div key={item.priority.priority_id} className="print-appendix-priority"><strong>{item.priority.rank}. {item.priority.title}</strong><span>Priority ID: {item.priority.priority_id}</span><span>Source role: {item.pack.primary_source_role} · Direction: {item.priority.direction}</span><span>Source finding IDs: {item.pack.priority.source_finding_ids.join(", ") || "None"}</span><span>Provider event IDs: {selected.map(moment => moment.event_id).join(", ") || "None"}</span><span>Coordinates: {item.pack.representative_moment_details[0]?.coordinate_system ?? "No coordinate-bearing event selected"}</span>{definitions.map(definition => <span key={definition}>{definition}</span>)}</div>;
    })}</section>
  </main>;
}
