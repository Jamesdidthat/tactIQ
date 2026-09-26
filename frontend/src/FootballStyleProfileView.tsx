import { useEffect, useState } from "react";
import { eventProfileApi } from "./api";
import { AnimatedEventSequencePitch } from "./AnimatedEventSequencePitch";
import type { EventProfileMatch, FootballConceptEvidence, FootballStyleConcept, FootballStyleProfile, TeamStyleVisualExamples } from "./types";

const formatEvidenceValue = (item: FootballConceptEvidence, value: number) => {
  if (item.unit === "proportion") return `${(value * 100).toFixed(0)}%`;
  if (item.unit === "count") return value.toFixed(Number.isInteger(value) ? 0 : 1);
  if (item.unit === "per_90") return `${value.toFixed(1)} per match`;
  if (item.unit === "xG_per_90") return `${value.toFixed(2)} xG per match`;
  if (item.unit === "xG") return `${value.toFixed(2)} xG`;
  return value.toFixed(1);
};

type VisualContext = { provider: string; teamId: string; competitionId: string; seasonId: string };

function VisualPatternExamples({ concept, context }: { concept: FootballStyleConcept; context: VisualContext }) {
  const [open, setOpen] = useState(false);
  const [examples, setExamples] = useState<TeamStyleVisualExamples | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!open || examples || error) return;
    let active = true;
    eventProfileApi.styleConceptMoments(context.provider, context.teamId, context.competitionId, context.seasonId, concept.concept_id)
      .then(result => { if (active) { setExamples(result); setSelectedEventId(result.representative_moments[0]?.event_id ?? null); } })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [open, examples, error, concept.concept_id, context.provider, context.teamId, context.competitionId, context.seasonId]);
  const selectedMoment = examples?.representative_moments.find(item => item.event_id === selectedEventId) ?? examples?.representative_moments[0];
  const selectedDetail = examples?.representative_moment_details.find(item => item.event_id === selectedMoment?.event_id);
  return <section className={`visual-pattern-examples ${open ? "open" : ""}`}>
    <button className="visual-pattern-toggle" type="button" onClick={() => setOpen(value => !value)}><span aria-hidden="true">▶</span><strong>{open ? "Close examples" : "Inspect recorded examples"}</strong><small>Whole-team positions appear only when tracking exists</small></button>
    {open && <div className="visual-pattern-body">
      {!examples && !error && <div className="visual-pattern-state">Loading representative match evidence…</div>}
      {error && <div className="visual-pattern-state error"><strong>Examples unavailable</strong><span>{error}</span></div>}
      {examples && !examples.representative_moments.length && <div className="visual-pattern-state"><strong>No faithful visual mapping yet</strong><span>{examples.limitations[examples.limitations.length - 1]}</span></div>}
      {examples && selectedMoment && <>
        <div className="visual-example-tabs">{examples.representative_moments.map((item, index) => <button className={item.event_id === selectedMoment.event_id ? "active" : ""} type="button" onClick={() => setSelectedEventId(item.event_id)} key={item.event_id}><b>Example {index + 1}</b><span>vs {item.opponent_name} · {item.minute}:{String(item.second).padStart(2,"0")}</span></button>)}</div>
        <header className="visual-example-heading"><div><small>{selectedMoment.match_date} · {selectedMoment.score_state_verified ? `${selectedMoment.score_state ?? "drawing"} at the time` : "Score state unavailable"}</small><h4>{selectedMoment.description}</h4></div><span>{selectedDetail?.moment_360_context.available ? "Partial 360" : "Event only"}</span></header>
        {selectedDetail ? <AnimatedEventSequencePitch detail={selectedDetail}/> : <div className="visual-pattern-state">Sequence detail unavailable.</div>}
        <footer className="visual-example-footer"><span>Selected from {new Set(examples.representative_moments.map(item => item.match_id)).size} historical matches for diversity.</span><a href={`/event-matches/${encodeURIComponent(context.provider)}/${encodeURIComponent(context.teamId)}/${encodeURIComponent(context.competitionId)}/${encodeURIComponent(context.seasonId)}/${encodeURIComponent(String(selectedMoment.match_id))}/overview`}>Open this match →</a></footer>
      </>}
    </div>}
  </section>;
}

function ConceptCard({ concept, technicalHref, visualContext }: { concept: FootballStyleConcept; technicalHref: string; visualContext: VisualContext }) {
  const examples = Array.from(new Map(concept.supporting_evidence.flatMap(item => item.representative_matches).map(item => [String(item.match_id), item])).values()).slice(0, 3);
  const recurrence = concept.evidence_basis === "Established" ? "This pattern appears consistently across the season sample." : concept.evidence_basis === "Developing" ? "This pattern appears across several matches." : "This is an early pattern and needs more matches.";
  return <article className="football-concept-card" id={`concept-${concept.concept_id}`}>
    <div><h3>{concept.title}</h3></div>
    <p>{concept.summary}</p>
    <p className="football-looks"><strong>What this looks like</strong><span>{concept.what_this_looks_like}</span></p>
    <VisualPatternExamples concept={concept} context={visualContext}/>
    {examples.length > 0 && <details className="football-examples"><summary>See the supporting matches</summary><div>{examples.map(item => <a href={`${technicalHref}&match_id=${encodeURIComponent(String(item.match_id))}`} key={String(item.match_id)}><strong>{item.opponent_team_name ? `vs ${item.opponent_team_name}` : `Match ${item.match_id}`}</strong><span>{item.match_date ?? "Date unavailable"} · {item.home_away ?? "Venue unavailable"}</span></a>)}</div><small>These matches illustrate the measured pattern. They do not by themselves explain its tactical cause.</small></details>}
    <details><summary>Why TactIQ says this</summary>
      <p className="football-recurrence">{recurrence}</p>
      <div className="football-evidence-list">{concept.supporting_evidence.map(item => <section key={item.metric}>
        <strong>{item.football_label}</strong><span>Usually {formatEvidenceValue(item, item.season_median)}</span>
        <small>Typical match range: {formatEvidenceValue(item, item.q25)}–{formatEvidenceValue(item, item.q75)} · {item.contributing_matches} matches</small>
        <details><summary>How this is measured</summary><p>{item.definition}</p></details>
      </section>)}</div>
      {concept.limitations.map(item => <p className="football-limitation" key={item}>{item}</p>)}
    </details>
  </article>;
}

function ConceptSection({ eyebrow, title, intro, concepts, empty, technicalHref, visualContext }: { eyebrow: string; title: string; intro: string; concepts: FootballStyleConcept[]; empty: string; technicalHref: string; visualContext: VisualContext }) {
  return <section className="football-style-section">
    <header><div><small>{eyebrow}</small><h2>{title}</h2></div><p>{intro}</p></header>
    {concepts.length ? <div className="football-concept-grid">{concepts.map(item => <ConceptCard concept={item} technicalHref={technicalHref} visualContext={visualContext} key={item.concept_id}/>)}</div> : <p className="football-empty">{empty}</p>}
  </section>;
}

export function FootballStyleProfileView({ profile, matches, technicalHref, provider }: { profile: FootballStyleProfile; matches: EventProfileMatch[]; technicalHref: string; provider: string }) {
  const visualContext = { provider, teamId: String(profile.team_id), competitionId: String(profile.competition_id), seasonId: String(profile.season_id) };
  const recentMatches = [...matches].sort((a, b) => String(b.match_date ?? "").localeCompare(String(a.match_date ?? ""))).slice(0, 10);
  const allConcepts = [...profile.in_possession, ...profile.out_of_possession, ...profile.transitions];
  const conceptById = new Map(allConcepts.map(item => [item.concept_id, item]));
  const gameFlow = [
    ["Build-up", "build_up"], ["Progression", "progression"], ["Final third", "territorial_access"],
    ["Chance creation", "chance_creation"], ["Shot selection", "shot_selection"],
  ].map(([stage, conceptId]) => ({ stage, concept: conceptById.get(conceptId) })).filter((item): item is { stage: string; concept: FootballStyleConcept } => Boolean(item.concept));
  const requestedMatch = new URLSearchParams(window.location.search).get("match_id");
  const [selectedMatch, setSelectedMatch] = useState<string | number | null>(matches.find(item => String(item.match_id) === requestedMatch)?.match_id ?? matches[0]?.match_id ?? null);
  const chooseMatch = (value: string) => {
    setSelectedMatch(value);
    const url = new URL(window.location.href); url.searchParams.set("match_id", value); window.history.replaceState({}, "", url);
  };
  const matchWorkspaceHref = selectedMatch == null ? null : `/event-matches/${encodeURIComponent(provider)}/${encodeURIComponent(String(profile.team_id))}/${encodeURIComponent(String(profile.competition_id))}/${encodeURIComponent(String(profile.season_id))}/${encodeURIComponent(String(selectedMatch))}/overview`;
  return <main className="shell football-style-profile">
    <header className="football-profile-header"><div><p className="eyebrow">TactIQ / How this team plays</p><h1>{profile.team_name}</h1><p>{profile.competition_name ?? "Competition unavailable"} · {profile.season_name ?? "Season unavailable"}</p></div><div><strong>{profile.analysed_match_count} matches analysed</strong><a href={technicalHref}>Open technical evidence</a><a href="/pre-match-briefing">Build a pre-match briefing</a></div></header>
    <section className="football-identity"><small>What kind of team are they?</small><h2>{profile.playing_identity}</h2><p>Based on patterns that repeat across their matches.</p></section>
    <section className="match-reader-picker"><div><small>Read a particular match</small><h2>How was this game actually played?</h2></div><label>Match<select value={String(selectedMatch ?? "")} onChange={event => chooseMatch(event.target.value)}>{matches.map(match => <option value={String(match.match_id)} key={String(match.match_id)}>{match.match_date ?? "Date unavailable"} · {match.opponent_team_name ? `vs ${match.opponent_team_name}` : `Match ${match.match_id}`} {match.team_score == null || match.opponent_score == null ? "" : `· ${match.team_score}–${match.opponent_score}`}</option>)}</select></label></section>
    <section className="match-workspace-launch"><div><small>Separate match workspace</small><h2>Open only the part of the match you want to study</h2><p>Overview, match flow, team analysis, goals and technical evidence now live on separate pages.</p></div>{matchWorkspaceHref && <a href={matchWorkspaceHref}>Open match analysis →</a>}</section>
    <section className="football-glance"><header><div><small>Team style at a glance</small><h2>The quickest way to read their game</h2></div><p>Football-facing levels only. Open any dimension to see the full explanation and evidence.</p></header><div>{profile.style_at_a_glance.map(item => <a href={`#concept-${item.concept_id}`} key={item.dimension_id}><span>{item.label}</span><strong>{item.level}</strong><i className={`style-level level-${item.level.toLowerCase()}`} aria-label={`${item.label}: ${item.level}`}><b/><b/><b/></i></a>)}</div></section>
    <section className="football-flow"><header><div><small>How their game usually develops</small><h2>From keeping the ball to taking a shot</h2></div></header><div>{gameFlow.map((item, index) => <a href={`#concept-${item.concept.concept_id}`} key={item.concept.concept_id}><small>{index + 1}</small><strong>{item.stage}</strong><p>{item.concept.summary}</p></a>)}</div></section>
    <nav className="football-question-index" aria-label="Team profile questions"><a href="#in-possession">How do they attack?</a><a href="#out-of-possession">How do they defend?</a><a href="#strengths">What are they good at?</a><a href="#recent-style">What has changed recently?</a></nav>
    <div id="in-possession"><ConceptSection eyebrow="With the ball" title="How they attack" intro="How they keep the ball, move up the pitch and create chances." concepts={profile.in_possession} empty="The available data does not support a reliable description of their attacking play." technicalHref={technicalHref} visualContext={visualContext}/></div>
    <div id="out-of-possession"><ConceptSection eyebrow="Without the ball" title="How they defend" intro="What they do when opponents have the ball and what opponents manage to create." concepts={profile.out_of_possession} empty="The available data does not support a reliable description of their defending." technicalHref={technicalHref} visualContext={visualContext}/></div>
    <ConceptSection eyebrow="When possession changes" title="Transitions" intro="What happens when they win or lose the ball." concepts={profile.transitions} empty="No transition pattern appeared often enough to describe confidently." technicalHref={technicalHref} visualContext={visualContext}/>
    <div id="strengths" className="football-two-column"><ConceptSection eyebrow="Repeated strengths" title="What they do well" intro="Useful attacking patterns that repeat across many matches." concepts={profile.strengths} empty="No repeated strength passed the current rule. This is not evidence that the team has no strengths." technicalHref={technicalHref} visualContext={visualContext}/><ConceptSection eyebrow="Situations to examine" title="Where they can struggle" intro="Dangerous outcomes opponents have produced repeatedly, without guessing the cause." concepts={profile.potential_weaknesses} empty="No potential problem repeated often enough to qualify. This does not mean opponents found no useful situations." technicalHref={technicalHref} visualContext={visualContext}/></div>
    <div id="recent-style"><ConceptSection eyebrow={`Latest ${profile.recent_window_matches} matches`} title="Recent style" intro="How their latest matches differ from the longer season pattern." concepts={profile.recent_style} empty="Their recent matches have not changed enough to describe as a clear shift." technicalHref={technicalHref} visualContext={visualContext}/></div>
    {!profile.capabilities.has_continuous_tracking && <section className="shape-unavailable"><h2>Detailed team shape requires tracking data</h2><p>This event profile does not estimate team width, defensive-line height, compactness or off-ball structure from event locations.</p></section>}
    <section className="football-history"><header><div><small>Game history</small><h2>Recent matches</h2></div><p>Open a match in its dedicated football workspace.</p></header><div>{recentMatches.map(match => <a href={`/event-matches/${encodeURIComponent(provider)}/${encodeURIComponent(String(profile.team_id))}/${encodeURIComponent(String(profile.competition_id))}/${encodeURIComponent(String(profile.season_id))}/${encodeURIComponent(String(match.match_id))}/overview`} key={String(match.match_id)}><strong>{match.opponent_team_name ? `vs ${match.opponent_team_name}` : `Match ${match.match_id}`}</strong><span>{match.match_date ?? "Date unavailable"} · {match.home_away ?? "Venue unavailable"}</span><b>{match.team_score == null || match.opponent_score == null ? "Score unavailable" : `${match.team_score}–${match.opponent_score}`}</b></a>)}</div></section>
    <section className="football-profile-notes"><div><small>What this profile can see</small><p>How teams use the ball, move attacks forward, enter dangerous areas, create shots, defend and react when possession changes.</p></div><div><small>What it cannot see here</small><p>The full position and movement of every player when they are away from the ball.</p></div><details><summary>Technical limitations</summary>{profile.limitations.map(item => <p key={item}>{item}</p>)}</details></section>
  </main>;
}
