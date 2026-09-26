import { mockDetail, mockExplanation, mockFrame, mockRanked, mockSummary } from "./mockApi";
import type { FootballShapeProfile, FootballStyleProfile, MatchTacticalProfile } from "./types";
import type { CurrentCompetitionCatalog, CurrentFixtureList, CurrentTeamCatalog, FootballDataStatus, LiveLeagueCatalog } from "./types";
import type { ApiFootballMatchupPreview, EventProfileCatalogResponse, EventProfileFinding, EventProfileMatch, EventProfileSummary, EventProfileTendency, EventSeasonBaseline, EventUnusualMatch, FindingDetailResponse, FindingExplanationResponse, LiveFixtureList, LiveFixtureSnapshot, LiveFootballStatus, MatchArchetypeAssignment, MatchArchetypeSummary, MatchStoryExplanationResponse, MatchStoryResponse, MatchSummaryResponse, MatchupInteraction, MatchupInteractionFinding, MetricRelationshipFinding, MetricRelationshipFit, MomentPattern, MomentPatternAssignment, MomentSequenceFeatures, MomentSequencePattern, MomentSequenceSimilarity, OpponentComparisonFinding, OpponentComparisonSummary, OpponentMetricComparison, PatternContextSummary, PitchClipResponse, PitchFrameResponse, PreMatchBriefing, PreMatchEvidencePack, PreMatchReviewPriority, RankedFindingsResponse, RepresentativeMoment, RepresentativeMomentDetail, TeamDeviation, TeamMetricBaseline, TeamProfileSummaryResponse, TeamStyleVisualExamples, TrackingTeamProfileCatalogResponse } from "./types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
const useMock = import.meta.env.VITE_USE_MOCK === "true";
async function request<T>(path: string, fallback: T): Promise<T> {
  if (useMock) return Promise.resolve(fallback);
  const response = await fetch(`${baseUrl}${path}`);
  if (!response.ok) { const payload = await response.json().catch(() => null) as { error?: string } | null; throw new Error(payload?.error ?? `Analysis API returned ${response.status}`); }
  return response.json() as Promise<T>;
}
export const analysisApi = {
  tacticalAnalysis: (matchId: string) => request<MatchTacticalProfile>(`/matches/${matchId}/tactical-analysis`, {} as MatchTacticalProfile),
  summary: (matchId: string) => request<MatchSummaryResponse>(`/matches/${matchId}/summary`, mockSummary),
  ranked: (matchId: string) => request<RankedFindingsResponse>(`/matches/${matchId}/findings`, mockRanked),
  detail: (matchId: string, findingId: string) => request<FindingDetailResponse>(`/matches/${matchId}/findings/${encodeURIComponent(findingId)}`, mockDetail),
  explanation: (matchId: string, findingId: string) => request<FindingExplanationResponse>(`/matches/${matchId}/findings/${encodeURIComponent(findingId)}/explanation`, mockExplanation),
  frame: (matchId: string, findingId: string, moment = 0) => request<PitchFrameResponse>(`/matches/${matchId}/findings/${encodeURIComponent(findingId)}/moments/${moment}/frame`, mockFrame),
  rawFrame: (matchId: string | number, frame: number, period: number) => request<PitchFrameResponse>(`/matches/${matchId}/frames/${frame}/periods/${period}`, mockFrame),
  rawClip: (matchId: string | number, centreFrame: number, period: number, beforeSeconds = 4, afterSeconds = 4, step = 1) => request<PitchClipResponse>(
    `/matches/${matchId}/clips/${centreFrame}/periods/${period}?before_seconds=${beforeSeconds}&after_seconds=${afterSeconds}&step=${step}`,
    { schema_version: "v1", provider: "mock", match_id: matchId, period, centre_frame: centreFrame, focus_index: 0, source_frame_rate_hz: 10, playback_frame_rate_hz: 10, requested: { before_frames: 0, after_frames: 0, before_seconds: beforeSeconds, after_seconds: afterSeconds, step }, actual_start_frame: centreFrame, actual_end_frame: centreFrame, actual_duration_seconds: 0, frames: [mockFrame], limitations: [] }
  )
};
export const liveFootballApi = {
  status: () => request<LiveFootballStatus>("/live-football/status", { schema_version: "v1", provider: "api_football", configured: false, mode: "live_scores_and_statistics", capability_note: "Live football is not configured in mock mode." }),
  leagues: () => request<LiveLeagueCatalog>("/live-football/leagues", { schema_version: "v1", provider: "api_football", league_count: 0, leagues: [], cache_note: "" }),
  fixtures: (options: { live?: string; date?: string; league?: number; season?: number; next?: number }) => {
    const params = new URLSearchParams();
    if (options.live) params.set("live", options.live);
    if (options.date) params.set("date", options.date);
    if (options.league !== undefined) params.set("league", String(options.league));
    if (options.season !== undefined) params.set("season", String(options.season));
    if (options.next !== undefined) params.set("next", String(options.next));
    return request<LiveFixtureList>(`/live-football/fixtures?${params.toString()}`, { schema_version: "v1", provider: "api_football", query: {}, fixture_count: 0, fixtures: [], cache_note: "" });
  },
  fixture: (fixtureId: number) => request<LiveFixtureSnapshot>(`/live-football/fixtures/${fixtureId}`, {} as LiveFixtureSnapshot),
  matchupPreview: (fixtureId: number) => request<ApiFootballMatchupPreview>(`/live-football/fixtures/${fixtureId}/matchup-preview`, {} as ApiFootballMatchupPreview),
};
export const footballDataApi = {
  status: () => request<FootballDataStatus>("/football-data/status", { schema_version: "v1", provider: "football_data_org", configured: false, mode: "current_fixtures_teams_and_results", capability_note: "Current football data is not configured in mock mode." }),
  competitions: () => request<CurrentCompetitionCatalog>("/football-data/competitions", { schema_version: "v1", provider: "football_data_org", competition_count: 0, competitions: [], popular_competition_codes: [], cache_note: "" }),
  fixtures: (code: string, options: { status?: string; dateFrom?: string; dateTo?: string } = {}) => {
    const params = new URLSearchParams();
    if (options.status) params.set("status", options.status);
    if (options.dateFrom) params.set("dateFrom", options.dateFrom);
    if (options.dateTo) params.set("dateTo", options.dateTo);
    const query = params.toString();
    return request<CurrentFixtureList>(`/football-data/competitions/${encodeURIComponent(code)}/fixtures${query ? `?${query}` : ""}`, { schema_version: "v1", provider: "football_data_org", competition_code: code, query: {}, fixture_count: 0, fixtures: [], cache_note: "" });
  },
  teams: (code: string) => request<CurrentTeamCatalog>(`/football-data/competitions/${encodeURIComponent(code)}/teams`, { schema_version: "v1", provider: "football_data_org", competition_code: code, team_count: 0, teams: [] }),
  matchupPreview: (matchId: number) => request<ApiFootballMatchupPreview>(`/football-data/matches/${matchId}/matchup-preview`, {} as ApiFootballMatchupPreview),
};
export const teamProfileApi = {
  catalog: () => request<TrackingTeamProfileCatalogResponse>("/team-profile-catalog", { schema_version: "v1", profiles: [] }),
  shapeStyle: (teamId: string) => request<FootballShapeProfile>(`/teams/${teamId}/shape-style`, {} as FootballShapeProfile),
  summary: (teamId: string) => request<TeamProfileSummaryResponse>(`/teams/${teamId}/summary`, { schema_version: "v1", team: { team_id: teamId, name: "Team Profile", provider_team_ids: {} }, analysed_match_count: 0, excluded_match_count: 0, profile_evidence_band: "insufficient", profile_baseline_label: "no analysed-match baseline", providers: [], capability_coverage: [], sample_periods: [] }),
  metrics: (teamId: string) => request<{ schema_version: "v1"; metric_baselines: TeamMetricBaseline[] }>(`/teams/${teamId}/metrics`, { schema_version: "v1", metric_baselines: [] }),
  families: (teamId: string) => request<{ schema_version: "v1"; recurring_finding_families: Array<{ provider: string; finding_family: string; contributing_matches: number; finding_count: number; match_ids: Array<string | number> }> }>(`/teams/${teamId}/finding-families`, { schema_version: "v1", recurring_finding_families: [] }),
  matches: (teamId: string) => request<{ schema_version: "v1"; included_matches: Array<Record<string, unknown>>; excluded_matches: Array<{ match_id: string | number; provider: string; reason: string }> }>(`/teams/${teamId}/matches`, { schema_version: "v1", included_matches: [], excluded_matches: [] }),
  deviations: (teamId: string) => request<{ schema_version: "v1"; match_deviations: TeamDeviation[] }>(`/teams/${teamId}/deviations`, { schema_version: "v1", match_deviations: [] }),
};
export const eventProfileApi = {
  footballStyle: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<FootballStyleProfile>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/football-style`, {} as FootballStyleProfile),
  styleConceptMoments: (provider: string, teamId: string, competitionId: string, seasonId: string, conceptId: string, limit = 6) => request<TeamStyleVisualExamples>(`/event-profiles/${encodeURIComponent(provider)}/${encodeURIComponent(teamId)}/${encodeURIComponent(competitionId)}/${encodeURIComponent(seasonId)}/style-concepts/${encodeURIComponent(conceptId)}/moments?limit=${limit}`, { schema_version: "v1", concept_id: conceptId, supported: false, representative_moments: [], representative_moment_details: [], query_mappings: [], limitations: ["Visual examples require canonical event data."] }),
  matchTacticalAnalysis: (provider: string, teamId: string, competitionId: string, seasonId: string, matchId: string | number) => request<MatchTacticalProfile>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/matches/${matchId}/tactical-analysis`, {} as MatchTacticalProfile),
  summary: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<EventProfileSummary>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/summary`, { schema_version: "v1", profile_type: "event_team_season", team: { team_id: teamId, name: "Event Team Profile" }, provider, competition_id: competitionId, competition_name: null, season_id: seasonId, season_name: null, analysed_match_count: 0, excluded_match_count: 0, coordinate_system: "statsbomb_120x80", capabilities: { has_events: true, has_lineups: true, has_continuous_tracking: false }, finding_count: 0 }),
  baselines: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; season_baselines: EventSeasonBaseline[] }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/baselines`, { schema_version: "v1", season_baselines: [] }),
  findings: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; findings: EventProfileFinding[]; suppressed_duplicate_count: number }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/findings`, { schema_version: "v1", findings: [], suppressed_duplicate_count: 0 }),
  tendencies: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; recurring_event_profile_tendencies: EventProfileTendency[] }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/tendencies`, { schema_version: "v1", recurring_event_profile_tendencies: [] }),
  unusualMatches: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; unusual_matches: EventUnusualMatch[] }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/unusual-matches`, { schema_version: "v1", unusual_matches: [] }),
  archetypes: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; season_summary: MatchArchetypeSummary[]; match_assignments: MatchArchetypeAssignment[]; total_matches: number }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/archetypes`, { schema_version: "v1", season_summary: [], match_assignments: [], total_matches: 0 }),
  relationships: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; relationship_fits: MetricRelationshipFit[]; findings: MetricRelationshipFinding[]; total_matches: number }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/relationships`, { schema_version: "v1", relationship_fits: [], findings: [], total_matches: 0 }),
  matches: (provider: string, teamId: string, competitionId: string, seasonId: string) => request<{ schema_version: "v1"; matches: EventProfileMatch[] }>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/matches`, { schema_version: "v1", matches: [] }),
  matchStory: (provider: string, teamId: string, competitionId: string, seasonId: string, matchId: string | number) => request<MatchStoryResponse>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/matches/${matchId}/story`, { schema_version: "v1", team_id: teamId, team_name: "Event Team Profile", match_id: matchId, maximum_story_points: 4, status: "no_qualifying_patterns", message: "No unusual season-relative patterns qualified. This does not mean the match lacked important events.", presentation_mode: "no_qualifying_patterns", coherence_linkages: [], match_context: { opponent_team_id: null, opponent_team_name: null, home_away: null, team_score: null, opponent_score: null, team_relative_score: null, match_date: null, score_state_exposure: {}, score_state_source: null }, story_points: [], candidate_audit: [] }),
  matchStoryExplanation: (provider: string, teamId: string, competitionId: string, seasonId: string, matchId: string | number) => request<MatchStoryExplanationResponse>(`/event-profiles/${provider}/${teamId}/${competitionId}/${seasonId}/matches/${matchId}/story/explanation`, { schema_version: "v1", match_id: matchId, explanation: { headline: "No unusual season-relative patterns qualified", summary: "No unusual season-relative patterns qualified. This does not mean the match lacked important events.", story_point_explanations: [], what_to_review_in_video: [], evidence_caveat: "No explanatory narrative was generated when the deterministic Match Story was empty." }, metadata: { evidence_hash: "mock-story-evidence", prompt_version: "tactiq-match-story-explanation-v1", provider_id: "deterministic", model_id: "deterministic_fallback", source: "deterministic_fallback", cache_hit: false, validation_warnings: [] } }),
};
const opponentPath = (target: string[], opponent: string[], resource: string) =>
  `/opponent-comparisons/${[...target, ...opponent].map(encodeURIComponent).join("/")}/${resource}`;
const emptyOpponentSummary = (target: string[], opponent: string[]): OpponentComparisonSummary => ({ schema_version: "v1", comparison_type: "event_team_season", target: { provider: target[0], team_id: target[1], team_name: "Target team", competition_id: target[2], competition_name: null, season_id: target[3], season_name: null, analysed_match_count: 0, coordinate_system: "statsbomb_120x80" }, opponent: { provider: opponent[0], team_id: opponent[1], team_name: "Opponent", competition_id: opponent[2], competition_name: null, season_id: opponent[3], season_name: null, analysed_match_count: 0, coordinate_system: "statsbomb_120x80" }, compatibility: { comparable: true, provider_rule: "same_provider", coordinate_system: "statsbomb_120x80", required_capabilities: ["has_events"], target_capabilities: { has_events: true, has_continuous_tracking: false }, opponent_capabilities: { has_events: true, has_continuous_tracking: false } }, configuration: { minimum_contributing_matches: 10, minimum_coverage: .8, material_iqr_overlap_threshold: .25, finding_minimum_absolute_standardized_difference: 1, difference_sign_convention: "opponent_minus_target", unit_of_historical_evidence: "match" }, compared_metric_count: 0, excluded_metric_count: 0, finding_count: 0 });
export const opponentComparisonApi = {
  briefing: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; briefing: PreMatchBriefing }>(opponentPath(target, opponent, "briefing"), {} as { schema_version: "v1"; briefing: PreMatchBriefing }),
  summary: (target: string[], opponent: string[]) => request<OpponentComparisonSummary>(opponentPath(target, opponent, "summary"), emptyOpponentSummary(target, opponent)),
  metrics: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; metric_comparisons: OpponentMetricComparison[]; excluded_metrics: Array<{ family: string; metric: string; reason: string }> }>(opponentPath(target, opponent, "metrics"), { schema_version: "v1", metric_comparisons: [], excluded_metrics: [] }),
  findings: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; ranked_comparison_findings: OpponentComparisonFinding[] }>(opponentPath(target, opponent, "findings"), { schema_version: "v1", ranked_comparison_findings: [] }),
  interactions: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; directional_interactions: MatchupInteraction[]; excluded_interactions: Array<{ direction_id: string; attacking_team_id: string | number; defending_team_id: string | number; interaction_family: string; reason: string }> }>(opponentPath(target, opponent, "interactions"), { schema_version: "v1", directional_interactions: [], excluded_interactions: [] }),
  interactionFindings: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; ranked_interaction_findings: MatchupInteractionFinding[] }>(opponentPath(target, opponent, "interaction-findings"), { schema_version: "v1", ranked_interaction_findings: [] }),
  reviewPriorities: (target: string[], opponent: string[]) => request<{ schema_version: "v1"; review_priorities: PreMatchReviewPriority[]; candidate_audit: Array<Record<string, unknown>> }>(opponentPath(target, opponent, "review-priorities"), { schema_version: "v1", review_priorities: [], candidate_audit: [] }),
  reviewPriorityMoments: (target: string[], opponent: string[], priorityId: string) => request<{ schema_version: "v1"; priority_id: string; supported: boolean; representative_moments: RepresentativeMoment[]; moment_patterns: MomentPattern[]; moment_pattern_assignments: MomentPatternAssignment[]; pattern_context_summaries: PatternContextSummary[]; pattern_limitations: string[]; moment_sequence_features: MomentSequenceFeatures[]; moment_sequence_patterns: MomentSequencePattern[]; moment_sequence_similarities: MomentSequenceSimilarity[]; moment_sequence_limitations: string[]; query_mappings: Array<Record<string, unknown>>; limitations: string[] }>(`${opponentPath(target, opponent, "review-priorities")}/${encodeURIComponent(priorityId)}/moments`, { schema_version: "v1", priority_id: priorityId, supported: false, representative_moments: [], moment_patterns: [], moment_pattern_assignments: [], pattern_context_summaries: [], pattern_limitations: [], moment_sequence_features: [], moment_sequence_patterns: [], moment_sequence_similarities: [], moment_sequence_limitations: [], query_mappings: [], limitations: ["Representative moments require the local event API."] }),
  reviewPriorityEvidencePack: (target: string[], opponent: string[], priorityId: string) => request<{ schema_version: "v1"; priority_id: string; evidence_pack: PreMatchEvidencePack }>(`${opponentPath(target, opponent, "review-priorities")}/${encodeURIComponent(priorityId)}/evidence-pack`, {} as { schema_version: "v1"; priority_id: string; evidence_pack: PreMatchEvidencePack }),
  reviewPriorityMomentDetail: (target: string[], opponent: string[], priorityId: string, eventId: string) => request<{ schema_version: "v1"; priority_id: string; event_id: string; supported: boolean; detail: RepresentativeMomentDetail | null; limitations: string[] }>(`${opponentPath(target, opponent, "review-priorities")}/${encodeURIComponent(priorityId)}/moments/${encodeURIComponent(eventId)}`, { schema_version: "v1", priority_id: priorityId, event_id: eventId, supported: false, detail: null, limitations: ["Representative moment detail requires the local event API."] }),
};
export const profileCatalogApi = {
  list: () => request<EventProfileCatalogResponse>("/event-profile-catalog", {
    schema_version: "v1",
    profiles: [
      { provider: "statsbomb_open_data", team_id: 217, team_name: "Barcelona", competition_id: 11, competition_name: "La Liga", season_id: 27, season_name: "2015/2016", analysed_match_count: 38 },
      { provider: "statsbomb_open_data", team_id: 220, team_name: "Real Madrid", competition_id: 11, competition_name: "La Liga", season_id: 27, season_name: "2015/2016", analysed_match_count: 38 },
    ],
    excluded: [],
  }),
};
