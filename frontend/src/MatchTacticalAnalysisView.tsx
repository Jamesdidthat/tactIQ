import type { GoalAnalysis, MatchTacticalProfile, TeamMatchTacticalProfile } from "./types";

export type MatchAnalysisSection = "overview" | "flow" | "teams" | "goals";

const contributorLabel = (value: string) => ({
  recurring_structural_pattern: "Recurring season pattern",
  match_specific_tactical_pattern: "Already seen in this match",
  opponent_recurring_attacking_strength: "Recurring scoring-team pattern",
  historical_mechanism_context: "Related season context",
  transition_after_turnover: "Counter-attack context",
  set_piece_pattern: "Set-play context",
  exceptional_individual_execution: "Difficult finish",
  unusual_event: "Unusual event",
  insufficient_evidence: "Not enough evidence",
}[value] ?? value.replaceAll("_", " "));

function SectionIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="match-section-intro"><div><small>{eyebrow}</small><h2>{title}</h2></div><p>{description}</p></header>;
}

function TeamOverviewCard({ team }: { team: TeamMatchTacticalProfile }) {
  return <article className="team-overview-card">
    <small>{team.team_name}</small><h3>{team.headline}</h3><p>{team.overview}</p>
    {team.style_deviations[1] && <span>{team.style_deviations[1].football_summary}</span>}
  </article>;
}

function TeamAnalysisCard({ team }: { team: TeamMatchTacticalProfile }) {
  const observations = team.style_deviations.slice(0, 3);
  return <article className="match-team-reading">
    <small>{team.team_name}</small><h3>{team.headline}</h3><p>{team.overview}</p>
    {observations.length > 0 && <div className="match-supporting-observations"><small>What stood out</small>{observations.map(item => <p key={item.metric}>{item.football_summary}</p>)}</div>}
    {team.opponent_relative_observations.map(item => <p className="match-interaction" key={item}>{item}</p>)}
    <details className="match-technical-evidence"><summary>Why TactIQ says this</summary>
      {team.style_deviations.length ? team.style_deviations.map(item => <section key={item.metric}><strong>{item.football_summary}</strong><span>Match {item.observed_value.toFixed(2)} · usual reference {item.season_median.toFixed(2)}</span><small>{item.contributing_matches} other matches · {(item.coverage * 100).toFixed(0)}% coverage</small><details><summary>Measurement definition</summary><p>{item.definition}</p></details></section>) : <p>No difference from their usual game passed the current evidence rule.</p>}
      {team.tracking_shape && <section><strong>Observed team shape</strong><span>{String(team.tracking_shape.observed_frames)} tracked frames</span><small>Continuous-tracking evidence; detailed measurements remain provider-scoped.</small></section>}
    </details>
  </article>;
}

function MatchFlowCard({ team }: { team: TeamMatchTacticalProfile }) {
  const highlights = team.segments.filter((segment, index) => index === 0 || segment.change_from_previous.length);
  return <article className="match-flow-card">
    <header><small>{team.team_name}</small><h3>How their match developed</h3></header>
    <div className="flow-timeline">{highlights.map((segment, index) => <article key={segment.segment_id} className={segment.change_from_previous.length ? "changed" : "opening"}>
      <time>{segment.start_minute}'–{segment.end_minute}'</time><div><strong>{segment.headline}</strong><p>{segment.explanation}</p>{segment.change_from_previous.map(item => <em key={item}>{item}.</em>)}</div><span>{index + 1}</span>
    </article>)}</div>
    <details className="match-full-timeline"><summary>See every 15-minute evidence window</summary><div className="match-segment-strip">{team.segments.map(segment => <details key={segment.segment_id}><summary><span>{segment.start_minute}'–{segment.end_minute}'</span><strong>{segment.headline}</strong></summary><p>{segment.explanation}</p></details>)}</div></details>
  </article>;
}

function chanceLabel(xg: number | null) {
  if (xg == null) return "Chance difficulty unavailable";
  if (xg <= .08) return "Difficult chance";
  if (xg <= .2) return "Moderate chance";
  return "Strong chance";
}

function GoalCard({ goal, index }: { goal: GoalAnalysis; index: number }) {
  return <article className="goal-investigation">
    <header><div><small>Goal {index + 1} · {goal.minute}:{String(goal.second).padStart(2, "0")}</small><h3>{goal.scoring_team_name} scored against {goal.conceding_team_name}</h3></div><span>{chanceLabel(goal.shot_xg)}</span></header>
    <dl className="goal-answers">
      <div><dt>What happened?</dt><dd>{goal.what_happened}</dd></div>
      <div><dt>What opened the chance?</dt><dd>{goal.what_created_the_opportunity}</dd></div>
      <div><dt>Had it happened earlier?</dt><dd>{goal.had_this_been_happening_earlier}</dd></div>
      <div><dt>Is it a recurring issue?</dt><dd>{goal.recurring_season_pattern}</dd></div>
      <div><dt>Structure or execution?</dt><dd>{goal.structural_versus_execution}</dd></div>
    </dl>
    <div className="goal-contributors">{goal.contributors.map(item => <div key={`${item.category}-${item.observation}`}><strong>{contributorLabel(item.category)}</strong><p>{item.observation}</p></div>)}</div>
    <details><summary>Show sequence and measurements</summary><p>{goal.sequence_duration_seconds.toFixed(1)} seconds · {goal.passes} passes · {goal.carries} carries · {goal.progression_route} route · score state: {goal.score_state_before_goal ?? "unavailable"}{goal.shot_xg == null ? "" : ` · xG ${goal.shot_xg.toFixed(2)}`}</p><ol className="goal-timeline">{goal.preceding_actions.map(action => <li key={action.event_id}><time>{action.minute}:{String(action.second).padStart(2, "0")}</time><strong>{action.event_type}</strong><span>{action.outcome ?? ""}</span></li>)}</ol>{goal.tracking_context ? <p>Compatible tracking context is available immediately before this goal.</p> : <p>Full player shape is unavailable for this event-only match.</p>}{goal.limitations.map(item => <small className="goal-limit" key={item}>{item}</small>)}</details>
  </article>;
}

export function MatchTacticalAnalysisView({ profile, section = "overview", loading, error }: { profile: MatchTacticalProfile | null; section?: MatchAnalysisSection; loading: boolean; error: string | null }) {
  if (loading) return <section className="panel match-tactical-state"><div className="spinner"/><h2>Reading how this match was played</h2></section>;
  if (error) return <section className="panel match-tactical-state"><h2>Match analysis unavailable</h2><p>{error}</p></section>;
  if (!profile) return null;

  if (section === "overview") return <section className="match-tactical-layer">
    <SectionIntro eyebrow="Match overview" title="The quickest read of the game" description="Start here. These are the clearest differences from each team's usual game; open another section when you want the detail." />
    <div className="match-team-grid">{profile.team_profiles.map(team => <TeamOverviewCard team={team} key={String(team.team_id)}/>)}</div>
    <div className="overview-goal-strip"><strong>{profile.goals.length ? `${profile.goals.length} goal${profile.goals.length === 1 ? "" : "s"} examined` : "No supported goal events"}</strong><span>{profile.goals.length ? "Each goal has its own sequence and evidence review." : "TactIQ does not infer goals from the final score."}</span></div>
  </section>;

  if (section === "teams") return <section className="match-tactical-layer">
    <SectionIntro eyebrow="Team analysis" title="How each side played compared with normal" description="Only the clearest match-versus-usual differences are shown first. Measurements and definitions stay behind the evidence control." />
    <div className="match-team-grid">{profile.team_profiles.map(team => <TeamAnalysisCard team={team} key={String(team.team_id)}/>)}</div>
  </section>;

  if (section === "flow") return <section className="match-tactical-layer">
    <SectionIntro eyebrow="Match flow" title="When the game changed" description="This view highlights the opening spell and periods where control, shooting or entries into the box changed noticeably." />
    <div className="match-flow-grid">{profile.team_profiles.map(team => <MatchFlowCard team={team} key={String(team.team_id)}/>)}</div>
    <details className="match-analysis-limits"><summary>How to read this timeline</summary><p>These are fixed evidence windows with deterministic change markers. They are not automatically tactical phases and do not prove why a change occurred.</p></details>
  </section>;

  return <section className="match-tactical-layer">
    <SectionIntro eyebrow="Goal analysis" title="How each goal developed" description="Every supported goal is reviewed separately. TactIQ preserves several possible contributors and does not force one cause or assign blame." />
    <section className="goal-analysis-section">{profile.goals.map((goal, index) => <GoalCard goal={goal} index={index} key={goal.goal_id}/>)}{!profile.goals.length && <p className="football-empty">No canonical goal event was available for investigation. TactIQ does not infer one from the final score.</p>}</section>
    <details className="match-analysis-limits"><summary>Coverage and limitations</summary>{Object.entries(profile.analysis_coverage).map(([key, value]) => <p key={key}><strong>{key.replaceAll("_", " ")}:</strong> {value}</p>)}{profile.limitations.map(item => <p key={item}>{item}</p>)}</details>
  </section>;
}
