"""Provider adapters, canonical contracts, and SkillCorner transformations."""

from .canonical import (
    CanonicalMatchBundle,
    ProviderCapabilities,
    require_analysis_support,
    supported_analyses,
    validate_canonical_bundle,
)
from .metrica import load_metrica_sample_game, sample_game_1_role_map, validate_canonical_metrica_data
from .phase_context import audit_phase_context_join, expand_phase_context, join_phase_context_to_team_shape
from .skillcorner import load_skillcorner_match, preflight_skillcorner_phase_periods
from .statsbomb import (
    STATSBOMB_PROVIDER,
    StatsBombOpenDataAdapter,
    statsbomb_team_coverage,
    validate_statsbomb_bundle,
)
from .tracking import flatten_player_tracking

__all__ = [
    "CanonicalMatchBundle", "ProviderCapabilities", "audit_phase_context_join",
    "expand_phase_context", "flatten_player_tracking", "join_phase_context_to_team_shape",
    "load_metrica_sample_game", "load_skillcorner_match", "require_analysis_support",
    "preflight_skillcorner_phase_periods",
    "STATSBOMB_PROVIDER", "StatsBombOpenDataAdapter", "statsbomb_team_coverage",
    "validate_statsbomb_bundle",
    "sample_game_1_role_map", "supported_analyses", "validate_canonical_bundle",
    "validate_canonical_metrica_data",
]
