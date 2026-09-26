import { useEffect, useState } from "react";
import { footballDataApi, liveFootballApi } from "./api";
import type { ApiFootballMatchupPreview, LiveTeam, MatchupPreviewTeam } from "./types";

function Crest({ team }: { team: LiveTeam }) {
  return team.logo_url ? <img src={team.logo_url} alt={`${team.name ?? "Team"} crest`}/> : <span>{(team.name ?? "?").slice(0, 3)}</span>;
}

const statDefinitions = [
  ["possession", "Possession", "%"], ["goals_for", "Goals scored", ""], ["goals_against", "Goals conceded", ""],
  ["shots", "Shots", ""], ["shots_on_target", "Shots on target", ""], ["shots_faced", "Shots faced", ""],
  ["shots_inside_box", "Shots from inside the box", ""], ["pass_accuracy", "Pass completion", "%"], ["corners", "Corners", ""],
] as const;

function value(team: MatchupPreviewTeam, key: string, suffix: string) {
  const number = team.averages[key];
  return number === null || number === undefined ? "—" : `${number.toFixed(1)}${suffix}`;
}

function Form({ team }: { team: MatchupPreviewTeam }) {
  return <div className="preview-form" aria-label={`${team.team.name} recent form`}>{team.form.split("").map((result, index) => <span className={result.toLowerCase()} key={index}>{result}</span>)}</div>;
}

function TeamRecent({ team }: { team: MatchupPreviewTeam }) {
  return <section className="preview-recent-team"><header><Crest team={team.team}/><div><h3>{team.team.name}</h3><p>{team.manager.name}{team.manager.start_date ? ` · since ${team.manager.start_date}` : ""}</p></div><Form team={team}/></header><div className="preview-record"><strong>{team.record.wins}W</strong><strong>{team.record.draws}D</strong><strong>{team.record.losses}L</strong>{team.most_common_formation && <span>Usually listed as {team.most_common_formation}</span>}</div><div className="preview-match-list">{team.recent_matches.map(match => <div key={match.fixture_id}><span className={match.result.toLowerCase()}>{match.result}</span><time>{new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(`${match.date}T12:00:00`))}</time><Crest team={match.opponent}/><strong>{match.opponent.name}</strong><b>{match.goals_for}–{match.goals_against}</b><small>{match.venue}{match.formation ? ` · ${match.formation}` : ""}</small></div>)}</div></section>;
}

export function MatchupPreviewPage({ fixtureId, provider = "api-football" }: { fixtureId: number; provider?: "api-football" | "football-data" }) {
  const [preview, setPreview] = useState<ApiFootballMatchupPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { const api = provider === "football-data" ? footballDataApi : liveFootballApi; api.matchupPreview(fixtureId).then(setPreview).catch(reason => setError(reason instanceof Error ? reason.message : String(reason))); }, [fixtureId, provider]);
  if (error) return <main className="preview-state"><a href="/">← Match centre</a><h1>Matchup preview unavailable</h1><p>{error}</p><p>Check that the corresponding football-data connection is configured and that this competition provides recent results.</p></main>;
  if (!preview) return <main className="preview-state"><h1>Preparing the matchup</h1><p>Reading each team's recent matches under the current manager…</p></main>;
  const [home, away] = preview.teams;
  return <main className="matchup-preview">
    <nav className="preview-nav"><a href="/">← Choose another match</a><strong><span>TACT</span>IQ MATCHUP</strong>{provider === "api-football" ? <a href={`/live?fixture=${fixtureId}`}>Match centre →</a> : <a href="/#fixture-browser">Fixture browser →</a>}</nav>
    <header className="preview-scoreboard"><div className="preview-competition">{preview.fixture.competition.name} · {preview.fixture.competition.round}</div><div className="preview-teams"><section><Crest team={home.team}/><h1>{home.team.name}</h1><p>{home.manager.name}</p></section><div><span>PRE-MATCH</span><strong>VS</strong><time>{preview.fixture.kickoff ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(preview.fixture.kickoff)) : "Date unavailable"}</time></div><section><Crest team={away.team}/><h1>{away.team.name}</h1><p>{away.manager.name}</p></section></div></header>

    <section className="preview-intro"><span>Recent evidence briefing</span><h2>How have these teams been playing?</h2><p>This comparison uses each side's latest completed league matches. When a current manager's start date is verified, the sample is limited to that tenure. It describes what has happened recently; it does not predict the result.</p></section>

    <section className="preview-section"><header><span>1</span><div><h2>The recent matches</h2><p>See the exact games behind this briefing.</p></div></header><div className="preview-recent-grid"><TeamRecent team={home}/><TeamRecent team={away}/></div></section>

    <section className="preview-section"><header><span>2</span><div><h2>How each team has looked</h2><p>Football language first, with the supporting numbers kept nearby.</p></div></header><div className="playing-read-grid">{[home, away].map(team => <article key={team.team.team_id}><div className="playing-read-title"><Crest team={team.team}/><h3>{team.team.name}</h3></div><div><small>With the ball</small><p>{team.football_read.control}</p></div><div><small>Turning play into chances</small><p>{team.football_read.attacking_output}</p></div><div><small>What opponents have produced</small><p>{team.football_read.defensive_exposure}</p></div></article>)}</div></section>

    <section className="preview-section"><header><span>3</span><div><h2>The basic numbers</h2><p>Per-match averages from the recent matches listed above.</p></div></header><div className="preview-stat-table"><div className="stat-table-head"><strong>{home.team.name}</strong><span>Recent average</span><strong>{away.team.name}</strong></div>{statDefinitions.map(([key,label,suffix]) => <div className="stat-comparison" key={key}><strong>{value(home,key,suffix)}</strong><span>{label}</span><strong>{value(away,key,suffix)}</strong></div>)}</div><p className="preview-note">{preview.basic_stats_note}</p></section>

    <section className="preview-section matchup-questions"><header><span>4</span><div><h2>What to watch in this matchup</h2><p>Evidence-backed questions—not predictions or instructions.</p></div></header><div>{preview.matchup_read.length ? preview.matchup_read.map((item,index) => <article key={item.title}><b>{String(index + 1).padStart(2,"0")}</b><div><h3>{item.title}</h3><p>{item.explanation}</p><details><summary>Why TactIQ says this</summary><pre>{JSON.stringify(item.evidence,null,2)}</pre></details></div></article>) : <p className="preview-note">The available recent-match statistics do not support a clear matchup contrast yet.</p>}</div></section>

    <section className="preview-limitations"><h2>What this briefing cannot see</h2><ul>{preview.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>{preview.request_efficiency}</p></section>
  </main>;
}
