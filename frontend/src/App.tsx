import { useEffect, useRef, useState } from "react";
import { analysisApi } from "./api";
import { Pitch } from "./Pitch";
import { MatchTacticalAnalysisView } from "./MatchTacticalAnalysisView";
import type { MatchAnalysisSection } from "./MatchTacticalAnalysisView";
import { FootballIcon, TeamBadge } from "./FootballVisuals";
import { VisualMatchStory } from "./VisualMatchStory";
import { evidenceLabel, priorityLabel, formatValue, metricLabel } from './presentation';
import type { FindingDetailResponse, FindingExplanationResponse, MatchSummaryResponse, MatchTacticalProfile, PitchFrameResponse, RankedFinding, RankedFindingsResponse } from "./types";

type WorkspaceSection = MatchAnalysisSection | "story" | "evidence";
const routeMatch = window.location.pathname.match(/^\/matches\/([^/]+)(?:\/(overview|story|flow|teams|goals|evidence))?\/?$/);
const query = new URLSearchParams(window.location.search);
const matchId = routeMatch?.[1] ?? query.get("match") ?? import.meta.env.VITE_MATCH_ID ?? "2017461";
const activeSection = (routeMatch?.[2] as WorkspaceSection | undefined) ?? "overview";
const requestedFindingId = query.get("finding");
const metric = metricLabel;
const selectionReason = (value: string | null | undefined) => value ? metric(value) : null;

function Header({ summary }: { summary: MatchSummaryResponse }) {
  const match = summary.match;
  const date = match.date_time ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(match.date_time)) : "Date unavailable";
  return <header className="football-scoreboard">
    <div className="scoreboard-meta"><span>Match analysis · <a href="/live">Live matches</a></span><time>{date}</time></div>
    <div className="scoreboard-teams">
      <div className="scoreboard-team home"><TeamBadge team={match.home_team} side="home"/><div><strong>{match.home_team.name ?? match.home_team.code ?? "Home"}</strong><small>Home</small></div></div>
      <div className="scoreboard-score"><strong>{match.home_team.score ?? "–"}</strong><span>FT</span><strong>{match.away_team.score ?? "–"}</strong></div>
      <div className="scoreboard-team away"><div><strong>{match.away_team.name ?? match.away_team.code ?? "Away"}</strong><small>Away</small></div><TeamBadge team={match.away_team} side="away"/></div>
    </div>
    <div className="scoreboard-foot"><span>{summary.capabilities.has_continuous_tracking ? "Tracking-backed match view" : "Event-backed match view"}</span><details><summary>Data source</summary><p>{match.provider.replaceAll("_", " ")} · {summary.finding_count} validated observations</p></details></div>
  </header>;
}

const workspaceSections: { id: WorkspaceSection; label: string; description: string; icon: "overview" | "flow" | "teams" | "goal" | "evidence" }[] = [
  { id: "overview", label: "Overview", description: "The quickest read of the match", icon: "overview" },
  { id: "story", label: "Visual story", description: "Watch how the game changed", icon: "flow" },
  { id: "flow", label: "Match flow", description: "When control and threat changed", icon: "flow" },
  { id: "teams", label: "Team analysis", description: "How each side differed from normal", icon: "teams" },
  { id: "goals", label: "Goals", description: "How every goal developed", icon: "goal" },
  { id: "evidence", label: "Evidence", description: "Measurements, findings and limitations", icon: "evidence" },
];

function MatchNavigation({ active }: { active: WorkspaceSection }) {
  return <nav className="match-workspace-nav" aria-label="Match analysis sections">{workspaceSections.map(item => <a href={`/matches/${encodeURIComponent(String(matchId))}/${item.id}`} className={active === item.id ? "active" : ""} key={item.id}><FootballIcon name={item.icon}/><span><strong>{item.label}</strong><small>{item.description}</small></span></a>)}</nav>;
}

function OverviewDirectory({ goalCount, findingCount }: { goalCount: number; findingCount: number }) {
  return <section className="match-directory"><header><small>Explore the match</small><h2>Choose what you want to understand</h2><p>Each area has one job, so you never have to read the entire analysis at once.</p></header><div>{workspaceSections.filter(item => item.id !== "overview").map(item => <a href={`/matches/${encodeURIComponent(String(matchId))}/${item.id}`} key={item.id}><FootballIcon name={item.icon}/><span><strong>{item.label}</strong><small>{item.description}</small>{item.id === "goals" && <em>{goalCount} available</em>}{item.id === "evidence" && <em>{findingCount} shortlisted</em>}</span><b>Open →</b></a>)}</div></section>;
}

function Coverage({ summary }: { summary: MatchSummaryResponse }) {
  return <section className="panel coverage"><div className="panel-heading"><h2>Analysis coverage</h2><span>Capability-aware</span></div><table><thead><tr><th>Module</th><th>Status</th><th>Findings</th><th>Reason</th></tr></thead><tbody>{summary.analysis_coverage.map(item => <tr key={item.analysis}><td>{metric(item.analysis)}</td><td><span className={`status ${item.status}`}>{item.status.replaceAll("_", " ")}</span></td><td>{item.finding_count}</td><td>{item.reason || "—"}</td></tr>)}</tbody></table>{summary.warnings.length > 0 && <div className="warning-list">{summary.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}</section>;
}

function FindingList({ findings, selected, onSelect }: { findings: RankedFinding[]; selected: string | null; onSelect: (finding: RankedFinding) => void }) {
  if (!findings.length) return <section className="panel empty"><h2>No ranked findings</h2><p>The completed analyses did not meet the deterministic evidence and contextual-baseline thresholds.</p></section>;
  return <section className="panel findings"><div className="panel-heading"><h2>Ranked findings</h2><span>Review priority</span></div>{findings.map(item => <button key={item.finding_id} className={`finding-row ${selected === item.finding_id ? "selected" : ""}`} onClick={() => onSelect(item)}><span className="rank">{item.rank}</span><span className="finding-main"><strong>{item.title}</strong><small>{item.description}</small>{item.selection_reason && <span className="comparison">Selected: {selectionReason(item.selection_reason)}</span>}</span><span className="finding-scores"><b>Priority: {priorityLabel(item.priority.priority_score)}</b><span>Evidence: {evidenceLabel(item.confidence_level)}</span></span></button>)}</section>;
}

function Explanation({ explanation, loading, error, onRetry }: { explanation: FindingExplanationResponse | null; loading: boolean; error: string | null; onRetry: () => void }) {
  return <section className="interpretation-section" aria-live="polite">
    <div className="section-heading"><div><span className="section-kicker">AI interpretation</span><h3>Analyst explanation</h3></div>{explanation && <span className={`explanation-source ${explanation.metadata.source}`}>{explanation.metadata.source === 'model' ? 'Model generated' : 'Deterministic fallback'}</span>}</div>
    {loading && <div className="explanation-state"><div className="mini-spinner" /><p>Preparing an evidence-bounded explanation…</p></div>}
    {!loading && error && <div className="explanation-state error"><p>{error}</p><button onClick={onRetry}>Retry explanation</button></div>}
    {!loading && !error && explanation && <div className="explanation-copy">
      {explanation.metadata.source === 'deterministic_fallback' && <p className="fallback-note">The configured model was unavailable or its output did not pass evidence validation. This text was generated deterministically from the EvidencePack.</p>}
      <div><h4>Plain-English summary</h4><p>{explanation.explanation.plain_english_summary}</p></div>
      <div><h4>Why it might matter</h4><p>{explanation.explanation.why_it_matters}</p></div>
      <div className="video-review"><h4>What to review in video</h4><p>{explanation.explanation.what_to_review_in_video}</p></div>
      <div className="confidence-note"><h4>Confidence note</h4><p>{explanation.explanation.confidence_note}</p></div>
    </div>}
  </section>;
}

function Detail({ detail, explanation, explanationLoading, explanationError, onRetryExplanation, onMoment }: { detail: FindingDetailResponse | null; explanation: FindingExplanationResponse | null; explanationLoading: boolean; explanationError: string | null; onRetryExplanation: () => void; onMoment: (index: number) => void }) {
  if (!detail) return <section className="panel detail empty"><h2>Finding detail</h2><p>Select a ranked finding to inspect its EvidencePack.</p></section>;
  const evidence = detail.evidence;
  return <section className="panel detail">
    <div className="panel-heading"><h2>{detail.finding.title}</h2></div>
    <p className="detail-description">{detail.finding.description}</p>
    <div className="score-grid">
      <div><small>Priority</small><strong>{priorityLabel(detail.finding.priority.priority_score)}</strong></div>
      <div><small>Evidence</small><strong>{evidenceLabel(detail.finding.confidence_level)}</strong></div>
      <div><small>{String(evidence.exact_metrics.sample_unit ?? (detail.finding.finding_type === 'team_shape_extreme' ? 'Frames' : 'Observations'))}</small><strong>{detail.finding.sample_size.toLocaleString()}</strong></div>
    </div>
    <section className="observed-section">
      <div className="section-heading"><div><span className="section-kicker">Observed evidence</span><h3>Measured match context</h3></div><span className="source-badge">Deterministic</span></div>
      <h3>Evidence metrics</h3><dl>{Object.entries(evidence.exact_metrics).map(([key, value]) => <div key={key}><dt>{metric(key)}</dt><dd>{formatValue(key, value)}</dd></div>)}</dl>
      <h3>Comparator / baseline</h3><dl>{Object.entries(evidence.comparator).map(([key, value]) => <div key={key}><dt>{metric(key)}</dt><dd>{formatValue(key, value)}</dd></div>)}</dl>
      <h3>Representative moments</h3>
      {evidence.representative_moments.length ? <div className="moments">{evidence.representative_moments.map((moment, index) => <button key={`${moment.frame}-${index}`} onClick={() => onMoment(index)}>
        <strong>{moment.label ?? `Moment ${index + 1}`}</strong>
        {moment.metric_value_metres !== undefined && <span>{moment.metric_value_metres.toFixed(1)} m · {moment.metric?.replace('outfield_', '')}</span>}
        {moment.target_value_metres !== undefined && <span>{moment.target_quantile === .5 ? 'Median' : `Q${(moment.target_quantile ?? 0) * 100}`} target: {moment.target_value_metres.toFixed(1)} m</span>}
        {moment.tactical_phase && <span>{metric(moment.tactical_phase)}{moment.possession_status ? ` · ${metric(moment.possession_status)}` : ''}</span>}
        <span>{moment.timestamp ?? `frame ${moment.frame}`} · P{moment.period}</span>
      </button>)}</div> : <p className="muted">No frame-level moment is available for this finding type.</p>}
      <details className="ranking-components"><summary>Normalized ranking components</summary><p>Internal review scores on a 0–1 scale. These are not probabilities, statistical confidence or percentage changes. Priority bands: High ≥0.75; Medium ≥0.50; Low below 0.50.</p><dl>{(['priority_score', 'evidence_strength', 'sample_adequacy', 'effect_magnitude', 'temporal_relevance', 'data_quality_coverage', 'redundancy_penalty'] as const).map(key => <div key={key}><dt>{key === 'effect_magnitude' ? 'Contextual variation score' : metric(key)}</dt><dd>{detail.finding.priority[key].toFixed(2)}</dd></div>)}</dl></details>
      <h3>Capability provenance</h3><p className="provenance">{evidence.capability_provenance.provider} · required: {evidence.capability_provenance.required_capabilities.join(', ')} · assumed roles: {String(evidence.capability_provenance.allow_assumed_roles)}</p>
      <h3>Limitations</h3><ul>{evidence.limitations.map(item => <li key={item}>{item}</li>)}</ul>
    </section>
    <Explanation explanation={explanation} loading={explanationLoading} error={explanationError} onRetry={onRetryExplanation} />
  </section>;
}

export default function App() {
  const [summary, setSummary] = useState<MatchSummaryResponse | null>(null); const [ranked, setRanked] = useState<RankedFindingsResponse | null>(null); const [tactical, setTactical] = useState<MatchTacticalProfile | null>(null); const [detail, setDetail] = useState<FindingDetailResponse | null>(null); const [explanation, setExplanation] = useState<FindingExplanationResponse | null>(null); const [explanationLoading, setExplanationLoading] = useState(false); const [explanationError, setExplanationError] = useState<string | null>(null); const [frame, setFrame] = useState<PitchFrameResponse | null>(null); const [error, setError] = useState<string | null>(null); const requestSequence = useRef(0); const linkedFindingOpened = useRef(false);
  useEffect(() => { Promise.all([analysisApi.summary(matchId), analysisApi.ranked(matchId), analysisApi.tacticalAnalysis(matchId)]).then(([nextSummary, nextRanked, nextTactical]) => { setSummary(nextSummary); setRanked(nextRanked); setTactical(nextTactical); }).catch(reason => setError(reason instanceof Error ? reason.message : "Unable to load analysis.")); }, []);
  const loadExplanation = (findingId: string, sequence: number) => { setExplanationLoading(true); setExplanationError(null); analysisApi.explanation(matchId, findingId).then(value => { if (requestSequence.current === sequence) setExplanation(value); }).catch(() => { if (requestSequence.current === sequence) setExplanationError("The explanation could not be loaded. The observed evidence remains available below."); }).finally(() => { if (requestSequence.current === sequence) setExplanationLoading(false); }); };
  const select = (finding: RankedFinding) => { const sequence = ++requestSequence.current; window.history.replaceState({}, "", `/matches/${encodeURIComponent(String(matchId))}/evidence?finding=${encodeURIComponent(finding.finding_id)}`); setDetail(null); setExplanation(null); setExplanationError(null); setExplanationLoading(false); setFrame(null); analysisApi.detail(matchId, finding.finding_id).then(value => { if (requestSequence.current !== sequence) return; setDetail(value); loadExplanation(finding.finding_id, sequence); }).catch(reason => setError(String(reason))); };
  useEffect(() => { if (!linkedFindingOpened.current && ranked && requestedFindingId) { const linked = ranked.ranked_findings.find(item => item.finding_id === requestedFindingId); linkedFindingOpened.current = true; if (linked) select(linked); } }, [ranked]);
  const retryExplanation = () => { if (detail) loadExplanation(detail.finding.finding_id, requestSequence.current); };
  const showMoment = (index: number) => { if (!detail) return; analysisApi.frame(matchId, detail.finding.finding_id, index).then(setFrame).catch(reason => setError(String(reason))); };
  if (error) return <main className="state"><h1>Analysis unavailable</h1><p>{error}</p><button onClick={() => window.location.reload()}>Retry</button></main>;
  if (!summary || !ranked || !tactical) return <main className="state"><div className="spinner" /><h1>Preparing match analysis</h1><p>Reading both teams, match changes and deterministic evidence.</p></main>;
  return <main className="shell match-workspace"><Header summary={summary} /><MatchNavigation active={activeSection}/>
    {activeSection === "overview" && <><MatchTacticalAnalysisView profile={tactical} section="overview" loading={false} error={null}/><OverviewDirectory goalCount={tactical.goals.length} findingCount={ranked.ranked_findings.length}/></>}
    {activeSection === "story" && <VisualMatchStory profile={tactical}/>} 
    {activeSection === "flow" && <MatchTacticalAnalysisView profile={tactical} section="flow" loading={false} error={null}/>} 
    {activeSection === "teams" && <MatchTacticalAnalysisView profile={tactical} section="teams" loading={false} error={null}/>} 
    {activeSection === "goals" && <MatchTacticalAnalysisView profile={tactical} section="goals" loading={false} error={null}/>} 
    {activeSection === "evidence" && <section className="evidence-workspace"><header className="match-section-intro"><div><small>Evidence room</small><h2>Measurements and supporting proof</h2></div><p>This section is intentionally more detailed. Open it when you want to challenge a conclusion or inspect how TactIQ reached it.</p></header><Coverage summary={summary} /><div className="analysis-grid"><FindingList findings={ranked.ranked_findings} selected={detail?.finding.finding_id ?? null} onSelect={select} /><div className="right-column"><Detail detail={detail} explanation={explanation} explanationLoading={explanationLoading} explanationError={explanationError} onRetryExplanation={retryExplanation} onMoment={showMoment} /><Pitch frame={frame} /></div></div></section>}
  </main>;
}
