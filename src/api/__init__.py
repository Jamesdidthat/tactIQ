"""Product-facing, JSON-safe local analysis service."""

from .match_analysis_service import MatchAnalysisService
from .team_profile_service import TeamProfileService
from .event_profile_service import EventProfileService, artifact_event_profile_resolver, load_event_profile_artifact
from .opponent_comparison_service import OpponentComparisonService

__all__ = [
    "MatchAnalysisService", "TeamProfileService", "EventProfileService",
    "artifact_event_profile_resolver", "load_event_profile_artifact",
    "OpponentComparisonService",
]
