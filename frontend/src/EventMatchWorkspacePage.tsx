import { useEffect, useState } from "react";
import { eventProfileApi } from "./api";
import { FootballIcon, TeamBadge } from "./FootballVisuals";
import { MatchTacticalAnalysisView } from "./MatchTacticalAnalysisView";
import type { MatchAnalysisSection } from "./MatchTacticalAnalysisView";
import type { MatchTacticalProfile, TeamHeader } from "./types";

type Section = MatchAnalysisSection | "evidence";
const sections: { id: Section; label: string; description: string; icon: "overview" | "flow" | "teams" | "goal" | "evidence" }[] = [
  { id: "overview", label: "Overview", description: "The quickest read of the match", icon: "overview" },
  { id: "flow", label: "Match flow", description: "When control and threat changed", icon: "flow" },
  { id: "teams", label: "Team analysis", description: "How each side differed from normal", icon: "teams" },
  { id: "goals", label: "Goals", description: "How every goal developed", icon: "goal" },
  { id: "evidence", label: "Evidence", description: "Coverage, measurements and limitations", icon: "evidence" },
];

const text = (value: unknown, fallback: string) => value == null ? fallback : String(value);
const score = (value: unknown) => typeof value === "number" ? value : "–";

export function EventMatchWorkspacePage({ provider, teamId, competitionId, seasonId, matchId, section }: { provider: string; teamId: string; competitionId: string; seasonId: string; matchId: string; section: Section }) {
  const [profile, setProfile] = useState<MatchTacticalProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { eventProfileApi.matchTacticalAnalysis(provider, teamId, competitionId, seasonId, matchId).then(setProfile).catch(reason => setError(reason instanceof Error ? reason.message : String(reason))); }, [provider, teamId, competitionId, seasonId, matchId]);
  if (error) return <main className="state"><h1>Match analysis unavailable</h1><p>{error}</p></main>;
  if (!profile) return <main className="state"><div className="spinner"/><h1>Preparing match workspace</h1><p>Separating match flow, team analysis, goals and evidence.</p></main>;

  const identity = profile.match_identity;
  const homeId = text(identity.home_team_id, "home");
  const awayId = text(identity.away_team_id, "away");
  const homeProfile = profile.team_profiles.find(team => String(team.team_id) === homeId) ?? profile.team_profiles[0];
  const awayProfile = profile.team_profiles.find(team => String(team.team_id) === awayId) ?? profile.team_profiles[1];
  const teamHeader = (name: string, id: string | number): TeamHeader => ({ team_id: id, name, code: name.split(/\s+/).map(word => word[0]).join("").slice(0, 3).toUpperCase(), score: null, crest_url: null });
  const home = teamHeader(homeProfile?.team_name ?? "Home", homeId);
  const away = teamHeader(awayProfile?.team_name ?? "Away", awayId);
  const base = `/event-matches/${encodeURIComponent(provider)}/${encodeURIComponent(teamId)}/${encodeURIComponent(competitionId)}/${encodeURIComponent(seasonId)}/${encodeURIComponent(matchId)}`;
  const profileHref = `/teams/${encodeURIComponent(teamId)}?provider=${encodeURIComponent(provider)}&competition_id=${encodeURIComponent(competitionId)}&season_id=${encodeURIComponent(seasonId)}`;
  return <main className="shell match-workspace">
    <header className="football-scoreboard"><div className="scoreboard-meta"><span>Match analysis</span><time>{text(identity.date, "Date unavailable")}</time></div><div className="scoreboard-teams"><div className="scoreboard-team home"><TeamBadge team={home}/><div><strong>{home.name}</strong><small>Home</small></div></div><div className="scoreboard-score"><strong>{score(identity.home_score)}</strong><span>FT</span><strong>{score(identity.away_score)}</strong></div><div className="scoreboard-team away"><div><strong>{away.name}</strong><small>Away</small></div><TeamBadge team={away} side="away"/></div></div><div className="scoreboard-foot"><span>Event-backed match view</span><details><summary>Data source</summary><p>{provider.replaceAll("_", " ")} · no continuous tracking</p></details></div></header>
    <nav className="match-workspace-nav" aria-label="Match analysis sections">{sections.map(item => <a href={`${base}/${item.id}`} className={section === item.id ? "active" : ""} key={item.id}><FootballIcon name={item.icon}/><span><strong>{item.label}</strong><small>{item.description}</small></span></a>)}</nav>
    {section !== "evidence" && <MatchTacticalAnalysisView profile={profile} section={section} loading={false} error={null}/>} 
    {section === "overview" && <section className="match-directory"><header><small>Explore the match</small><h2>Choose what you want to understand</h2><p>Each page answers one football question.</p></header><div>{sections.filter(item => item.id !== "overview").map(item => <a href={`${base}/${item.id}`} key={item.id}><FootballIcon name={item.icon}/><span><strong>{item.label}</strong><small>{item.description}</small>{item.id === "goals" && <em>{profile.goals.length} available</em>}</span><b>Open →</b></a>)}</div></section>}
    {section === "evidence" && <section className="evidence-workspace"><header className="match-section-intro"><div><small>Evidence room</small><h2>Coverage and analytical limits</h2></div><p>This is where technical provenance lives. The football pages stay focused on what happened.</p></header><div className="event-evidence-cards">{Object.entries(profile.analysis_coverage).map(([key, value]) => <article key={key}><strong>{key.replaceAll("_", " ")}</strong><span>{value}</span></article>)}</div><section className="panel event-evidence-notes"><h3>Important limitations</h3>{profile.limitations.map(item => <p key={item}>{item}</p>)}<a href={profileHref}>Open the team's season profile and definitions →</a></section></section>}
  </main>;
}
