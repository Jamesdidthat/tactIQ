import { useEffect, useState } from "react";
import { eventProfileApi, teamProfileApi } from "./api";
import { EventMatchStory } from "./EventMatchStory";
import { FootballStyleProfileView } from "./FootballStyleProfileView";
import { FootballShapeProfileView } from "./FootballShapeProfileView";
import { MatchTacticalAnalysisView } from "./MatchTacticalAnalysisView";
import { metricLabel } from "./presentation";
import type { FootballShapeProfile, FootballStyleProfile } from "./types";
import type { EventMetricUnit, EventProfileFinding, EventProfileMatch, EventProfileSummary, EventProfileTendency, EventSeasonBaseline, EventUnusualMatch, MatchArchetypeAssignment, MatchArchetypeSummary, MatchStoryExplanationResponse, MatchStoryResponse, MatchTacticalProfile, MetricRelationshipFinding, MetricRelationshipFit, MetricUnit, TeamDeviation, TeamMetricBaseline, TeamProfileSummaryResponse } from "./types";

const formatMetric = (value: number, unit: MetricUnit) =>
  unit === "count" ? value.toFixed(Number.isInteger(value) ? 0 : 1) : `${value.toFixed(1)} m`;

const contextLabel = (status: string | null, phase: string | null) =>
  [status ? metricLabel(status) : null, phase ? metricLabel(phase) : null].filter(Boolean).join(" · ");

const provenanceBadge = (provider: string, label: string, capabilities: string) => (
  <span className="provenance-badge" title={`Required capabilities: ${capabilities || "none"}`}>
    {provider} · {label}
  </span>
);

const formatEventMetric = (value: number, unit: EventMetricUnit) => {
  if (unit === "proportion") return `${(value * 100).toFixed(1)}%`;
  if (unit === "native_120x80_units") return `${value.toFixed(1)} units`;
  if (unit === "count") return value.toFixed(Number.isInteger(value) ? 0 : 1);
  return value.toFixed(2);
};
const formatFinite = (value: number | null, digits = 2) => value != null && Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";

function EventProfileView({ summary, baselines, findings, tendencies, unusual, matches, archetypes, archetypeAssignments, relationshipFits, relationshipFindings, duplicateCount }: { summary: EventProfileSummary; baselines: EventSeasonBaseline[]; findings: EventProfileFinding[]; tendencies: EventProfileTendency[]; unusual: EventUnusualMatch[]; matches: EventProfileMatch[]; archetypes: MatchArchetypeSummary[]; archetypeAssignments: MatchArchetypeAssignment[]; relationshipFits: MetricRelationshipFit[]; relationshipFindings: MetricRelationshipFinding[]; duplicateCount: number }) {
  const preferred = ["possession_share_estimate", "passes_attempted_per90", "pass_completion_rate", "progressive_passes_per90", "passes_into_penalty_area_per90", "shots_per90", "xg_per90", "high_regains_per90"];
  const cards = preferred.map(metric => baselines.find(item => item.metric === metric)).filter((item): item is EventSeasonBaseline => Boolean(item));
  const requestedMatch = new URLSearchParams(window.location.search).get("match_id");
  const initialMatch = matches.find(item => String(item.match_id) === requestedMatch)?.match_id ?? matches[0]?.match_id ?? null;
  const [selectedMatchId, setSelectedMatchId] = useState<string | number | null>(initialMatch);
  const [matchStory, setMatchStory] = useState<MatchStoryResponse | null>(null);
  const [storyLoading, setStoryLoading] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);
  const [storyExplanation, setStoryExplanation] = useState<MatchStoryExplanationResponse | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [tacticalProfile, setTacticalProfile] = useState<MatchTacticalProfile | null>(null);
  const [tacticalLoading, setTacticalLoading] = useState(false);
  const [tacticalError, setTacticalError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedMatchId != null || !matches.length) return;
    setSelectedMatchId(matches[0].match_id);
  }, [matches, selectedMatchId]);

  useEffect(() => {
    if (selectedMatchId == null) return;
    let active = true;
    setStoryLoading(true);
    setStoryError(null);
    setMatchStory(null);
    setStoryExplanation(null);
    setExplanationError(null);
    setExplanationLoading(true);
    setTacticalProfile(null);
    setTacticalError(null);
    setTacticalLoading(true);
    eventProfileApi.matchStory(summary.provider, String(summary.team.team_id), String(summary.competition_id), String(summary.season_id), selectedMatchId)
      .then(result => { if (active) setMatchStory(result); })
      .catch(reason => { if (active) setStoryError(String(reason)); })
      .finally(() => { if (active) setStoryLoading(false); });
    eventProfileApi.matchStoryExplanation(summary.provider, String(summary.team.team_id), String(summary.competition_id), String(summary.season_id), selectedMatchId)
      .then(result => { if (active) setStoryExplanation(result); })
      .catch(reason => { if (active) setExplanationError(String(reason)); })
      .finally(() => { if (active) setExplanationLoading(false); });
    eventProfileApi.matchTacticalAnalysis(summary.provider, String(summary.team.team_id), String(summary.competition_id), String(summary.season_id), selectedMatchId)
      .then(result => { if (active) setTacticalProfile(result); })
      .catch(reason => { if (active) setTacticalError(String(reason)); })
      .finally(() => { if (active) setTacticalLoading(false); });
    return () => { active = false; };
  }, [selectedMatchId, summary.provider, summary.team.team_id, summary.competition_id, summary.season_id]);

  const selectMatch = (matchId: string) => {
    setSelectedMatchId(matchId);
    const url = new URL(window.location.href);
    url.searchParams.set("match_id", matchId);
    window.history.replaceState({}, "", url);
  };
  return <main className="shell team-profile event-profile">
    <header className="profile-header"><div><p className="eyebrow">TactIQ / Team Profile / Event evidence</p><h1>{summary.team.name}</h1><p>{summary.competition_name ?? `Competition ${summary.competition_id}`} · {summary.season_name ?? `Season ${summary.season_id}`}</p></div><div className="profile-status"><span className="evidence-band established">Established evidence</span><small>{summary.analysed_match_count} match-level observations</small><a href={`/opponent-comparison?target_provider=${encodeURIComponent(summary.provider)}&target_team_id=${encodeURIComponent(String(summary.team.team_id))}&target_competition_id=${encodeURIComponent(String(summary.competition_id))}&target_season_id=${encodeURIComponent(String(summary.season_id))}`}>Compare opponent</a><a href="/">Single-match analysis</a></div></header>
    <section className="profile-caution event-context"><strong>Event profile: {summary.analysed_match_count} matches</strong><span>Match-weighted baselines · StatsBomb 120×80 coordinates · no continuous tracking</span></section>
    <MatchTacticalAnalysisView profile={tacticalProfile} loading={tacticalLoading} error={tacticalError}/>
    <EventMatchStory matches={matches} selectedMatchId={selectedMatchId} story={matchStory} loading={storyLoading} error={storyError} explanation={storyExplanation} explanationLoading={explanationLoading} explanationError={explanationError} onSelect={selectMatch} />
    <section className="panel profile-section"><div className="panel-heading"><h2>Season baseline cards</h2><span>Median · Q25–Q75 across matches</span></div><div className="event-baseline-grid">{cards.map(item => <article key={item.metric} title={item.definition}><small>{metricLabel(item.metric)}</small><strong>{formatEventMetric(item.median_across_matches, item.unit)}</strong><span>{formatEventMetric(item.q25_across_matches, item.unit)}–{formatEventMetric(item.q75_across_matches, item.unit)}</span><em>{item.contributing_matches}/{item.total_matches} matches</em></article>)}</div></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Recurring event-profile tendencies</h2><span>Unusual match deviations by family</span></div>{tendencies.length ? <div className="family-list">{tendencies.map(item => <div key={item.finding_family}><strong>{metricLabel(item.finding_family)}</strong><span>{item.unusual_matches} unusual matches · {item.finding_count} findings</span><small>{item.above_baseline} above · {item.below_baseline} below baseline · strongest z {item.strongest_robust_z > 0 ? "+" : ""}{item.strongest_robust_z.toFixed(1)}</small></div>)}</div> : <p className="muted">No deviations passed the deterministic evidence threshold.</p>}</section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Match archetypes</h2><span>Rule-based · multi-label · no clustering</span></div><div className="archetype-grid">{archetypes.map(item => <article key={item.archetype} className={item.match_count ? "active" : "empty-archetype"}><small>{metricLabel(item.archetype)}</small><strong>{item.match_count} matches</strong><span>{(item.match_share * 100).toFixed(0)}% of season</span><p>{item.description}</p><em>{item.representative_match_ids.length ? `Examples: ${item.representative_match_ids.join(", ")}` : "No matches met every component threshold"}</em></article>)}</div>{archetypeAssignments.length > 0 && <details className="archetype-evidence"><summary>Representative component evidence</summary>{archetypeAssignments.slice(0, 12).map(item => <div key={item.archetype_id}><strong>{item.title} · Match {item.match_id}</strong><span>{item.contributing_metrics.map(metric => `${metricLabel(metric.metric)} z ${metric.robust_z_score > 0 ? "+" : ""}${metric.robust_z_score.toFixed(2)}`).join(" · ")}</span></div>)}</details>}</section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Metric relationships</h2><span>Robust expectation · unusual residuals only</span></div><table><thead><tr><th>Relationship</th><th>Fitted slope</th><th>Rank association</th><th>Slope sensitivity</th><th>Residual spread</th><th>Coverage</th></tr></thead><tbody>{relationshipFits.map(item => <tr key={`${item.upstream_metric}-${item.downstream_metric}`}><td>{metricLabel(item.upstream_metric)} → {metricLabel(item.downstream_metric)}<small className="table-note">Theil–Sen median pairwise slope</small></td><td>{formatFinite(item.slope, 3)}</td><td>{formatFinite(item.spearman_rank_correlation)}</td><td>{formatFinite(item.slope_leave_one_out_low, 3)}–{formatFinite(item.slope_leave_one_out_high, 3)}<small className="table-note">Leave-one-match-out sensitivity; not a confidence interval</small></td><td>{formatFinite(item.residual_q25)}–{formatFinite(item.residual_q75)}<small className="table-note">Robust scale {formatFinite(item.residual_robust_scale)}</small></td><td>{item.contributing_match_count}/{summary.analysed_match_count}<small className="table-note">{(item.coverage * 100).toFixed(0)}%</small></td></tr>)}</tbody></table><div className="relationship-findings">{relationshipFindings.slice(0, 12).map(item => <article key={item.finding_id}><div><strong>{item.title}</strong><span className={`evidence-band ${item.evidence_level === "strong" ? "established" : "developing"}`}>{item.evidence_level}</span></div><p>Match {item.match_id} · observed {item.observed_downstream_value.toFixed(2)} · expected {item.expected_downstream_value.toFixed(2)} · residual {item.residual > 0 ? "+" : ""}{item.residual.toFixed(2)} · robust z {item.residual_robust_z > 0 ? "+" : ""}{item.residual_robust_z.toFixed(2)}</p><small>Descriptive prediction band: {item.residual_prediction_low.toFixed(2)}–{item.residual_prediction_high.toFixed(2)}</small></article>)}</div></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Most unusual matches</h2><span>Robust distance from this season's median</span></div><table><thead><tr><th>Match</th><th>Strongest observation</th><th>Observed</th><th>Season median</th><th>Robust deviation</th><th>Findings</th></tr></thead><tbody>{unusual.slice(0, 15).map(row => <tr key={String(row.match_id)}><td>Match {row.match_id}<small className="table-note">{row.match_date ?? "Date unavailable"}</small></td><td>{metricLabel(row.strongest_metric)}</td><td>{formatEventMetric(row.observed_value, row.unit)}</td><td>{formatEventMetric(row.season_baseline, row.unit)}</td><td>{row.strongest_robust_z > 0 ? "+" : ""}{row.strongest_robust_z.toFixed(1)}</td><td>{row.meaningful_finding_count}</td></tr>)}</tbody></table></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Deterministic event findings</h2><span>{duplicateCount} correlated duplicates suppressed</span></div><div className="event-finding-list">{findings.slice(0, 20).map(item => <article key={item.finding_id}><div><span className={`evidence-band ${item.evidence_level === "strong" ? "established" : item.evidence_level === "moderate" ? "developing" : "provisional"}`}>{item.evidence_level} evidence</span><small>{metricLabel(item.finding_family)} · Match {item.source_match_id}</small></div><h3>{item.title}</h3><p>{item.description}</p><dl><div><dt>Observed</dt><dd>{formatEventMetric(item.observed_value, item.unit)}</dd></div><div><dt>Season median</dt><dd>{formatEventMetric(item.season_baseline, item.unit)}</dd></div><div><dt>Difference</dt><dd>{item.signed_deviation > 0 ? "+" : ""}{formatEventMetric(item.signed_deviation, item.unit)}</dd></div><div><dt>Absolute deviation</dt><dd>{formatEventMetric(item.absolute_deviation, item.unit)}</dd></div><div><dt>Relative deviation</dt><dd>{item.relative_deviation == null ? "Unavailable" : `${item.relative_deviation > 0 ? "+" : ""}${(item.relative_deviation * 100).toFixed(1)}%`}</dd></div></dl><details><summary>Definition and evidence</summary><p>{item.definition}</p><p>{item.contributing_match_count} contributing matches · {(item.coverage * 100).toFixed(0)}% coverage · robust z {item.robust_z_score.toFixed(2)}</p></details></article>)}</div></section>
  </main>;
}

export function TeamProfilePage({ teamId }: { teamId: string }) {
  const query = new URLSearchParams(window.location.search);
  const eventProvider = query.get("provider");
  const eventCompetition = query.get("competition_id");
  const eventSeason = query.get("season_id");
  const eventMode = Boolean(eventProvider && eventCompetition && eventSeason);
  const technicalMode = query.get("view") === "technical";
  const [summary, setSummary] = useState<TeamProfileSummaryResponse | null>(null);
  const [metrics, setMetrics] = useState<TeamMetricBaseline[]>([]);
  const [families, setFamilies] = useState<Array<{ provider: string; finding_family: string; contributing_matches: number; finding_count: number; match_ids: Array<string | number> }>>([]);
  const [matches, setMatches] = useState<{ included_matches: Array<Record<string, unknown>>; excluded_matches: Array<{ match_id: string | number; provider: string; reason: string }> } | null>(null);
  const [deviations, setDeviations] = useState<TeamDeviation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [eventSummary, setEventSummary] = useState<EventProfileSummary | null>(null);
  const [eventBaselines, setEventBaselines] = useState<EventSeasonBaseline[]>([]);
  const [eventFindings, setEventFindings] = useState<EventProfileFinding[]>([]);
  const [eventTendencies, setEventTendencies] = useState<EventProfileTendency[]>([]);
  const [eventUnusual, setEventUnusual] = useState<EventUnusualMatch[]>([]);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [archetypes, setArchetypes] = useState<MatchArchetypeSummary[]>([]);
  const [archetypeAssignments, setArchetypeAssignments] = useState<MatchArchetypeAssignment[]>([]);
  const [relationshipFits, setRelationshipFits] = useState<MetricRelationshipFit[]>([]);
  const [relationshipFindings, setRelationshipFindings] = useState<MetricRelationshipFinding[]>([]);
  const [eventMatches, setEventMatches] = useState<EventProfileMatch[]>([]);
  const [footballStyle, setFootballStyle] = useState<FootballStyleProfile | null>(null);
  const [footballShape, setFootballShape] = useState<FootballShapeProfile | null>(null);

  useEffect(() => {
    if (eventMode) {
      Promise.all([
        eventProfileApi.footballStyle(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.summary(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.baselines(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.findings(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.tendencies(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.unusualMatches(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.archetypes(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.relationships(eventProvider!, teamId, eventCompetition!, eventSeason!),
        eventProfileApi.matches(eventProvider!, teamId, eventCompetition!, eventSeason!),
      ]).then(([style, s, b, f, t, u, a, r, m]) => { setFootballStyle(style); setEventSummary(s); setEventBaselines(b.season_baselines); setEventFindings(f.findings); setDuplicateCount(f.suppressed_duplicate_count); setEventTendencies(t.recurring_event_profile_tendencies); setEventUnusual(u.unusual_matches); setArchetypes(a.season_summary); setArchetypeAssignments(a.match_assignments); setRelationshipFits(r.relationship_fits); setRelationshipFindings(r.findings); setEventMatches(m.matches); }).catch(reason => setError(String(reason)));
      return;
    }
    Promise.all([
      teamProfileApi.shapeStyle(teamId),
      teamProfileApi.summary(teamId), teamProfileApi.metrics(teamId), teamProfileApi.families(teamId),
      teamProfileApi.matches(teamId), teamProfileApi.deviations(teamId),
    ]).then(([shape, s, m, f, a, d]) => {
      setFootballShape(shape);
      setSummary(s); setMetrics(m.metric_baselines); setFamilies(f.recurring_finding_families);
      setMatches(a); setDeviations(d.match_deviations);
    }).catch(reason => setError(String(reason)));
  }, [teamId, eventMode, eventProvider, eventCompetition, eventSeason]);

  if (error) return <main className="state"><h1>Team Profile unavailable</h1><p>{error}</p></main>;
  if (eventMode) {
    if (!eventSummary || !footballStyle) return <main className="state"><div className="spinner" /><h1>Building Team Style Profile</h1><p>Turning match evidence into football language.</p></main>;
    const base = `/teams/${encodeURIComponent(teamId)}?provider=${encodeURIComponent(eventProvider!)}&competition_id=${encodeURIComponent(eventCompetition!)}&season_id=${encodeURIComponent(eventSeason!)}`;
    return technicalMode
      ? <EventProfileView summary={eventSummary} baselines={eventBaselines} findings={eventFindings} tendencies={eventTendencies} unusual={eventUnusual} matches={eventMatches} archetypes={archetypes} archetypeAssignments={archetypeAssignments} relationshipFits={relationshipFits} relationshipFindings={relationshipFindings} duplicateCount={duplicateCount} />
      : <FootballStyleProfileView profile={footballStyle} matches={eventMatches} technicalHref={`${base}&view=technical`} provider={eventProvider!}/>;
  }
  if (!summary || !matches || !footballShape) return <main className="state"><div className="spinner" /><h1>Building Team Shape Profile</h1><p>Turning observed tracking positions into football language.</p></main>;
  if (!technicalMode) return <FootballShapeProfileView profile={footballShape} technicalHref={`/teams/${encodeURIComponent(teamId)}?view=technical`} />;

  const phase = metrics.filter(row => row.metric_family === "phase_team_shape");
  const lines = metrics.filter(row => row.metric_family === "defensive_line_structure");
  const shots = metrics.filter(row => row.metric_family === "shot_counts");
  const evidenceMessage = summary.profile_evidence_band === "insufficient"
    ? "insufficient for stable team tendencies"
    : `${summary.profile_evidence_band} baseline`;
  const baselineTable = (rows: TeamMetricBaseline[]) => rows.length ? (
    <table>
      <thead><tr><th>Context / metric</th><th>Baseline</th><th>Spread</th><th>Evidence</th><th>Provenance</th></tr></thead>
      <tbody>{rows.map(row => (
        <tr key={`${row.provider}-${row.metric}-${row.possession_status}-${row.tactical_phase}`} className={`evidence-${row.evidence_band}`}>
          <td>{contextLabel(row.possession_status, row.tactical_phase) && <small className="context-label">{contextLabel(row.possession_status, row.tactical_phase)}</small>}{metricLabel(row.metric)}</td>
          <td>{formatMetric(row.median_across_matches, row.unit)}<small className="table-note">{row.baseline_label}</small></td>
          <td>{row.contributing_matches < 3 ? <span className="provisional-spread">Exploratory: {formatMetric(row.q25_across_matches, row.unit)}–{formatMetric(row.q75_across_matches, row.unit)}</span> : `${formatMetric(row.q25_across_matches, row.unit)}–${formatMetric(row.q75_across_matches, row.unit)}`}</td>
          <td><strong className={`evidence-band ${row.evidence_band}`}>{metricLabel(row.evidence_band)}</strong><small className="table-note">{row.contributing_matches} contributing {row.contributing_matches === 1 ? "match" : "matches"}</small></td>
          <td>{provenanceBadge(row.provider_label, row.provenance_label, row.required_capabilities)}</td>
        </tr>
      ))}</tbody>
    </table>
  ) : <p className="muted">Unsupported or no compatible match-level samples.</p>;

  return <main className="shell team-profile">
    <header className="profile-header">
      <div><p className="eyebrow">TactIQ / Team Profile</p><h1>{summary.team.name}</h1><p>{summary.analysed_match_count} analysed matches · {summary.excluded_match_count} excluded</p></div>
      <div className="profile-status"><span className={`evidence-band ${summary.profile_evidence_band}`}>{metricLabel(summary.profile_evidence_band)} evidence</span><small>{summary.profile_baseline_label}; not a historical norm</small><a href="/">Single-match analysis</a></div>
    </header>
    <section className={`profile-caution ${summary.profile_evidence_band}`}><strong>Profile evidence: {summary.analysed_match_count} matches — {evidenceMessage}</strong><span>{summary.analysed_match_count < 3 ? "Values describe the available matches and should not be read as a historical norm." : "Baselines are match-weighted and retain their contributing-match coverage."}</span></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Capability and data coverage</h2><span>{summary.providers.join(", ") || "No provider"}</span></div><div className="coverage-cards">{summary.capability_coverage.map(item => <div key={item.capability}><strong>{metricLabel(item.capability)}</strong><span>{item.available_matches}/{item.included_matches} matches</span><small>{item.providers || "Unavailable"}</small></div>)}</div></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Phase-specific shape comparisons</h2><span>Match-weighted · sample count shown per row</span></div>{baselineTable(phase)}</section>
    <div className="profile-grid"><section className="panel profile-section"><div className="panel-heading"><h2>Defensive line and gaps</h2><span>Direction normalized</span></div>{baselineTable(lines)}</section><section className="panel profile-section"><div className="panel-heading"><h2>Shots for and conceded</h2><span>Counts per match</span></div>{baselineTable(shots)}</section></div>
    <section className="panel profile-section"><div className="panel-heading"><h2>Recurring finding families</h2><span>At least two matches</span></div>{families.length ? <div className="family-list">{families.map(item => <div key={`${item.provider}-${item.finding_family}`}><strong>{metricLabel(item.finding_family)}</strong><span>{item.contributing_matches} matches · {item.finding_count} findings</span><small>{item.provider}</small></div>)}</div> : <p className="muted">No finding family recurred in two compatible matches.</p>}</section>
    <section className="panel profile-section"><div className="panel-heading"><h2>{summary.analysed_match_count < 3 ? "Available match comparisons" : "Largest match deviations"}</h2><span>{summary.analysed_match_count < 3 ? "Exploratory · not a historical ranking" : "From team baseline"}</span></div><table><thead><tr><th>Match</th><th>Context</th><th>Observed</th><th>Comparison</th><th>Difference</th><th>Evidence</th></tr></thead><tbody>{deviations.slice(0, 20).map((row, index) => <tr key={`${row.match_id}-${row.metric}-${index}`}><td><a href={row.match_analysis_path}>{row.link_label}</a><small className="table-note">Match {row.match_id}</small></td><td>{contextLabel(row.possession_status, row.tactical_phase) && <small className="context-label">{contextLabel(row.possession_status, row.tactical_phase)}</small>}{metricLabel(row.metric)}<small className="table-note">{metricLabel(row.deviation_label)}</small></td><td>{formatMetric(row.value, row.unit)}</td><td>{formatMetric(row.team_baseline, row.unit)}<small className="table-note">{row.comparison_label}</small></td><td>{row.deviation_from_baseline > 0 ? "+" : ""}{formatMetric(row.deviation_from_baseline, row.unit)}</td><td><strong className={`evidence-band ${row.evidence_band}`}>{metricLabel(row.evidence_band)}</strong><small className="table-note">{row.contributing_matches} contributing matches</small>{provenanceBadge(row.provider_label, row.provenance_label, row.required_capabilities)}</td></tr>)}</tbody></table></section>
    <section className="panel profile-section"><div className="panel-heading"><h2>Match audit</h2><span>Included / excluded</span></div><p className="muted">Included: {matches.included_matches.map(row => String(row.match_id)).join(", ") || "none"}</p>{matches.excluded_matches.map(row => <p className="profile-warning" key={`${row.provider}-${row.match_id}`}>{row.match_id} · {row.provider}: {row.reason}</p>)}</section>
  </main>;
}
