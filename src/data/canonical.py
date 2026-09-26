"""Provider-neutral match bundle contracts and capability-gated analysis support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


MATCH_COLUMNS = {"match_id", "pitch_length_m", "pitch_width_m"}
TEAM_COLUMNS = {"match_id", "team_id", "team_code"}
ROSTER_COLUMNS = {"match_id", "player_id", "team_id", "position", "position_group", "is_goalkeeper"}
PLAYER_POSITION_COLUMNS = {"match_id", "frame", "period", "elapsed_seconds", "player_id", "team_id", "x", "y"}
BALL_POSITION_COLUMNS = {"match_id", "frame", "period", "elapsed_seconds", "ball_x", "ball_y"}
DIRECTION_COLUMNS = {"match_id", "period", "team_id", "attacking_x_sign"}
EVENT_COLUMNS = {"match_id", "event_id", "period", "team_id", "event_type", "is_shot"}
PHASE_COLUMNS = {"match_id", "period", "frame_start", "frame_end_exclusive", "possession_team_id"}
EVENT_SNAPSHOT_COLUMNS = {
    "match_id", "event_id", "snapshot_player_index", "teammate", "actor",
    "keeper", "location_x", "location_y", "visible_area",
}


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider has supplied and what was assumed by an adapter."""

    has_continuous_tracking: bool
    has_ball_tracking: bool
    has_verified_roles: bool
    has_attacking_direction: bool
    has_events: bool
    has_tactical_phases: bool
    has_lineups: bool = False
    has_360_snapshots: bool = False
    has_assumed_roles: bool = False


@dataclass
class CanonicalMatchBundle:
    """Schema-validated, provider-neutral data for exactly one match.

    ``match_info`` remains a small compatibility view for existing metric
    functions. New provider-aware code should consume the typed tables and
    ``capabilities`` instead. Dataframes contain only canonical column names.
    """

    provider: str
    match_info: dict[str, Any]
    matches: pd.DataFrame
    teams: pd.DataFrame
    roster: pd.DataFrame
    player_positions: pd.DataFrame
    ball_positions: pd.DataFrame
    attacking_directions: pd.DataFrame
    capabilities: ProviderCapabilities
    events: pd.DataFrame | None = None
    tactical_phases: pd.DataFrame | None = None
    event_snapshots: pd.DataFrame | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        """Temporary mapping compatibility for older notebook/demo call sites."""
        return getattr(self, key)


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Canonical {label} is missing columns: {sorted(missing)}")


def validate_canonical_bundle(bundle: CanonicalMatchBundle) -> None:
    """Validate table keys, metadata consistency, and declared capabilities."""
    _require_columns(bundle.matches, MATCH_COLUMNS, "matches")
    _require_columns(bundle.teams, TEAM_COLUMNS, "teams")
    _require_columns(bundle.roster, ROSTER_COLUMNS, "roster")
    _require_columns(bundle.player_positions, PLAYER_POSITION_COLUMNS, "player_positions")
    _require_columns(bundle.attacking_directions, DIRECTION_COLUMNS, "attacking_directions")
    if len(bundle.matches) != 1:
        raise ValueError("A CanonicalMatchBundle must contain exactly one matches row.")
    match_id = bundle.matches.match_id.iloc[0]
    if bundle.match_info.get("id") != match_id:
        raise ValueError("match_info.id must equal canonical matches.match_id.")
    for label, frame in (("teams", bundle.teams), ("roster", bundle.roster), ("player_positions", bundle.player_positions), ("attacking_directions", bundle.attacking_directions)):
        if not frame.match_id.eq(match_id).all():
            raise ValueError(f"Canonical {label} contains another match ID.")
    if bundle.player_positions.duplicated(["match_id", "frame", "period", "player_id"]).any():
        raise ValueError("Canonical player_positions contains duplicate player-frame rows.")
    team_ids = set(bundle.teams.team_id)
    if not set(bundle.player_positions.team_id.dropna()).issubset(team_ids):
        raise ValueError("Canonical player_positions references an unknown team.")
    if not set(bundle.roster.team_id.dropna()).issubset(team_ids):
        raise ValueError("Canonical roster references an unknown team.")
    if bundle.capabilities.has_ball_tracking:
        if bundle.ball_positions is None:
            raise ValueError("Capabilities declare ball tracking but ball_positions is absent.")
        _require_columns(bundle.ball_positions, BALL_POSITION_COLUMNS, "ball_positions")
        if not bundle.ball_positions.match_id.eq(match_id).all():
            raise ValueError("Canonical ball_positions contains another match ID.")
        if bundle.ball_positions.duplicated(["match_id", "frame", "period"]).any():
            raise ValueError("Canonical ball_positions contains duplicate frame rows.")
    if bundle.capabilities.has_events:
        if bundle.events is None:
            raise ValueError("Capabilities declare events but events is absent.")
        _require_columns(bundle.events, EVENT_COLUMNS, "events")
    if bundle.capabilities.has_tactical_phases:
        if bundle.tactical_phases is None:
            raise ValueError("Capabilities declare tactical phases but tactical_phases is absent.")
        _require_columns(bundle.tactical_phases, PHASE_COLUMNS, "tactical_phases")
        if (bundle.tactical_phases.frame_end_exclusive <= bundle.tactical_phases.frame_start).any():
            raise ValueError("Canonical tactical phases must have a positive frame interval.")
    if bundle.capabilities.has_lineups and bundle.roster.empty:
        raise ValueError("Capabilities declare lineups but the canonical roster is empty.")
    if bundle.capabilities.has_360_snapshots:
        if bundle.event_snapshots is None:
            raise ValueError("Capabilities declare 360 snapshots but event_snapshots is absent.")
        _require_columns(bundle.event_snapshots, EVENT_SNAPSHOT_COLUMNS, "event_snapshots")
        if not bundle.event_snapshots.match_id.eq(match_id).all():
            raise ValueError("Canonical event_snapshots contains another match ID.")
        if bundle.event_snapshots.event_id.isna().any():
            raise ValueError("Canonical 360 snapshots require an event ID.")
    if bundle.capabilities.has_360_snapshots and bundle.capabilities.has_continuous_tracking:
        # Both can coexist for a future provider, but snapshots must remain a
        # distinct table and never be used to imply temporal continuity.
        if bundle.event_snapshots is bundle.player_positions:
            raise ValueError("Event snapshots cannot alias continuous player tracking.")
    if bundle.capabilities.has_verified_roles and bundle.roster.position.isna().any():
        raise ValueError("Verified-role capability requires a position for every roster player.")
    if bundle.capabilities.has_assumed_roles and bundle.capabilities.has_verified_roles:
        raise ValueError("Roles cannot be both assumed and verified.")
    if bundle.capabilities.has_attacking_direction:
        if not bundle.attacking_directions.attacking_x_sign.isin([-1, 1]).all():
            raise ValueError("Canonical attacking_x_sign values must be -1 or +1.")


_REQUIREMENTS = {
    "pitch_visualization": ("has_continuous_tracking", "has_ball_tracking"),
    "team_shape": ("has_continuous_tracking", "has_verified_roles"),
    "defensive_line_structure": ("has_continuous_tracking", "has_verified_roles", "has_attacking_direction"),
    "local_defensive_context": ("has_continuous_tracking", "has_ball_tracking", "has_verified_roles", "has_attacking_direction"),
    "ball_goal_geometry": ("has_continuous_tracking", "has_ball_tracking", "has_verified_roles", "has_attacking_direction"),
    "temporal_shot_analysis": ("has_continuous_tracking", "has_ball_tracking", "has_events", "has_tactical_phases"),
    "phase_shape_analysis": ("has_continuous_tracking", "has_verified_roles", "has_tactical_phases"),
}


def supported_analyses(bundle: CanonicalMatchBundle, *, allow_assumed_roles: bool = False) -> pd.DataFrame:
    """Report supported analyses and explicit missing/assumed capability reasons."""
    validate_canonical_bundle(bundle)
    rows = []
    for analysis, requirements in _REQUIREMENTS.items():
        missing = [name for name in requirements if not getattr(bundle.capabilities, name)]
        assumed_role_block = "has_verified_roles" in requirements and bundle.capabilities.has_assumed_roles and not allow_assumed_roles
        supported = not missing or (allow_assumed_roles and missing == ["has_verified_roles"] and bundle.capabilities.has_assumed_roles)
        if assumed_role_block:
            supported = False
        reason = "" if supported else ("assumed roles require allow_assumed_roles=True" if assumed_role_block else f"missing: {', '.join(missing)}")
        rows.append({"analysis": analysis, "supported": supported, "reason": reason})
    return pd.DataFrame(rows)


def require_analysis_support(bundle: CanonicalMatchBundle, analysis: str, *, allow_assumed_roles: bool = False) -> None:
    """Fail before an analysis can silently run with unavailable capabilities."""
    support = supported_analyses(bundle, allow_assumed_roles=allow_assumed_roles)
    result = support.loc[support.analysis.eq(analysis)]
    if result.empty:
        raise ValueError(f"Unknown canonical analysis: {analysis!r}")
    if not bool(result.supported.iloc[0]):
        raise ValueError(f"{analysis} is unsupported for {bundle.provider}: {result.reason.iloc[0]}")
