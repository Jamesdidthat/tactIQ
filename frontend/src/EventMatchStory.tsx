import type { EventMetricUnit, EventProfileMatch, MatchStoryExplanationResponse, MatchStoryPoint, MatchStoryResponse } from "./types";
import { metricLabel } from "./presentation";

const sourceLabels: Record<MatchStoryPoint["story_type"], string> = {
  metric_relationship_residual: "Relationship",
  match_archetype: "Archetype",
  single_metric_deviation: "Single-metric",
};

const evidenceClasses: Record<MatchStoryPoint["evidence_level"], string> = {
  exploratory: "provisional",
  limited: "provisional",
  moderate: "developing",
  strong: "established",
};

const numberValue = (record: Record<string, unknown>, key: string) => {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};

const formatValue = (value: number | null, unit?: EventMetricUnit) => {
  if (value == null) return "Multiple metrics";
  if (unit === "proportion") return `${(value * 100).toFixed(1)}%`;
  if (unit === "native_120x80_units") return `${value.toFixed(1)} units`;
  if (unit === "count") return value.toFixed(Number.isInteger(value) ? 0 : 1);
  return value.toFixed(unit === "xG" || unit === "xG_per_90" ? 2 : 1);
};

function StoryPointCard({ point, index }: { point: MatchStoryPoint; index: number }) {
  const isArchetype = point.story_type === "match_archetype";
  const leadMetric = point.story_type === "metric_relationship_residual"
    ? point.supporting_metrics[1]
    : point.supporting_metrics[0];
  const observed = leadMetric?.observed_value ?? null;
  const baseline = point.story_type === "metric_relationship_residual"
    ? numberValue(point.comparator, "expected_value")
    : leadMetric?.season_baseline ?? numberValue(point.comparator, "value");
  const deviation = point.story_type === "metric_relationship_residual"
    ? numberValue(point.deviation, "residual")
    : numberValue(point.deviation, "signed") ?? numberValue(point.deviation, "rule_strength");
  const deviationLabel = point.story_type === "metric_relationship_residual" ? "Residual" : point.story_type === "match_archetype" ? "Comparison" : "Difference";
  const ruleStrength = numberValue(point.deviation, "rule_strength");
  const archetypeObserved = point.supporting_metrics.map(metric => `${metricLabel(metric.metric)} ${formatValue(metric.observed_value ?? null, metric.unit)}`).join(" · ");
  const archetypeBaseline = point.supporting_metrics.map(metric => `${metricLabel(metric.metric)} ${formatValue(metric.season_baseline ?? null, metric.unit)}`).join(" · ");

  return <article className="match-story-card">
    <div className="story-index">{index + 1}</div>
    <div className="story-body">
      <div className="story-meta">
        <span className={`story-source ${point.story_type}`}>{sourceLabels[point.story_type]}</span>
        <span className={`evidence-band ${evidenceClasses[point.evidence_level]}`}>Evidence basis: {point.primary_evidence_basis}</span>
      </div>
      <h3>{point.title}</h3>
      <p>{point.observation}</p>
      <dl className="story-comparison">
        <div><dt>Observed</dt><dd>{isArchetype ? archetypeObserved : formatValue(observed, leadMetric?.unit)}</dd></div>
        <div><dt>{point.story_type === "metric_relationship_residual" ? "Expected" : "Season baseline"}</dt><dd>{isArchetype ? archetypeBaseline : formatValue(baseline, leadMetric?.unit)}</dd></div>
        <div><dt>{deviationLabel}</dt><dd>{isArchetype ? "Season-relative combination" : <>{deviation != null && deviation > 0 ? "+" : ""}{deviation == null ? "See components" : formatValue(deviation, leadMetric?.unit)}</>}</dd></div>
      </dl>
      <details className="story-evidence">
        <summary>Supporting metrics and definitions</summary>
        <div className="story-metric-list">{point.supporting_metrics.map((metric, metricIndex) => <div key={`${metric.metric}-${metricIndex}`}>
          <strong>{metricLabel(metric.metric)}</strong>
          <span>Observed {formatValue(metric.observed_value ?? null, metric.unit)}{metric.season_baseline != null ? ` · season median ${formatValue(metric.season_baseline, metric.unit)}` : ""}{metric.robust_z_score != null ? ` · robust z ${metric.robust_z_score > 0 ? "+" : ""}${metric.robust_z_score.toFixed(2)}` : ""}</span>
          {metric.definition && <small>{metric.definition}</small>}
        </div>)}</div>
        <div className="story-limitations"><strong>Limitations</strong>{point.limitations.map((limitation, limitationIndex) => <p key={limitationIndex}>{limitation}</p>)}</div>
        {point.supporting_evidence_bases.length > 1 && <div className="story-support-bases"><strong>Evidence provenance</strong>{point.supporting_evidence_bases.map(item => <span key={item.candidate_id}>{item.is_primary ? "Primary" : "Secondary"} · {sourceLabels[item.story_type]} · {item.evidence_basis}</span>)}</div>}
        <small>{point.contributing_season_match_count} contributing matches · {(point.coverage * 100).toFixed(0)}% coverage{point.chronology.available ? ` · contributing events span approximately minutes ${Math.floor((point.chronology.first_seconds ?? 0) / 60)}–${Math.ceil((point.chronology.last_seconds ?? 0) / 60)}` : " · chronology unavailable"}</small>
        <small className="story-internal-audit">Internal evidence audit · priority {point.priority_score.toFixed(3)}{ruleStrength != null ? ` · rule strength ${ruleStrength.toFixed(2)}` : ""}</small>
      </details>
    </div>
  </article>;
}

function StoryExplanation({ response, loading, error }: { response: MatchStoryExplanationResponse | null; loading: boolean; error: string | null }) {
  if (loading) return <section className="story-ai explanation-state"><div className="spinner" /><span>Preparing grounded explanation…</span></section>;
  if (error) return <section className="story-ai explanation-state error"><div><strong>AI explanation unavailable</strong><p>The deterministic evidence above is unaffected. {error}</p></div></section>;
  if (!response) return null;
  const explanation = response.explanation;
  const fallback = response.metadata.source === "deterministic_fallback";
  return <section className="story-ai">
    <div className="story-ai-heading"><div><p className="eyebrow">AI explanation</p><h3>{explanation.headline}</h3></div><span className={`story-ai-source ${fallback ? "fallback" : "model"}`}>{fallback ? "Deterministic fallback" : "Model explanation"}</span></div>
    <p className="story-ai-summary">{explanation.summary}</p>
    {explanation.story_point_explanations.length > 0 && <div className="story-ai-points">{explanation.story_point_explanations.map((item, index) => <div key={item.story_id}><strong>Observation {index + 1}</strong><p>{item.explanation}</p></div>)}</div>}
    {explanation.what_to_review_in_video.length > 0 && <div className="story-ai-review"><strong>What to review in video</strong><ul>{explanation.what_to_review_in_video.map(item => <li key={item.story_id}>{item.guidance}</li>)}</ul></div>}
    <p className="story-ai-caveat">{explanation.evidence_caveat}</p>
    {response.metadata.validation_warnings.length > 0 && <p className="story-ai-fallback-note">The configured model output did not pass grounding checks, so TactIQ used deterministic fallback text.</p>}
  </section>;
}

export function EventMatchStory({ matches, selectedMatchId, story, loading, error, explanation, explanationLoading, explanationError, onSelect }: { matches: EventProfileMatch[]; selectedMatchId: string | number | null; story: MatchStoryResponse | null; loading: boolean; error: string | null; explanation: MatchStoryExplanationResponse | null; explanationLoading: boolean; explanationError: string | null; onSelect: (matchId: string) => void }) {
  const sectionTitle = story?.presentation_mode === "parallel_observations" ? "Notable observations" : "Match Story";
  return <section className="panel profile-section match-story">
    <div className="panel-heading">
      <div><p className="eyebrow">Selected-match evidence</p><h2>{sectionTitle}</h2>{story?.presentation_mode === "parallel_observations" && <small className="parallel-note">Valid observations shown separately; the available data does not establish a deterministic link between them.</small>}</div>
      <label className="story-match-picker">Match
        <select value={selectedMatchId == null ? "" : String(selectedMatchId)} onChange={event => onSelect(event.target.value)} disabled={!matches.length}>
          {!matches.length && <option value="">No matches available</option>}
          {matches.map(match => <option key={String(match.match_id)} value={String(match.match_id)}>Match {match.match_id}{match.opponent_team_name ? ` · vs ${match.opponent_team_name}` : ""}{match.match_date ? ` · ${match.match_date}` : ""}</option>)}
        </select>
      </label>
    </div>
    {!loading && story && <div className="story-context"><strong>{story.match_context.opponent_team_name ? `${story.team_name} vs ${story.match_context.opponent_team_name}` : `Match ${story.match_id}`}</strong><span>{[story.match_context.home_away ? metricLabel(story.match_context.home_away) : null, story.match_context.team_relative_score ? `team-relative score ${story.match_context.team_relative_score}` : null, story.match_context.match_date].filter(Boolean).join(" · ") || "Match context unavailable"}</span>{story.match_context.score_state_source && <details><summary>Score-state exposure</summary><p>{(["leading", "drawing", "trailing"] as const).map(state => { const share = story.match_context.score_state_exposure[state]?.share; return `${metricLabel(state)} ${share == null ? "unavailable" : `${(share * 100).toFixed(0)}%`}`; }).join(" · ")}</p><small>{metricLabel(story.match_context.score_state_source)}</small></details>}</div>}
    {loading && <div className="story-state"><div className="spinner" /><span>Assembling deterministic match evidence…</span></div>}
    {!loading && !error && !story && matches.length === 0 && <div className="story-state empty"><strong>No season matches available</strong><span>This event profile has no match-level observations that can be selected.</span></div>}
    {!loading && error && <div className="story-state error"><strong>Match Story unavailable</strong><span>{error}</span></div>}
    {!loading && !error && story && story.story_points.length === 0 && <div className="story-state empty"><strong>No qualifying story points for this match</strong><span>{story.message ?? "No unusual season-relative patterns qualified. This does not mean the match lacked important events."}</span></div>}
    {!loading && !error && story && story.story_points.length > 0 && <div className="match-story-list">{story.story_points.map((point, index) => <StoryPointCard key={point.story_id} point={point} index={index} />)}</div>}
    {!loading && !error && story && <StoryExplanation response={explanation} loading={explanationLoading} error={explanationError} />}
  </section>;
}
