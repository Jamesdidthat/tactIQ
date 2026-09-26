import { useEffect, useMemo, useRef, useState } from "react";
import { opponentComparisonApi, profileCatalogApi } from "./api";
import { EvidencePackView } from "./OpponentComparisonPage";
import { metricLabel } from "./presentation";
import type { EventProfileCatalogItem, PreMatchBriefing, PreMatchBriefingPriority } from "./types";

const identityFields = ["provider", "team_id", "competition_id", "season_id"] as const;
const identityKey = (item: EventProfileCatalogItem) => [item.provider, item.competition_id, item.season_id].join("|");
const competitionKey = (item: EventProfileCatalogItem) => [item.provider, item.competition_id].join("|");
const uniqueBy = <T,>(items: T[], key: (item: T) => string) => Array.from(new Map(items.map(item => [key(item), item])).values());

function BriefingSetup({ query }: { query: URLSearchParams }) {
  const [profiles, setProfiles] = useState<EventProfileCatalogItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const initialCompetition = [query.get("target_provider"), query.get("target_competition_id")].filter(Boolean).join("|");
  const initialSeason = [query.get("target_provider"), query.get("target_competition_id"), query.get("target_season_id")].filter(Boolean).join("|");
  const [selectedCompetition, setSelectedCompetition] = useState(initialCompetition);
  const [selectedSeason, setSelectedSeason] = useState(initialSeason);
  const [targetId, setTargetId] = useState(query.get("target_team_id") ?? "");
  const [opponentId, setOpponentId] = useState(query.get("opponent_team_id") ?? "");

  useEffect(() => {
    profileCatalogApi.list().then(response => setProfiles(response.profiles)).catch(reason => setError(String(reason)));
  }, []);
  const competitions = useMemo(() => uniqueBy(profiles, competitionKey), [profiles]);
  const activeCompetition = selectedCompetition || (competitions[0] ? competitionKey(competitions[0]) : "");
  const seasons = useMemo(() => uniqueBy(profiles.filter(item => competitionKey(item) === activeCompetition), identityKey), [profiles, activeCompetition]);
  const activeSeason = seasons.some(item => identityKey(item) === selectedSeason) ? selectedSeason : (seasons[0] ? identityKey(seasons[0]) : "");
  const teams = profiles.filter(item => identityKey(item) === activeSeason);
  const target = teams.find(item => String(item.team_id) === targetId) ?? teams[0];
  const opponentChoices = teams.filter(item => String(item.team_id) !== String(target?.team_id));
  const opponent = opponentChoices.find(item => String(item.team_id) === opponentId) ?? opponentChoices[0];

  if (error) return <main className="state"><h1>Matchup choices unavailable</h1><p>{error}</p><button type="button" onClick={() => window.location.reload()}>Try again</button></main>;
  if (!profiles.length) return <main className="state"><div className="spinner"/><h1>Loading available team profiles</h1><p>Finding competitions, seasons, and teams ready for comparison.</p></main>;
  return <main className="shell opponent-setup">
    <header className="profile-header"><div><p className="eyebrow">TactIQ / Pre-match</p><h1>Pre-Match Briefing</h1><p>Choose two available team-season profiles. No IDs or URL editing required.</p></div></header>
    <form method="get" action="/pre-match-briefing" className="panel briefing-selector-form">
      <label>Competition<select value={activeCompetition} onChange={event => { setSelectedCompetition(event.target.value); setSelectedSeason(""); setTargetId(""); setOpponentId(""); }}>{competitions.map(item => <option key={competitionKey(item)} value={competitionKey(item)}>{item.competition_name ?? `Competition ${item.competition_id}`}</option>)}</select></label>
      <label>Season<select value={activeSeason} onChange={event => { setSelectedSeason(event.target.value); setTargetId(""); setOpponentId(""); }}>{seasons.map(item => <option key={identityKey(item)} value={identityKey(item)}>{item.season_name ?? `Season ${item.season_id}`}</option>)}</select></label>
      <label>Target team<select value={String(target?.team_id ?? "")} onChange={event => { setTargetId(event.target.value); if (event.target.value === opponentId) setOpponentId(""); }}>{teams.map(item => <option key={String(item.team_id)} value={String(item.team_id)}>{item.team_name} · {item.analysed_match_count} matches</option>)}</select></label>
      <label>Opponent<select value={String(opponent?.team_id ?? "")} onChange={event => setOpponentId(event.target.value)}>{opponentChoices.map(item => <option key={String(item.team_id)} value={String(item.team_id)}>{item.team_name} · {item.analysed_match_count} matches</option>)}</select></label>
      {target && opponent && <>
        <input type="hidden" name="target_provider" value={target.provider}/><input type="hidden" name="target_team_id" value={target.team_id}/><input type="hidden" name="target_competition_id" value={target.competition_id}/><input type="hidden" name="target_season_id" value={target.season_id}/>
        <input type="hidden" name="opponent_provider" value={opponent.provider}/><input type="hidden" name="opponent_team_id" value={opponent.team_id}/><input type="hidden" name="opponent_competition_id" value={opponent.competition_id}/><input type="hidden" name="opponent_season_id" value={opponent.season_id}/>
      </>}
      <button type="submit" disabled={!target || !opponent}>Build briefing</button>
    </form>
  </main>;
}

const footballEvidenceSummary = (summary: string) => summary
  .replaceAll("defensive-exposure median", "usual conceded median")
  .replace("the season interquartile ranges have limited overlap.", "their usual match ranges overlap only slightly.")
  .replace("the season interquartile ranges materially overlap.", "their usual match ranges overlap.");

export function PreMatchBriefingPage() {
  const [locationSearch, setLocationSearch] = useState(window.location.search);
  const query = useMemo(() => new URLSearchParams(locationSearch), [locationSearch]);
  const target = identityFields.map(field => query.get(`target_${field}`) ?? "");
  const opponent = identityFields.map(field => query.get(`opponent_${field}`) ?? "");
  const targetKey = target.join("|");
  const opponentKey = opponent.join("|");
  const complete = [...target, ...opponent].every(Boolean);
  const requestedPriorityId = query.get("priority");
  const requestedMomentId = query.get("moment");
  const [briefing, setBriefing] = useState<PreMatchBriefing | null>(null);
  const [selectedPriority, setSelectedPriority] = useState<PreMatchBriefingPriority | null>(null);
  const [error, setError] = useState<string | null>(null);
  const briefingScroll = useRef(0);

  useEffect(() => {
    const restore = () => setLocationSearch(window.location.search);
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (!complete) return;
    setBriefing(null); setError(null); setSelectedPriority(null);
    opponentComparisonApi.briefing(target, opponent).then(response => setBriefing(response.briefing)).catch(reason => setError(String(reason)));
  }, [complete, targetKey, opponentKey]);
  useEffect(() => {
    if (briefing) setSelectedPriority(briefing.review_priorities.find(item => item.priority_id === requestedPriorityId) ?? null);
  }, [briefing, requestedPriorityId]);

  const setDrilldown = (priorityId: string | null, momentId: string | null) => {
    const url = new URL(window.location.href);
    if (priorityId) url.searchParams.set("priority", priorityId); else url.searchParams.delete("priority");
    if (priorityId && momentId) url.searchParams.set("moment", momentId); else url.searchParams.delete("moment");
    window.history.pushState({}, "", url);
    setLocationSearch(url.search);
  };
  const openPriority = (priority: PreMatchBriefingPriority) => {
    briefingScroll.current = window.scrollY;
    setSelectedPriority(priority);
    setDrilldown(priority.priority_id, null);
  };
  const closeEvidencePack = () => {
    setSelectedPriority(null);
    setDrilldown(null, null);
    window.requestAnimationFrame(() => window.scrollTo({ top: briefingScroll.current, behavior: "smooth" }));
  };

  if (!complete) return <BriefingSetup query={query}/>;
  if (error) return <main className="state"><h1>Pre-Match Briefing unavailable</h1><p>{error}</p><a href="/pre-match-briefing">Choose another matchup</a></main>;
  if (!briefing) return <main className="state"><div className="spinner"/><h1>Building Pre-Match Briefing</h1><p>Organizing the selected review evidence without generating new claims.</p></main>;
  const competition = briefing.competition.shared ? briefing.competition.target.name ?? "Competition unavailable" : "Different competition contexts";
  const season = briefing.season.shared ? briefing.season.target.name ?? "Season unavailable" : "Different season contexts";
  const comparisonQuery = new URLSearchParams([...query].filter(([key]) => !["priority", "moment"].includes(key))).toString();

  return <main className="shell pre-match-briefing">
    <header className="briefing-header"><div><p className="eyebrow">TactIQ / Pre-match briefing</p><h1>{briefing.target_team.team_name} <span>vs</span> {briefing.opponent_team.team_name}</h1><p>{competition} · {season}</p></div><div className="briefing-header-actions"><a href="/pre-match-briefing">Change matchup</a><a href={`/opponent-comparison?${comparisonQuery}`}>Open full comparison</a><a href={`/pre-match-briefing/print?${comparisonQuery}`}>Print / Export briefing</a></div></header>
    <section className="briefing-executive panel"><small>Executive summary</small><h2>{briefing.briefing_summary}</h2><p>Deterministic summary of selected evidence only.</p></section>
    <section className="briefing-priorities panel">
      <div className="panel-heading"><div><p className="eyebrow">Review index</p><h2>Ranked Review Priorities</h2></div><span>{briefing.review_priorities.length} qualified theme{briefing.review_priorities.length === 1 ? "" : "s"}</span></div>
      {briefing.review_priorities.length === 0 && <div className="review-priority-empty"><strong>No review themes passed the evidence threshold.</strong><span>This does not mean the matchup lacks important tactical questions.</span></div>}
      <div className="briefing-priority-list">{briefing.review_priorities.map(priority => <article key={priority.priority_id} aria-current={selectedPriority?.priority_id === priority.priority_id ? "true" : undefined}><span>{priority.rank}</span><div><div className="review-priority-meta"><small>{metricLabel(priority.direction)} · {metricLabel(priority.primary_source_role)}</small><b>Evidence support: {priority.evidence_support}</b></div><h3>{priority.title}</h3><p className="briefing-question">{priority.review_question}</p><p>{footballEvidenceSummary(priority.evidence_summary)}</p><button type="button" onClick={() => openPriority(priority)}>Open Evidence Pack</button></div></article>)}</div>
      {selectedPriority && <EvidencePackView priority={selectedPriority} target={target} opponent={opponent} initialEventId={requestedMomentId} onMomentChange={eventId => setDrilldown(selectedPriority.priority_id, eventId)} onClose={closeEvidencePack} closeLabel="Back to briefing"/>}
    </section>
    <section className="briefing-coverage panel">
      <div><small>Data coverage</small><h2>{briefing.data_capabilities.comparable ? "Comparable season event profiles" : "Data contexts are not directly comparable"}</h2><p>{briefing.target_team.analysed_match_count} {briefing.target_team.team_name} matches · {briefing.opponent_team.analysed_match_count} {briefing.opponent_team.team_name} matches.</p><p>Event evidence is available. Continuous player tracking was not used.</p></div>
      <div><small>Video availability</small><h2>{metricLabel(briefing.video_availability.status)}</h2><p>{briefing.video_availability.message}</p></div>
      <details className="briefing-technical"><summary>Technical provenance</summary><p>Providers: {briefing.target_team.provider} · {briefing.opponent_team.provider}</p><p>Team IDs: {briefing.target_team.team_id} · {briefing.opponent_team.team_id}</p><p>Coordinate system: {briefing.data_capabilities.coordinate_system ?? "Unavailable"}</p><p>Required capabilities: {briefing.data_capabilities.required_capabilities.join(", ") || "None"}</p></details>
    </section>
    <section className="briefing-limitations panel"><small>Limitations</small>{briefing.limitations.map(item => <p key={item}>{item}</p>)}</section>
  </main>;
}
