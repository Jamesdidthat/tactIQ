import { useCallback, useEffect, useState } from "react";
import { liveFootballApi } from "./api";
import type { LiveFixture, LiveFixtureSnapshot, LiveFootballStatus, LiveTeam } from "./types";

function Crest({ team }: { team: LiveTeam }) {
  return team.logo_url
    ? <img className="live-crest" src={team.logo_url} alt={`${team.name ?? "Team"} crest`} />
    : <span className="live-crest fallback">{(team.name ?? "?").slice(0, 3).toUpperCase()}</span>;
}

function clockLabel(fixture: LiveFixture) {
  if (fixture.status.is_live) return `${fixture.status.elapsed ?? ""}${fixture.status.extra ? `+${fixture.status.extra}` : ""}'`;
  if (fixture.status.short === "NS" && fixture.kickoff) return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(fixture.kickoff));
  return fixture.status.short ?? fixture.status.long ?? "—";
}

function FixtureCard({ fixture, selected, onOpen }: { fixture: LiveFixture; selected: boolean; onOpen: () => void }) {
  return <button className={`live-fixture-card ${selected ? "selected" : ""}`} onClick={onOpen}>
    <div className="live-fixture-meta"><span>{fixture.competition.name ?? "Competition"}</span><b className={fixture.status.is_live ? "live-pill" : ""}>{clockLabel(fixture)}</b></div>
    <div className="live-fixture-team"><Crest team={fixture.home_team}/><strong>{fixture.home_team.name ?? "Home"}</strong><em>{fixture.goals.home ?? "–"}</em></div>
    <div className="live-fixture-team"><Crest team={fixture.away_team}/><strong>{fixture.away_team.name ?? "Away"}</strong><em>{fixture.goals.away ?? "–"}</em></div>
    <small>{fixture.competition.round ?? fixture.venue.name ?? "Match details"}</small>
  </button>;
}

function FixtureDetail({ snapshot }: { snapshot: LiveFixtureSnapshot }) {
  const fixture = snapshot.fixture;
  return <article className="live-match-detail">
    <header>
      <span>{fixture.competition.name} · {fixture.competition.round}</span>
      <div><Crest team={fixture.home_team}/><strong>{fixture.home_team.name}</strong><b>{fixture.goals.home ?? "–"} — {fixture.goals.away ?? "–"}</b><strong>{fixture.away_team.name}</strong><Crest team={fixture.away_team}/></div>
      <p>{fixture.status.long}{fixture.status.elapsed ? ` · ${fixture.status.elapsed}'` : ""}</p>
    </header>
    <section><h2>Match incidents</h2>{snapshot.events.length ? <ol className="live-events">{snapshot.events.map((event, index) => <li key={`${event.elapsed}-${event.type}-${index}`}><time>{event.elapsed ?? "–"}'</time><span><strong>{event.detail ?? event.type}</strong><small>{String(event.player.name ?? event.team.name ?? "")}</small></span></li>)}</ol> : <p className="live-empty">No incident timeline is currently available for this match.</p>}</section>
    <section><h2>Match statistics</h2>{snapshot.team_statistics.length ? <div className="live-stat-columns">{snapshot.team_statistics.map(team => <div key={String(team.team.team_id)}><h3><Crest team={team.team}/>{team.team.name}</h3>{team.statistics.map(stat => <p key={String(stat.label)}><span>{stat.label}</span><strong>{String(stat.value ?? "—")}</strong></p>)}</div>)}</div> : <p className="live-empty">Team statistics are not available yet or are not covered for this competition.</p>}</section>
    <section><h2>Lineups</h2>{snapshot.lineups.length ? <div className="live-lineups">{snapshot.lineups.map(team => <div key={String(team.team.team_id)}><h3>{team.team.name} <span>{team.formation}</span></h3>{team.starting_xi.map((player, index) => <p key={String(player.id ?? index)}><b>{String(player.number ?? "")}</b>{String(player.name ?? "Player")}</p>)}</div>)}</div> : <p className="live-empty">Lineups are not available yet or are not covered for this competition.</p>}</section>
    <aside className="live-scope"><strong>What TactIQ can say from this feed</strong><p>{snapshot.analysis_scope}</p>{snapshot.warnings.map(warning => <small key={warning}>{warning}</small>)}</aside>
  </article>;
}

export function LiveMatchesPage() {
  const params = new URLSearchParams(window.location.search);
  const initialFixture = Number(params.get("fixture")) || null;
  const [status, setStatus] = useState<LiveFootballStatus | null>(null);
  const [mode, setMode] = useState<"live" | "today">("live");
  const [fixtures, setFixtures] = useState<LiveFixture[]>([]);
  const [selected, setSelected] = useState<number | null>(initialFixture);
  const [snapshot, setSnapshot] = useState<LiveFixtureSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadFixtures = useCallback(() => {
    setLoading(true); setError(null);
    liveFootballApi.fixtures(mode === "live" ? { live: "all" } : { date: new Date().toISOString().slice(0, 10) }).then(value => setFixtures(value.fixtures)).catch(reason => setError(reason instanceof Error ? reason.message : String(reason))).finally(() => setLoading(false));
  }, [mode]);

  useEffect(() => { liveFootballApi.status().then(setStatus).catch(reason => setError(String(reason))); }, []);
  useEffect(() => { if (status?.configured) loadFixtures(); else if (status) setLoading(false); }, [status, loadFixtures]);
  useEffect(() => { if (!status?.configured || mode !== "live") return; const timer = window.setInterval(loadFixtures, 180_000); return () => window.clearInterval(timer); }, [status, mode, loadFixtures]);
  useEffect(() => { if (!selected || !status?.configured) return; setDetailLoading(true); setSnapshot(null); liveFootballApi.fixture(selected).then(setSnapshot).catch(reason => setError(reason instanceof Error ? reason.message : String(reason))).finally(() => setDetailLoading(false)); }, [selected, status]);

  const open = (fixtureId: number) => { setSelected(fixtureId); window.history.replaceState({}, "", `/live?fixture=${fixtureId}`); };
  return <main className="live-shell">
    <nav className="live-topbar"><a href="/matches/2017461/overview">← TactIQ analysis</a><strong><span>TACT</span>IQ LIVE</strong><button onClick={loadFixtures} disabled={!status?.configured || loading}>Refresh</button></nav>
    <header className="live-hero"><span className="live-kicker">Live football</span><h1>Follow today's matches</h1><p>Scores, incidents, lineups and match statistics—connected to TactIQ without pretending this feed contains tracking data.</p></header>
    {!status ? <section className="live-state">Checking live-data access…</section> : !status.configured ? <section className="live-setup"><h2>Connect API-Football</h2><p>The integration is installed, but the backend key is not configured. Set <code>TACTIQ_API_FOOTBALL_KEY</code> in the terminal that starts the API, then restart it.</p><p>Keep the key on the backend. Never add it to a <code>VITE_*</code> variable or frontend file.</p></section> : <>
      <div className="live-tabs"><button className={mode === "live" ? "active" : ""} onClick={() => { setMode("live"); setSelected(null); setSnapshot(null); }}>Live now</button><button className={mode === "today" ? "active" : ""} onClick={() => { setMode("today"); setSelected(null); setSnapshot(null); }}>Today's fixtures</button></div>
      {error && <section className="live-state error"><h2>Live data unavailable</h2><p>{error}</p></section>}
      <div className="live-layout"><section className="live-fixture-list">{loading ? <div className="live-state">Updating matches…</div> : fixtures.length ? fixtures.map(fixture => <FixtureCard key={fixture.fixture_id} fixture={fixture} selected={selected === fixture.fixture_id} onOpen={() => open(fixture.fixture_id)}/>) : <div className="live-state"><h2>{mode === "live" ? "No matches are live" : "No covered fixtures found"}</h2><p>Coverage depends on the API plan, competition and available season.</p></div>}</section><section>{detailLoading ? <div className="live-state">Loading match details…</div> : snapshot ? <FixtureDetail snapshot={snapshot}/> : <div className="live-state live-prompt"><h2>Select a match</h2><p>Open a fixture to inspect its incidents, team statistics and available lineups.</p></div>}</section></div>
    </>}
  </main>;
}
