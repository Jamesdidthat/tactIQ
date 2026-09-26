export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

export interface TeamHeader { team_id: string | number | null; name: string | null; code: string | null; score: number | null; crest_url?: string | null; }
export interface MatchSummaryResponse {
  schema_version: "v1";
  match: { match_id: string | number; provider: string; pitch_length_m: number; pitch_width_m: number; date_time: string | null; home_team: TeamHeader; away_team: TeamHeader; };
  capabilities: Record<string, boolean>;
  finding_count: number;
  shortlist_count: number;
  warnings: string[];
  analysis_coverage: AnalysisCoverage[];
}
export interface AnalysisCoverage { analysis: string; supported: boolean; status: "run" | "skipped" | "available_not_implemented"; reason: string; finding_count: number; }
export interface Priority { evidence_strength: number; sample_adequacy: number; effect_magnitude: number; temporal_relevance: number; data_quality_coverage: number; redundancy_penalty: number; priority_score: number; comparator: Record<string, Json>; suppressed_as_duplicate: boolean; redundancy_group: string; }
export interface RankedFinding { rank: number; finding_id: string; match_id: string | number; team_id: string | number; finding_type: string; title: string; description: string; sample_size: number; confidence_level: string; selection_reason?: string | null; priority: Priority; limitations: string[]; }
export interface RankedFindingsResponse { schema_version: "v1"; ranked_findings: RankedFinding[]; }
export interface EvidenceMoment { frame?: number; period?: number; timestamp?: string; elapsed_seconds?: number; phase_frame_start?: number; phase_frame_end?: number; tactical_phase?: string; possession_status?: string; extreme_episode_id?: number; episode_frame_start?: number; episode_frame_end_inclusive?: number; episode_frame_count?: number; is_at_or_above_q95?: boolean; label?: string; metric?: string; metric_value_metres?: number; target_quantile?: number; target_value_metres?: number; target_error_metres?: number; }
export interface FindingDetailResponse { schema_version: "v1"; finding: RankedFinding; evidence: { exact_metrics: Record<string, Json>; comparator: Record<string, Json>; supporting_references: EvidenceMoment[]; representative_moments: EvidenceMoment[]; capability_provenance: { provider: string; capabilities: Record<string, boolean>; required_capabilities: string[]; allow_assumed_roles: boolean; }; coverage: { analysis_coverage: AnalysisCoverage[]; finding_sample_size: number; reference_count: number; }; limitations: string[]; }; }
export interface FindingExplanationResponse { schema_version: "v1"; finding_id: string; explanation: { plain_english_summary: string; why_it_matters: string; what_to_review_in_video: string; confidence_note: string; }; metadata: { evidence_hash: string; prompt_version: string; model_id: string; source: "model" | "deterministic_fallback"; cache_hit: boolean; validation_warnings: string[]; }; }
export type ProfileEvidenceBand = "insufficient" | "provisional" | "developing" | "established";
export type MetricUnit = "metres" | "count";
export interface TeamProfileSummaryResponse { schema_version: "v1"; team: { team_id: string | number; name: string; provider_team_ids: Record<string, string | number> }; analysed_match_count: number; excluded_match_count: number; profile_evidence_band: ProfileEvidenceBand; profile_baseline_label: string; providers: string[]; capability_coverage: Array<{ capability: string; available_matches: number; included_matches: number; coverage: number; providers: string }>; sample_periods: Array<{ match_id: string | number; provider: string; period: number; tracked_frames: number; represented_seconds: number }> }
export interface TeamMetricBaseline { provider: string; provider_label: string; provenance_label: string; capability_signature: string; metric_family: string; metric: string; unit: MetricUnit; possession_status: string | null; tactical_phase: string | null; required_capabilities: string; median_across_matches: number; q25_across_matches: number; q75_across_matches: number; contributing_matches: number; evidence_band: ProfileEvidenceBand; baseline_label: string; match_ids: Array<string | number> }
export interface TeamDeviation { match_id: string | number; provider: string; provider_label: string; provenance_label: string; metric_family: string; metric: string; unit: MetricUnit; possession_status: string | null; tactical_phase: string | null; value: number; team_baseline: number; deviation_from_baseline: number; absolute_deviation: number; deviation_label: string; capability_signature: string; required_capabilities: string; contributing_matches: number; evidence_band: ProfileEvidenceBand; baseline_label: string; comparison_label: string; evidence_finding_id?: string | null; match_analysis_path: string; link_label: "View evidence" | "View match" }
export type EventMetricUnit = "count" | "per_90" | "proportion" | "xG" | "xG_per_90" | "native_120x80_units";
export interface EventProfileSummary { schema_version: "v1"; profile_type: "event_team_season"; team: { team_id: string | number; name: string }; provider: string; competition_id: string | number; competition_name: string | null; season_id: string | number; season_name: string | null; analysed_match_count: number; excluded_match_count: number; coordinate_system: string; capabilities: Record<string, boolean>; finding_count: number; }
export interface EventSeasonBaseline { metric: string; unit: EventMetricUnit; median_across_matches: number; q25_across_matches: number; q75_across_matches: number; contributing_matches: number; total_matches: number; coverage: number; coordinate_system: string | null; definition: string; }
export interface EventProfileFinding { finding_id: string; source_match_id: string | number; finding_family: string; metric: string; title: string; description: string; observed_value: number; season_baseline: number; signed_deviation: number; absolute_deviation: number; relative_deviation: number | null; robust_z_score: number; contributing_match_count: number; coverage: number; evidence_level: "limited" | "moderate" | "strong"; unit: EventMetricUnit; definition: string; }
export interface EventProfileTendency { finding_family: string; unusual_matches: number; finding_count: number; above_baseline: number; below_baseline: number; strongest_robust_z: number; }
export interface EventUnusualMatch { match_id: string | number; match_date: string | null; strongest_metric: string; strongest_robust_z: number; absolute_robust_z: number; observed_value: number; season_baseline: number; unit: EventMetricUnit; meaningful_finding_count: number; match_analysis_path: string; }
export interface MatchArchetypeSummary { archetype: string; title: string; description: string; match_count: number; match_share: number; representative_match_ids: Array<string | number>; representative_rule_strengths: number[]; }
export interface MatchArchetypeAssignment { archetype_id: string; match_id: string | number; archetype: string; title: string; description: string; rule_threshold: number; rule_strength: number; evidence_level: "exploratory" | "moderate" | "strong"; contributing_metrics: Array<{ metric: string; required_direction: "high" | "low"; observed_value: number; season_baseline: number; robust_z_score: number; contributing_match_count: number; coverage: number; unit: EventMetricUnit; definition: string }>; }
export interface MetricRelationshipFit { upstream_metric: string; downstream_metric: string; method: string; slope: number; intercept: number; equation: string; spearman_rank_correlation: number | null; slope_leave_one_out_low: number | null; slope_leave_one_out_high: number | null; slope_interval_kind: string; residual_q25: number; residual_q75: number; residual_robust_scale: number | null; residual_scale_method: string; descriptive_prediction_half_width_95: number | null; prediction_interval_kind: string; contributing_match_count: number; coverage: number; }
export interface MetricRelationshipFinding { finding_id: string; match_id: string | number; upstream_metric: string; downstream_metric: string; title: string; description: string; upstream_value: number; observed_downstream_value: number; expected_downstream_value: number; residual: number; absolute_residual: number; residual_robust_z: number; contributing_match_count: number; coverage: number; evidence_level: "moderate" | "strong"; relationship_method: string; slope: number; intercept: number; residual_prediction_low: number; residual_prediction_high: number; }
export interface EventProfileMatch { match_id: string | number; match_date: string | null; opponent_team_id: string | number | null; opponent_team_name: string | null; home_away: string | null; team_score: number | null; opponent_score: number | null; match_minutes: number | null; }
export type MatchStorySourceType = "metric_relationship_residual" | "match_archetype" | "single_metric_deviation";
export interface MatchStorySupportingMetric {
  metric: string;
  observed_value?: number;
  season_baseline?: number;
  robust_z_score?: number;
  unit?: EventMetricUnit;
  definition?: string;
  required_direction?: "high" | "low";
}
export interface MatchStoryPoint {
  story_id: string;
  story_type: MatchStorySourceType;
  title: string;
  observation: string;
  supporting_metrics: MatchStorySupportingMetric[];
  comparator: Record<string, unknown>;
  deviation: Record<string, unknown>;
  evidence_level: "exploratory" | "limited" | "moderate" | "strong";
  source_match_id: string | number;
  contributing_season_match_count: number;
  coverage: number;
  limitations: string[];
  redundancy_group: string;
  priority_score: number;
  priority_components: Record<string, number>;
  selection_reason: string;
  semantic_topic: string;
  chronology: { available: boolean; first_seconds?: number; median_seconds?: number; last_seconds?: number; event_count?: number; approximate_match_phase?: string; basis: string };
  evidence_basis: "High" | "Moderate" | "Limited";
  primary_evidence_basis: "High" | "Moderate" | "Limited";
  supporting_evidence_bases: Array<{ candidate_id: string; story_type: MatchStorySourceType; evidence_level: string; evidence_basis: "High" | "Moderate" | "Limited"; is_primary: boolean }>;
  merged_candidate_ids: string[];
}
export interface MatchStoryResponse { schema_version: "v1"; team_id: string | number; team_name: string; match_id: string | number; maximum_story_points: number; status: "story_available" | "no_qualifying_patterns"; message: string | null; presentation_mode: "connected_story" | "parallel_observations" | "no_qualifying_patterns"; coherence_linkages: Array<Record<string, unknown>>; match_context: { opponent_team_id: string | number | null; opponent_team_name: string | null; home_away: string | null; team_score: number | null; opponent_score: number | null; team_relative_score: string | null; match_date: string | null; score_state_exposure: Record<string, { seconds: number | null; share: number | null }>; score_state_source: string | null }; story_points: MatchStoryPoint[]; candidate_audit: Array<Record<string, unknown>>; }
export interface MatchStoryExplanationResponse {
  schema_version: "v1";
  match_id: string | number;
  explanation: {
    headline: string;
    summary: string;
    story_point_explanations: Array<{ story_id: string; explanation: string }>;
    what_to_review_in_video: Array<{ story_id: string; guidance: string }>;
    evidence_caveat: string;
  };
  metadata: {
    evidence_hash: string;
    prompt_version: string;
    provider_id: string;
    model_id: string;
    source: "model" | "deterministic_fallback";
    cache_hit: boolean;
    validation_warnings: string[];
  };
}
export interface OpponentComparisonIdentity { provider: string; team_id: string | number; team_name: string; competition_id: string | number; competition_name: string | null; season_id: string | number; season_name: string | null; analysed_match_count: number; coordinate_system: string | null; }
export interface OpponentComparisonSummary { schema_version: "v1"; comparison_type: "event_team_season"; target: OpponentComparisonIdentity; opponent: OpponentComparisonIdentity; compatibility: { comparable: boolean; provider_rule: string; coordinate_system: string | null; required_capabilities: string[]; target_capabilities: Record<string, boolean>; opponent_capabilities: Record<string, boolean> }; configuration: { minimum_contributing_matches: number; minimum_coverage: number; material_iqr_overlap_threshold: number; finding_minimum_absolute_standardized_difference: number; difference_sign_convention: "opponent_minus_target"; unit_of_historical_evidence: "match" }; compared_metric_count: number; excluded_metric_count: number; finding_count: number; }
export interface OpponentMetricComparison { family: string; metric: string; metric_label: string; unit: EventMetricUnit; definition: string; target_median: number; target_q25: number; target_q75: number; target_contributing_matches: number; target_coverage: number; target_robust_scale: number | null; opponent_median: number; opponent_q25: number; opponent_q75: number; opponent_contributing_matches: number; opponent_coverage: number; opponent_robust_scale: number | null; signed_difference: number; absolute_difference: number; relative_difference: number | null; standardized_by_target_variability: number | null; standardized_by_opponent_variability: number | null; combined_standardized_difference: number | null; iqr_overlap_ratio: number; distributions_materially_overlap: boolean; difference_sign_convention: "opponent_minus_target"; }
export interface OpponentComparisonFinding { finding_id: string; rank: number; finding_family: string; metric: string; title: string; description: string; target_value: number; opponent_value: number; signed_difference: number; relative_difference: number | null; combined_standardized_difference: number; distributions_materially_overlap: boolean; evidence_basis: "High" | "Moderate" | "Limited"; priority_score: number; contributing_matches_target: number; contributing_matches_opponent: number; coverage_target: number; coverage_opponent: number; unit: EventMetricUnit; limitations: string[]; }
export type ReviewEvidenceCompatibility = "same_metric" | "direct_attack_vs_defence_counterpart" | "validated_relationship" | "unsupported_cross_metric";
export interface MatchupInteraction { direction_id: string; attacking_team_id: string | number; attacking_team_name: string; defending_team_id: string | number; defending_team_name: string; interaction_family: string; production_metric: string; exposure_metric: string; interaction_label: string; comparability_basis: string; review_priority_compatibility: ReviewEvidenceCompatibility; unit: EventMetricUnit; production_definition: string; exposure_definition: string; attacking_median: number; attacking_q25: number; attacking_q75: number; attacking_contributing_matches: number; attacking_coverage: number; attacking_robust_scale: number | null; defending_exposure_median: number; defending_exposure_q25: number; defending_exposure_q75: number; defending_contributing_matches: number; defending_coverage: number; defending_robust_scale: number | null; signed_mismatch: number | null; absolute_mismatch: number | null; standardized_by_attacking_variability: number | null; standardized_by_defending_variability: number | null; combined_standardized_mismatch: number | null; iqr_overlap_ratio: number | null; distributions_materially_overlap: boolean | null; interaction_strength_score: number | null; mismatch_sign_convention: "attacking_production_minus_defending_exposure"; }
export interface MatchupInteractionFinding { finding_id: string; rank_within_direction: number; direction_id: string; attacking_team_id: string | number; attacking_team_name: string; defending_team_id: string | number; defending_team_name: string; interaction_family: string; production_metric: string; exposure_metric: string; review_priority_compatibility: ReviewEvidenceCompatibility; title: string; description: string; attacking_median: number; defending_exposure_median: number; signed_mismatch: number; combined_standardized_mismatch: number; interaction_strength_score: number; evidence_basis: "High" | "Moderate" | "Limited"; attacking_contributing_matches: number; defending_contributing_matches: number; attacking_coverage: number; defending_coverage: number; unit: EventMetricUnit; limitations: string[]; }
export interface PreMatchReviewPriority { priority_id: string; rank: number; title: string; review_question: string; direction: "target_attack_vs_opponent_defence" | "opponent_attack_vs_target_defence" | "opponent_vs_target_season_tendency"; football_family: string; primary_source_role: "directional_matchup_interaction" | "general_team_comparison"; primary_evidence: Record<string, unknown>; supporting_evidence: Array<Record<string, unknown>>; target_baseline: { team_id: string | number; team_name: string; role: string; metric: string; median: number; q25: number; q75: number; unit: EventMetricUnit }; opponent_baseline: { team_id: string | number; team_name: string; role: string; metric: string; median: number; q25: number; q75: number; unit: EventMetricUnit }; interaction_strength: number; evidence_basis: "High" | "Moderate" | "Limited"; match_counts: Record<string, number>; coverage: Record<string, number>; limitations: string[]; source_finding_ids: string[]; priority_score: number; selection_reason: string; }
export interface RepresentativeMoment { match_id: number; team_id: string | number; team_name: string; opponent_id: string | number; opponent_name: string; match_date: string; minute: number; second: number; period: number; event_id: string; event_type: string; metric: string; family: string; description: string; relevant_values: { xg?: number | null; start_coordinates?: number[] | null; end_coordinates?: number[] | null; play_pattern?: string | null; shot_type?: string | null; shot_outcome?: string | null; team_season_shot_xg_distribution?: { q25: number; median: number; q75: number; shot_count: number }; [key: string]: unknown }; score_state: "leading" | "drawing" | "trailing" | null; score_state_verified: boolean; score_state_team_id: string | number; score_state_team_name: string; source_provenance: Record<string, unknown>; video_availability_status: string; reason_selected: string; evidence_side: string; }
export interface PatternContextMetricSummary { metric: string; metric_label: string; unit: string; median: number | null; q25: number | null; q75: number | null; sample_count: number; coverage: number; }
export interface PatternContextSummary { pattern_id: string; pattern_key: string; pattern_name: string; full_event_sample_count: number; full_eligible_event_sample_count: number; event_sample_share: number; snapshot_360_subset_count: number; snapshot_360_coverage: number; minimum_360_sample: number; spatial_summary_available: boolean; scope_statement: string; metric_summaries: PatternContextMetricSummary[]; capability_provenance: Record<string, unknown>; limitations: string[]; }
export interface MomentPattern { pattern_id: string; pattern_key: string; pattern_name: string; deterministic_definition: string; priority_id: string; relevant_metrics: string[]; moment_count: number; eligible_moment_count: number; share_of_eligible_moments: number; contributing_matches: number[]; representative_moment_ids: string[]; coordinate_event_field_evidence: Record<string, unknown>; limitations: string[]; capability_provenance: Record<string, unknown>; context_summary: PatternContextSummary; }
export interface MomentPatternAssignment { event_id: string; match_id: number; pattern_ids: string[]; pattern_keys: string[]; }
export interface MomentSequenceFeatures { event_id: string; match_id: number; entry_type: string; start_zone: string | null; end_zone: string | null; corridor: string | null; sequence_length_events: number; sequence_duration_seconds: number; preceding_event_count: number; preceding_pass_count: number; preceding_carry_count: number; sequence_band: string; play_context: string; explicit_counter: boolean; shot_outcome: string | null; shot_xg: number | null; score_state: string | null; score_state_verified: boolean; sequence_pattern_id: string; sequence_pattern_label: string; }
export interface MomentSequencePattern { pattern_id: string; pattern_label: string; count: number; share_of_retrieved_moments: number; contributing_matches: number[]; representative_event_ids: string[]; original_subgroup_ids: string[]; defining_features: Record<string, unknown>; limitations: string[]; }
export interface MomentSequenceSimilarity { event_id_a: string; event_id_b: string; distance: number; similarity: number; compared_feature_count: number; shared_categorical_features: string[]; differing_categorical_features: string[]; }
export interface MomentSequenceEvent { event_id: string; event_index: number; relation_to_focal: "previous" | "focal" | "next"; period: number; minute: number; second: number; elapsed_seconds: number; possession_id: string | number | null; possession_team_id: string | number | null; possession_team_name: string | null; team_id: string | number | null; team_name: string | null; player_id: string | number | null; event_type: string; event_subtype: string | null; outcome: string | null; start_coordinates: [number, number] | null; end_coordinates: [number, number] | null; xg: number | null; play_pattern: string | null; coordinate_system: "statsbomb_120x80"; is_focal: boolean; pitch_renderable: boolean; }
export interface SnapshotPlayer { snapshot_player_index: number; affiliation: "teammate" | "opponent" | "unknown"; teammate: boolean | null; actor: boolean; keeper: boolean; location_x: number; location_y: number; }
export interface Moment360Context { event_id: string; available: boolean; spatial_context_mode: "event_only" | "event_plus_360_snapshot" | "continuous_tracking"; visible_teammate_count: number | null; visible_opponent_count: number | null; visible_unknown_affiliation_count: number | null; nearest_opponent_distance: number | null; nearest_teammate_distance: number | null; opponents_within_radius: Record<string, number>; teammates_within_radius: Record<string, number>; visible_players_ahead_of_event: number | null; visible_players_behind_event: number | null; visible_teammates_ahead_of_event: number | null; visible_opponents_ahead_of_event: number | null; visible_teammates_in_penalty_area: number | null; visible_opponents_in_penalty_area: number | null; visible_player_width_range: number | null; visible_player_depth_range: number | null; event_location_inside_visible_player_hull: boolean | null; event_location_inside_provider_visible_area: boolean | null; snapshot_players: SnapshotPlayer[]; coordinate_provenance: Record<string, unknown>; attacking_direction_provenance: Record<string, unknown>; visibility_limitations: string[]; freeze_frame_source_metadata: Record<string, unknown>; evidence_wording: string; }
export interface RepresentativeMomentDetail { match_id: number; event_id: string; focal_event: MomentSequenceEvent; sequence_events: MomentSequenceEvent[]; context_mode: "same_possession" | "bounded_time_window" | "turnover_to_shot_window"; possession_id: string | number | null; possession_team_id: string | number | null; possession_team_name: string | null; score_state: "leading" | "drawing" | "trailing" | null; score_state_verified: boolean; score_state_team_id: string | number; score_state_team_name: string; phase_context: { label: string; source: string; interpretation: string } | null; coordinate_system: "statsbomb_120x80"; sequence_supported: boolean; source_provenance: Record<string, unknown>; video_availability_status: string; moment_360_context: Moment360Context; limitations: string[]; }
export interface TeamStyleVisualExamples { schema_version: "v1"; concept_id: string; concept_title?: string; supported: boolean; representative_moments: RepresentativeMoment[]; representative_moment_details: RepresentativeMomentDetail[]; query_mappings: Array<Record<string, unknown>>; limitations: string[]; suppressed_duplicates?: Array<Record<string, unknown>>; }
export interface PreMatchEvidencePack {
  priority: PreMatchReviewPriority;
  why_selected: { selection_reason: string; description: string; rank: number; priority_score: number; evidence_support: string; source_finding_ids: string[] };
  primary_source_role: "directional_matchup_interaction" | "general_team_comparison";
  primary_interaction_or_comparison: Record<string, unknown>;
  supporting_tendencies: Array<Record<string, unknown>>;
  season_baselines: { target: PreMatchReviewPriority["target_baseline"]; opponent: PreMatchReviewPriority["opponent_baseline"]; unit_of_historical_evidence: "match" };
  distribution_summary: { target: Record<string, unknown>; opponent: Record<string, unknown>; iqr_overlap_ratio: number | null; distributions_materially_overlap: boolean | null; direction: string };
  sequence_pattern_summaries: { retrieved_sample_count: number; denominator_statement: string; event_patterns: MomentPattern[]; event_sequence_groups: MomentSequencePattern[] };
  representative_moments: RepresentativeMoment[];
  representative_moment_details: RepresentativeMomentDetail[];
  optional_360_context: { available: boolean; observed_moment_count: number; representative_moment_count: number; coverage: number; scope: string; contexts: Moment360Context[]; pattern_context_summaries: PatternContextSummary[] };
  capability_provenance: Record<string, unknown>;
  limitations: string[];
  video_status: { available: boolean; statuses: string[]; message: string };
  technical_provenance: Record<string, unknown>;
}
export interface PreMatchBriefingPriority {
  priority_id: string;
  rank: number;
  title: string;
  review_question: string;
  evidence_summary: string;
  evidence_support: "High" | "Moderate" | "Limited";
  primary_source_role: "directional_matchup_interaction" | "general_team_comparison";
  direction: PreMatchReviewPriority["direction"];
  football_family: string;
  evidence_pack_link: string;
}
export interface PreMatchBriefing {
  matchup_identity: { id: string; target_team_id: string | number; opponent_team_id: string | number; comparison_type: "event_team_season" };
  target_team: OpponentComparisonIdentity;
  opponent_team: OpponentComparisonIdentity;
  competition: { shared: boolean; target: { id: string | number; name: string | null }; opponent: { id: string | number; name: string | null } };
  season: { shared: boolean; target: { id: string | number; name: string | null }; opponent: { id: string | number; name: string | null } };
  briefing_summary: string;
  review_priorities: PreMatchBriefingPriority[];
  evidence_pack_links: Record<string, string>;
  key_comparison_context: Array<Record<string, unknown>>;
  directional_matchup_context: Array<Record<string, unknown>>;
  data_capabilities: { comparable: boolean; provider_rule: string | null; coordinate_system: string | null; required_capabilities: string[]; target_capabilities: Record<string, boolean>; opponent_capabilities: Record<string, boolean>; continuous_tracking_used: boolean };
  limitations: string[];
  video_availability: { status: "available" | "unavailable" | "unknown"; message: string };
}
export interface EventProfileCatalogItem {
  provider: string;
  team_id: string | number;
  team_name: string;
  competition_id: string | number;
  competition_name: string | null;
  season_id: string | number;
  season_name: string | null;
  analysed_match_count: number;
}
export interface EventProfileCatalogResponse {
  schema_version: "v1";
  profiles: EventProfileCatalogItem[];
  excluded: Array<{ identity: string[]; reason: string }>;
}
export interface FootballConceptEvidence {
  metric: string; football_label: string; season_median: number; q25: number; q75: number;
  unit: EventMetricUnit; contributing_matches: number; coverage: number; definition: string;
  representative_matches: Array<{ match_id: string | number; match_date: string | null; opponent_team_name: string | null; home_away: string | null; value: number }>;
}
export interface FootballStyleConcept {
  concept_id: string; title: string; summary: string; what_this_looks_like: string; evidence_basis: "Established" | "Developing" | "Limited" | "Unavailable";
  supporting_evidence: FootballConceptEvidence[]; limitations: string[];
}
export interface TeamStyleDimension { dimension_id: string; label: string; level: "Low" | "Moderate" | "High"; concept_id: string; }
export interface FootballStyleProfile {
  schema_version: "tactiq.football-style-profile.v1"; team_id: string | number; team_name: string;
  competition_id: string | number; competition_name: string | null; season_id: string | number; season_name: string | null;
  analysed_match_count: number; playing_identity: string; style_at_a_glance: TeamStyleDimension[]; in_possession: FootballStyleConcept[];
  out_of_possession: FootballStyleConcept[]; transitions: FootballStyleConcept[]; strengths: FootballStyleConcept[];
  potential_weaknesses: FootballStyleConcept[]; recent_style: FootballStyleConcept[]; recent_window_matches: number;
  capabilities: Record<string, boolean>; limitations: string[];
}
export interface PitchFrameResponse { schema_version: "v1"; match_id: string | number; frame: number; period: number; timestamp: string | null; elapsed_seconds: number; pitch: { length_m: number; width_m: number; }; players: Array<{ player_id: string | number; player_number?: string | number | null; team_id: string | number; team_acronym?: string; position?: string | null; position_group?: string | null; x: number; y: number; is_detected?: boolean; }>; ball: { x: number | null; y: number | null; is_observed: boolean } | null; }
export interface PitchClipResponse { schema_version: "v1"; provider: string; match_id: string | number; period: number; centre_frame: number; focus_index: number; source_frame_rate_hz: number | null; playback_frame_rate_hz: number | null; requested: { before_frames: number; after_frames: number; before_seconds: number | null; after_seconds: number | null; step: number }; actual_start_frame: number; actual_end_frame: number; actual_duration_seconds: number; frames: PitchFrameResponse[]; limitations: string[]; }
export interface ShapeFrameReference { match_id: string | number; frame: number; period: number; label: string; highlight: "none" | "width" | "length" | "team_position" | "defensive_line" | "midfield_line" | "defence_midfield_gap"; clip_before_seconds: number; clip_after_seconds: number; clip_reason: string; }
export interface TrackingTeamProfileCatalogItem { provider: string; team_id: string | number; team_name: string; analysed_match_count: number; excluded_match_count: number; has_continuous_tracking: boolean; }
export interface TrackingTeamProfileCatalogResponse { schema_version: "v1"; profiles: TrackingTeamProfileCatalogItem[]; }
export interface ShapeConceptEvidence { metric: string; metric_label: string; median_metres: number; q25_metres: number; q75_metres: number; contributing_matches: number; tracked_frame_count: number; possession_status: string | null; tactical_phase: string | null; provider: string; required_capabilities: string[]; }
export interface FootballShapeConcept { concept_id: string; headline: string; explanation: string; what_this_looks_like: string; evidence_basis: string; evidence: ShapeConceptEvidence[]; representative_frames: ShapeFrameReference[]; limitations: string[]; }
export interface FootballShapeProfile { schema_version: "tactiq.football-shape-profile.v1"; available: boolean; availability_message: string; team_id: string | number; team_name: string; provider: string | null; source_label: string; with_ball: FootballShapeConcept[]; without_ball: FootballShapeConcept[]; transitions: FootballShapeConcept[]; unsupported_concepts: string[]; limitations: string[]; }
export interface MatchStyleDeviation { metric: string; football_concept: string; observed_value: number; season_median: number; q25: number; q75: number; signed_difference: number; robust_standardized_difference: number | null; contributing_matches: number; coverage: number; football_summary: string; definition: string; }
export interface MatchTimeSegment { segment_id: string; start_minute: number; end_minute: number; team_id: string | number; headline: string; explanation: string; evidence: Record<string, Json>; change_from_previous: string[]; limitations: string[]; }
export interface TeamMatchTacticalProfile { team_id: string | number; team_name: string; opponent_team_id: string | number; opponent_team_name: string; headline: string; overview: string; style_deviations: MatchStyleDeviation[]; segments: MatchTimeSegment[]; tracking_shape: Record<string, Json> | null; opponent_relative_observations: string[]; capabilities_used: string[]; limitations: string[]; }
export interface GoalContributor { category: string; observation: string; evidence: Record<string, Json>; scope: string; }
export interface GoalSequenceAction { event_id: string; order: number; minute: number; second: number; event_type: string; player_id: string | number | null; start_coordinates: [number, number] | null; end_coordinates: [number, number] | null; outcome: string | null; }
export interface GoalAnalysis { goal_id: string; event_id: string; scoring_team_id: string | number; scoring_team_name: string; conceding_team_id: string | number; conceding_team_name: string; period: number; minute: number; second: number; score_state_before_goal: string | null; what_happened: string; what_created_the_opportunity: string; had_this_been_happening_earlier: string; recurring_season_pattern: string; structural_versus_execution: string; sequence_origin: string; sequence_duration_seconds: number; progression_route: string; passes: number; carries: number; shot_location: [number, number] | null; shot_xg: number | null; preceding_actions: GoalSequenceAction[]; contributors: GoalContributor[]; tracking_context: Record<string, Json> | null; comparable_historical_matches: Array<Record<string, Json>>; limitations: string[]; }
export interface MatchTacticalProfile { schema_version: "tactiq.match-tactical-profile.v1"; match_id: string | number; provider: string; match_identity: Record<string, Json>; team_profiles: TeamMatchTacticalProfile[]; goals: GoalAnalysis[]; capabilities: Record<string, boolean>; analysis_coverage: Record<string, string>; limitations: string[]; }

export interface LiveTeam { team_id: number | null; name: string | null; short_name?: string | null; tla?: string | null; logo_url: string | null; winner: boolean | null; }
export interface LiveFixture {
  fixture_id: number; kickoff: string | null; timezone: string | null; referee: string | null;
  venue: { id: number | null; name: string | null; city: string | null };
  status: { long: string | null; short: string | null; elapsed: number | null; extra: number | null; is_live: boolean };
  competition: { league_id: number | null; code?: string | null; name: string | null; country: string | null; logo_url: string | null; flag_url: string | null; season: number | string | null; round: string | null };
  home_team: LiveTeam; away_team: LiveTeam; goals: { home: number | null; away: number | null };
  score: Record<"halftime" | "fulltime" | "extratime" | "penalty", { home: number | null; away: number | null }>;
}
export interface LiveFootballStatus { schema_version: "v1"; provider: "api_football"; configured: boolean; mode: string; capability_note: string; }
export interface LiveLeague { league_id: number; name: string; type: string | null; logo_url: string | null; country: string | null; country_code: string | null; flag_url: string | null; current_season: number; season_start: string | null; season_end: string | null; coverage: Record<string, Json>; }
export interface LiveLeagueCatalog { schema_version: "v1"; provider: "api_football"; league_count: number; leagues: LiveLeague[]; cache_note: string; }
export interface LiveFixtureList { schema_version: "v1"; provider: "api_football"; query: Record<string, string | number | null>; fixture_count: number; fixtures: LiveFixture[]; cache_note: string; }
export interface CurrentCompetition { competition_id: number; code: string; name: string; type: string | null; logo_url: string | null; country: string | null; country_code: string | null; flag_url: string | null; current_season: string | null; season_start: string | null; season_end: string | null; current_matchday: number | null; }
export interface CurrentCompetitionCatalog { schema_version: "v1"; provider: "football_data_org"; competition_count: number; competitions: CurrentCompetition[]; popular_competition_codes: string[]; cache_note: string; }
export interface CurrentTeamCatalog { schema_version: "v1"; provider: "football_data_org"; competition_code: string; team_count: number; teams: LiveTeam[]; }
export interface CurrentFixtureList { schema_version: "v1"; provider: "football_data_org"; competition_code: string; query: Record<string, string | null>; fixture_count: number; fixtures: LiveFixture[]; cache_note: string; }
export interface FootballDataStatus { schema_version: "v1"; provider: "football_data_org"; configured: boolean; mode: string; capability_note: string; }
export interface LiveFixtureSnapshot {
  schema_version: "tactiq.live-match.v1"; provider: "api_football"; fixture: LiveFixture;
  capabilities: Record<string, boolean>;
  events: Array<{ elapsed: number | null; extra: number | null; team: LiveTeam; player: Record<string, Json>; assist: Record<string, Json>; type: string | null; detail: string | null; comments: string | null }>;
  team_statistics: Array<{ team: LiveTeam; statistics: Array<{ label: string | null; value: Json }> }>;
  lineups: Array<{ team: LiveTeam; formation: string | null; coach: Record<string, Json>; starting_xi: Array<Record<string, Json>>; substitutes: Array<Record<string, Json>> }>;
  player_statistics: Array<{ team: LiveTeam; players: Array<Record<string, Json>> }>;
  warnings: string[]; analysis_scope: string;
}
export interface MatchupPreviewTeam {
  team: LiveTeam;
  manager: { manager_id: number | null; name: string; photo_url: string | null; start_date: string | null; verified: boolean };
  matches_in_sample: number; form: string; record: { wins: number; draws: number; losses: number }; most_common_formation: string | null;
  averages: Record<string, number | null>;
  recent_matches: Array<{ fixture_id: number; date: string; opponent: LiveTeam; venue: "Home" | "Away"; result: "W" | "D" | "L"; goals_for: number; goals_against: number; formation: string | null; statistics_available: boolean }>;
  football_read: { control: string; attacking_output: string; defensive_exposure: string };
}
export interface ApiFootballMatchupPreview {
  schema_version: "tactiq.api-football-matchup-preview.v1" | "tactiq.current-matchup-preview.v1"; provider: "api_football" | "football_data_org"; fixture: LiveFixture;
  sample_definition: { requested_recent_matches: number; competition_only: boolean; current_manager_tenure_only: boolean; unit_of_evidence: string };
  teams: MatchupPreviewTeam[];
  matchup_read: Array<{ title: string; explanation: string; evidence: Record<string, Json> }>;
  basic_stats_note: string; limitations: string[]; request_efficiency: string;
}
