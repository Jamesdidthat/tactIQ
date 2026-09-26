"""Descriptive analysis built on validated TactIQ data layers."""

from .phase_shape import summarize_phase_shape
from .outcome_linked_shape import summarize_defensive_shape_by_outcome
from .multimatch_pipeline import (
    MultiMatchPipelineResult,
    discover_match_directories,
    process_skillcorner_matches,
)
from .cross_match_outcomes import (
    compare_defensive_shape_by_shot_outcome,
    compare_phase_relative_defensive_shape_by_shot_outcome,
)
from .low_block_line_structure import compare_low_block_line_structure_by_shot_outcome
from .low_block_ball_relative import compare_low_block_ball_relative_by_shot_outcome
from .shot_sequence_temporal import audit_shot_sequence_timing
from .pre_shot_trajectory import build_pre_shot_trajectory_analysis
from .conditional_outcomes import exploratory_conditional_outcomes
from .local_defensive_trajectory import build_local_defensive_context_trajectory
from .attacking_sequence_audit import (
    audit_attacking_pre_shot_sequences, build_shot_sequence_descriptors,
    summarize_descriptor_matched_pair_coverage,
)
from .finish_carry_trajectory import summarize_finish_carry_matched_trajectories
from .tactical_findings import MatchAnalysisResult, TacticalFinding, run_match_analysis
from .team_shape_evidence import group_high_tail_episodes, select_typical_and_extreme_moments
from .finding_prioritization import EvidencePack, FindingPriority, FindingPrioritizationResult, prioritize_findings
from .team_profile import TeamProfileIdentity, TeamProfileResult, build_team_profile
from .team_profile_cache import (
    TEAM_PROFILE_CACHE_SCHEMA_VERSION,
    TEAM_PROFILE_VERSION,
    TeamProfileArtifactStore,
    precompute_team_profile,
    reconstruct_team_profile,
)
from .dataset_inventory import DatasetInventoryResult, build_dataset_inventory
from .event_team_profile import (
    EventTeamProfileResult, EventTeamSeasonProfile, aggregate_event_team_match_metrics,
    build_event_team_season_profile,
    calculate_event_team_match_metrics, metric_definitions,
)
from .event_profile_findings import (
    EventProfileFinding, EventProfileFindingResult,
    generate_event_profile_findings,
)
from .match_archetypes import (
    MatchArchetype, MatchArchetypeResult, archetype_rule_definitions,
    build_match_archetypes,
)
from .metric_relationships import (
    MetricRelationshipFinding, MetricRelationshipResult,
    build_metric_relationship_deviations,
)
from .match_story import MatchStoryPoint, MatchStoryResult, assemble_match_story
from .opponent_comparison import (
    OpponentComparisonFinding, OpponentComparisonResult, compare_event_team_profiles,
)
from .matchup_interactions import (
    MatchupInteractionFinding, MatchupInteractionResult, analyze_matchup_interactions,
)
from .pre_match_review import (
    PreMatchReviewPriority, PreMatchReviewResult, ReviewPriorityEvidenceCompatibility,
    build_metric_review_question, build_pre_match_review_priorities,
)
from .representative_moments import (
    RepresentativeMoment, RepresentativeMomentResult, build_representative_match_moments,
    build_team_style_concept_moments,
)
from .moment_360_context import Moment360Context, SnapshotPlayer, build_moment_360_context
from .pattern_context_comparison import (
    DEFAULT_MINIMUM_360_SAMPLE, PatternContextMetricSummary, PatternContextSummary,
    build_pattern_context_summaries,
)
from .representative_moment_detail import (
    MomentSequenceEvent, RepresentativeMomentDetail, build_representative_moment_detail,
)
from .moment_patterns import (
    MomentPattern, MomentPatternAssignment, MomentPatternResult,
    build_moment_patterns, classify_moment_patterns,
)
from .moment_sequence_similarity import (
    MomentSequenceFeatures, MomentSequenceGroupingResult, MomentSequencePattern,
    MomentSequenceSimilarity, build_moment_sequence_grouping,
    derive_moment_sequence_features, sequence_feature_distance,
)
from .pre_match_evidence_pack import PreMatchEvidencePack, build_pre_match_evidence_pack
from .pre_match_briefing import PreMatchBriefing, PreMatchBriefingPriority, build_pre_match_briefing
from .football_style_profile import (
    FootballConceptEvidence, FootballStyleConcept, FootballStyleProfile, TeamStyleDimension,
    build_football_style_profile,
)
from .football_shape_profile import (
    FootballShapeConcept, FootballShapeProfile, ShapeConceptEvidence,
    ShapeFrameReference, build_football_shape_profile,
)
from .match_tactical_profile import (
    GoalAnalysis, GoalContributor, GoalSequenceAction, MatchStyleDeviation,
    MatchTacticalProfile, MatchTimeSegment, TeamMatchTacticalProfile,
    build_match_tactical_profile,
)

__all__ = [
    "MultiMatchPipelineResult",
    "compare_defensive_shape_by_shot_outcome",
    "compare_phase_relative_defensive_shape_by_shot_outcome",
    "compare_low_block_line_structure_by_shot_outcome",
    "compare_low_block_ball_relative_by_shot_outcome",
    "audit_shot_sequence_timing",
    "build_pre_shot_trajectory_analysis",
    "exploratory_conditional_outcomes",
    "build_local_defensive_context_trajectory",
    "audit_attacking_pre_shot_sequences",
    "build_shot_sequence_descriptors",
    "summarize_descriptor_matched_pair_coverage",
    "summarize_finish_carry_matched_trajectories",
    "discover_match_directories",
    "process_skillcorner_matches",
    "summarize_defensive_shape_by_outcome",
    "summarize_phase_shape",
    "MatchAnalysisResult",
    "TacticalFinding",
    "run_match_analysis",
    "group_high_tail_episodes",
    "select_typical_and_extreme_moments",
    "EvidencePack",
    "FindingPriority",
    "FindingPrioritizationResult",
    "prioritize_findings",
    "TeamProfileIdentity",
    "TeamProfileResult",
    "build_team_profile",
    "TEAM_PROFILE_CACHE_SCHEMA_VERSION",
    "TEAM_PROFILE_VERSION",
    "TeamProfileArtifactStore",
    "precompute_team_profile",
    "reconstruct_team_profile",
    "DatasetInventoryResult",
    "build_dataset_inventory",
    "EventTeamSeasonProfile",
    "EventTeamProfileResult",
    "aggregate_event_team_match_metrics",
    "build_event_team_season_profile",
    "calculate_event_team_match_metrics",
    "metric_definitions",
    "EventProfileFinding",
    "EventProfileFindingResult",
    "generate_event_profile_findings",
    "MatchArchetype",
    "MatchArchetypeResult",
    "archetype_rule_definitions",
    "build_match_archetypes",
    "MetricRelationshipFinding",
    "MetricRelationshipResult",
    "build_metric_relationship_deviations",
    "MatchStoryPoint",
    "MatchStoryResult",
    "assemble_match_story",
    "OpponentComparisonFinding",
    "OpponentComparisonResult",
    "compare_event_team_profiles",
    "MatchupInteractionFinding",
    "MatchupInteractionResult",
    "analyze_matchup_interactions",
    "PreMatchReviewPriority",
    "PreMatchReviewResult",
    "ReviewPriorityEvidenceCompatibility",
    "build_metric_review_question",
    "build_pre_match_review_priorities",
    "RepresentativeMoment",
    "RepresentativeMomentResult",
    "build_representative_match_moments",
    "build_team_style_concept_moments",
    "Moment360Context",
    "SnapshotPlayer",
    "build_moment_360_context",
    "DEFAULT_MINIMUM_360_SAMPLE",
    "PatternContextMetricSummary",
    "PatternContextSummary",
    "build_pattern_context_summaries",
    "MomentSequenceEvent",
    "RepresentativeMomentDetail",
    "build_representative_moment_detail",
    "MomentPattern",
    "MomentPatternAssignment",
    "MomentPatternResult",
    "build_moment_patterns",
    "classify_moment_patterns",
    "MomentSequenceFeatures",
    "MomentSequenceGroupingResult",
    "MomentSequencePattern",
    "MomentSequenceSimilarity",
    "build_moment_sequence_grouping",
    "derive_moment_sequence_features",
    "sequence_feature_distance",
    "PreMatchEvidencePack",
    "build_pre_match_evidence_pack",
    "PreMatchBriefing",
    "FootballConceptEvidence",
    "FootballStyleConcept",
    "FootballStyleProfile",
    "TeamStyleDimension",
    "build_football_style_profile",
    "FootballShapeConcept",
    "FootballShapeProfile",
    "ShapeConceptEvidence",
    "ShapeFrameReference",
    "build_football_shape_profile",
    "GoalAnalysis",
    "GoalContributor",
    "GoalSequenceAction",
    "MatchStyleDeviation",
    "MatchTacticalProfile",
    "MatchTimeSegment",
    "TeamMatchTacticalProfile",
    "build_match_tactical_profile",
    "PreMatchBriefingPriority",
    "build_pre_match_briefing",
]
