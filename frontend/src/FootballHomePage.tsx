import { useEffect, useMemo, useState } from "react";
import { footballDataApi, liveFootballApi, profileCatalogApi, teamProfileApi } from "./api";
import { FootballIcon } from "./FootballVisuals";
import type { CurrentCompetition, EventProfileCatalogItem, FootballDataStatus, LiveFixture, LiveFootballStatus, LiveTeam, TrackingTeamProfileCatalogItem } from "./types";

const POPULAR_LIVE_LEAGUES = new Map([[2, 0], [39, 1], [140, 2], [135, 3], [78, 4], [61, 5], [3, 6]]);
const POPULAR_COMPETITIONS = new Map([["PL", 0], ["CL", 1], ["PD", 2], ["BL1", 3], ["SA", 4], ["FL1", 5], ["ELC", 6]]);

function Crest({ team }: { team: LiveTeam }) {
  return team.logo_url
    ? <img className="home-team-crest" src={team.logo_url} alt={`${team.name ?? "Team"} crest`} />
    : <span className="home-team-crest fallback">{(team.name ?? "?").split(/\s+/).map(value => value[0]).join("").slice(0, 3)}</span>;
}

function kickoff(fixture: LiveFixture) {
  if (fixture.status.is_live) return `${fixture.status.elapsed ?? ""}${fixture.status.extra ? `+${fixture.status.extra}` : ""}' LIVE`;
  if (fixture.status.short !== "NS") return fixture.status.short ?? fixture.status.long ?? "—";
  return fixture.kickoff ? new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(fixture.kickoff)) : "Time unavailable";
}

function FixtureCard({ fixture, provider }: { fixture: LiveFixture; provider: "api-football" | "football-data" }) {
  const target = provider === "football-data" ? `/matchup-preview/football-data/${fixture.fixture_id}` : `/live?fixture=${fixture.fixture_id}`;
  return <a className="home-fixture" href={target}>
    <div className="home-fixture-top"><span>{fixture.competition.name}</span><b className={fixture.status.is_live ? "is-live" : ""}>{kickoff(fixture)}</b></div>
    <div><span><Crest team={fixture.home_team}/><strong>{fixture.home_team.name ?? "Home"}</strong></span><em>{fixture.goals.home ?? "–"}</em></div>
    <div><span><Crest team={fixture.away_team}/><strong>{fixture.away_team.name ?? "Away"}</strong></span><em>{fixture.goals.away ?? "–"}</em></div>
    <footer><span>{fixture.competition.round ?? "Fixture"}</span><b>{provider === "football-data" ? "Preview matchup →" : "Open match centre →"}</b></footer>
  </a>;
}

export function FootballHomePage() {
  const [liveStatus, setLiveStatus] = useState<LiveFootballStatus | null>(null);
  const [currentStatus, setCurrentStatus] = useState<FootballDataStatus | null>(null);
  const [liveFixtures, setLiveFixtures] = useState<LiveFixture[]>([]);
  const [competitions, setCompetitions] = useState<CurrentCompetition[]>([]);
  const [competitionCode, setCompetitionCode] = useState("PL");
  const [teams, setTeams] = useState<LiveTeam[]>([]);
  const [teamId, setTeamId] = useState("all");
  const [fixtures, setFixtures] = useState<LiveFixture[]>([]);
  const [fixtureView, setFixtureView] = useState<"upcoming" | "results" | "all">("upcoming");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [styleProfiles, setStyleProfiles] = useState<EventProfileCatalogItem[]>([]);
  const [shapeProfiles, setShapeProfiles] = useState<TrackingTeamProfileCatalogItem[]>([]);
  const [styleProfileKey, setStyleProfileKey] = useState("");
  const [shapeTeamId, setShapeTeamId] = useState("");

  useEffect(() => {
    liveFootballApi.status().then(setLiveStatus).catch(reason => setLiveError(String(reason)));
    footballDataApi.status().then(setCurrentStatus).catch(reason => setError(String(reason)));
    profileCatalogApi.list().then(result => {
      const ordered = [...result.profiles].sort((a, b) => b.analysed_match_count - a.analysed_match_count || a.team_name.localeCompare(b.team_name));
      setStyleProfiles(ordered);
      if (ordered[0]) setStyleProfileKey([ordered[0].provider, ordered[0].team_id, ordered[0].competition_id, ordered[0].season_id].join("|"));
    }).catch(() => undefined);
    teamProfileApi.catalog().then(result => {
      setShapeProfiles(result.profiles);
      if (result.profiles[0]) setShapeTeamId(String(result.profiles[0].team_id));
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!liveStatus?.configured) return;
    liveFootballApi.fixtures({ live: "all" }).then(value => {
      const ordered = [...value.fixtures].sort((a, b) => {
        const left = POPULAR_LIVE_LEAGUES.get(a.competition.league_id ?? -1) ?? 99;
        const right = POPULAR_LIVE_LEAGUES.get(b.competition.league_id ?? -1) ?? 99;
        return left - right || String(a.kickoff).localeCompare(String(b.kickoff));
      });
      setLiveFixtures(ordered);
    }).catch(reason => setLiveError(reason instanceof Error ? reason.message : String(reason)));
  }, [liveStatus?.configured]);

  useEffect(() => {
    if (!currentStatus?.configured) return;
    footballDataApi.competitions().then(value => {
      const ordered = [...value.competitions].sort((a, b) => (POPULAR_COMPETITIONS.get(a.code) ?? 99) - (POPULAR_COMPETITIONS.get(b.code) ?? 99) || a.name.localeCompare(b.name));
      setCompetitions(ordered);
      if (!ordered.some(item => item.code === competitionCode) && ordered[0]) setCompetitionCode(ordered[0].code);
    }).catch(reason => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [currentStatus?.configured]);

  const selectedCompetition = competitions.find(item => item.code === competitionCode);
  useEffect(() => {
    if (!currentStatus?.configured || !competitionCode) return;
    setLoading(true); setError(null); setTeamId("all");
    Promise.all([footballDataApi.fixtures(competitionCode), footballDataApi.teams(competitionCode)])
      .then(([fixtureResult, teamResult]) => { setFixtures(fixtureResult.fixtures); setTeams(teamResult.teams); })
      .catch(reason => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, [currentStatus?.configured, competitionCode]);

  const visibleFixtures = useMemo(() => {
    const now = Date.now();
    let values = fixtures.filter(fixture => teamId === "all" || String(fixture.home_team.team_id) === teamId || String(fixture.away_team.team_id) === teamId);
    if (fixtureView === "upcoming") {
      values = values.filter(fixture => fixture.status.short === "NS" || fixture.status.is_live || (fixture.kickoff && new Date(fixture.kickoff).getTime() >= now));
      return values.sort((a,b) => String(a.kickoff).localeCompare(String(b.kickoff))).slice(0, 20);
    }
    if (fixtureView === "results") {
      values = values.filter(fixture => fixture.status.short === "FT");
      return values.sort((a,b) => String(b.kickoff).localeCompare(String(a.kickoff))).slice(0, 20);
    }
    return values.sort((a,b) => String(a.kickoff).localeCompare(String(b.kickoff)));
  }, [fixtures, fixtureView, teamId]);
  const selectedStyle = styleProfiles.find(item => [item.provider, item.team_id, item.competition_id, item.season_id].join("|") === styleProfileKey);
  const selectedShape = shapeProfiles.find(item => String(item.team_id) === shapeTeamId);
  const styleHref = selectedStyle ? `/teams/${encodeURIComponent(String(selectedStyle.team_id))}?provider=${encodeURIComponent(selectedStyle.provider)}&competition_id=${encodeURIComponent(String(selectedStyle.competition_id))}&season_id=${encodeURIComponent(String(selectedStyle.season_id))}` : "#analysis-library";
  const shapeHref = selectedShape ? `/teams/${encodeURIComponent(String(selectedShape.team_id))}` : "#analysis-library";

  return <main className="football-home">
    <nav className="home-nav"><a className="home-brand" href="/"><span>TACT</span>IQ</a><div><a href="#live-now"><i/> Live now</a><a href="#fixture-browser">Fixtures</a><a href="#analysis-library">Team analysis</a><a href="/pre-match-briefing">Pre-match briefing</a></div></nav>
    <header className="home-hero">
      <div><span className="home-eyebrow">Football intelligence, explained clearly</span><h1>Choose the match<br/>you want to understand.</h1><p>See what is live, browse a league, choose a team, and open a recent-form matchup preview without needing to know provider IDs.</p></div>
      <aside><strong>Start here</strong><a href="#live-now">What is live? <span>↓</span></a><a href="#fixture-browser">Find a league or team <span>→</span></a><a href="#analysis-library">Understand how a team plays <span>→</span></a><a href="/pre-match-briefing">Prepare for a matchup <span>→</span></a></aside>
    </header>

    <section className="match-picker live-home-section" id="live-now">
      <header><div><span>Live match centre</span><h2>Matches happening now</h2></div><small>Major competitions are shown first</small></header>
      {!liveStatus ? <div className="picker-state">Connecting to live matches…</div> : !liveStatus.configured ? <div className="picker-state"><h3>Live scores are not connected</h3><p>The fixture browser below still works independently.</p></div> : liveError ? <div className="picker-state error"><h3>Live matches could not be loaded</h3><p>{liveError}</p></div> : liveFixtures.length ? <div className="home-fixture-grid">{liveFixtures.slice(0, 12).map(fixture => <FixtureCard fixture={fixture} provider="api-football" key={fixture.fixture_id}/>)}</div> : <div className="picker-state"><h3>No matches are live right now</h3><p>Choose a competition below to see its current-season fixtures and results.</p></div>}
    </section>

    <section className="match-picker" id="fixture-browser">
      <header><div><span>Fixture browser</span><h2>Choose a league, then a team</h2></div>{currentStatus?.configured && <small>Current schedules from football-data.org</small>}</header>
      {!currentStatus ? <div className="picker-state">Connecting to current football data…</div> : !currentStatus.configured ? <div className="picker-state setup"><h3>Current fixtures need to be connected</h3><p>Restart the backend with <code>TACTIQ_FOOTBALL_DATA_KEY</code> set. The key remains on the backend.</p></div> : <>
        <div className="picker-controls three-step-picker">
          <label><span>1. League</span><select value={competitionCode} onChange={event => setCompetitionCode(event.target.value)}>{competitions.map(item => <option key={item.code} value={item.code}>{POPULAR_COMPETITIONS.has(item.code) ? "★ " : ""}{item.name}{item.country ? ` · ${item.country}` : ""}</option>)}</select></label>
          <label><span>2. Team (optional)</span><select value={teamId} onChange={event => setTeamId(event.target.value)}><option value="all">All teams</option>{teams.map(team => <option key={team.team_id ?? team.name} value={String(team.team_id)}>{team.name}</option>)}</select></label>
          <label><span>3. What to show</span><select value={fixtureView} onChange={event => setFixtureView(event.target.value as "upcoming" | "results" | "all")}><option value="upcoming">Upcoming fixtures</option><option value="results">Recent results</option><option value="all">Full season schedule</option></select></label>
        </div>
        {error ? <div className="picker-state error"><h3>Fixtures could not be loaded</h3><p>{error}</p></div> : loading ? <div className="picker-state">Loading {selectedCompetition?.name ?? "competition"} fixtures and teams…</div> : <>
          <div className="fixture-section-title">{selectedCompetition?.logo_url && <img src={selectedCompetition.logo_url} alt=""/>}<div><strong>{selectedCompetition?.name ?? "Competition"}</strong><small>{teamId === "all" ? "All teams" : teams.find(team => String(team.team_id) === teamId)?.name} · {visibleFixtures.length} match{visibleFixtures.length === 1 ? "" : "es"} shown</small></div></div>
          {visibleFixtures.length ? <div className="home-fixture-grid">{visibleFixtures.map(fixture => <FixtureCard fixture={fixture} provider="football-data" key={fixture.fixture_id}/>)}</div> : <div className="picker-state"><h3>No matching fixtures found</h3><p>Try another team or switch between upcoming fixtures and recent results.</p></div>}
        </>}
      </>}
    </section>

    <section className="analysis-library" id="analysis-library">
      <header><div><span>TactIQ analysis</span><h2>What do you want to understand?</h2></div><p>Choose a football question first. TactIQ takes you to a focused workspace and keeps the technical evidence underneath the explanation.</p></header>
      <div className="analysis-path-grid">
        <article><FootballIcon name="teams"/><small>Team Style</small><h3>How does this team normally play?</h3><p>Attacking approach, chance creation, defending and recurring patterns across a season.</p>{styleProfiles.length ? <><select aria-label="Choose a team style profile" value={styleProfileKey} onChange={event => setStyleProfileKey(event.target.value)}>{styleProfiles.map(item => { const key = [item.provider, item.team_id, item.competition_id, item.season_id].join("|"); return <option value={key} key={key}>{item.team_name} · {item.season_name ?? item.season_id}</option>; })}</select><a href={styleHref}>Open {selectedStyle?.team_name ?? "Team"} style →</a></> : <span className="analysis-path-unavailable">No season style profiles are ready.</span>}</article>
        <article><FootballIcon name="overview"/><small>Team Shape</small><h3>What does their structure look like?</h3><p>Real tracking movement showing width, compactness, defensive lines and the space between units.</p>{shapeProfiles.length ? <><select aria-label="Choose a tracking team profile" value={shapeTeamId} onChange={event => setShapeTeamId(event.target.value)}>{shapeProfiles.map(item => <option value={String(item.team_id)} key={`${item.provider}-${item.team_id}`}>{item.team_name} · {item.analysed_match_count} tracked matches</option>)}</select><a href={shapeHref}>Open {selectedShape?.team_name ?? "Team"} shape →</a></> : <span className="analysis-path-unavailable">No continuous-tracking profiles are ready.</span>}</article>
        <article><FootballIcon name="flow"/><small>Match Analysis</small><h3>How was this match actually played?</h3><p>Read the game flow, compare both teams, investigate goals and inspect the supporting moments.</p><a href="/matches/2017461/overview">Open Melbourne Victory vs Auckland →</a><a className="secondary" href="/event-matches/statsbomb_open_data/217/11/27/266557/overview">Open Barcelona match →</a></article>
        <article><FootballIcon name="evidence"/><small>Pre-Match Briefing</small><h3>What should I review before kickoff?</h3><p>Compare established team tendencies, matchup interactions and representative historical moments.</p><a href="/pre-match-briefing">Build a pre-match briefing →</a></article>
      </div>
      <p className="analysis-source-note">Current fixtures provide schedules and basic match statistics. Deeper style and shape analysis appears only where TactIQ has compatible event or tracking evidence.</p>
    </section>
  </main>;
}
