"""Frame-level team shape metrics for native SkillCorner coordinates."""

from __future__ import annotations

import pandas as pd


TEAM_SHAPE_INDEX = [
    "frame",
    "timestamp",
    "elapsed_seconds",
    "period",
    "team_id",
    "team_acronym",
]

TEAM_SHAPE_COLUMNS = [
    "full_team_width",
    "full_team_length",
    "full_team_centroid_x",
    "full_team_centroid_y",
    "outfield_width",
    "outfield_length",
    "outfield_centroid_x",
    "outfield_centroid_y",
    "player_count",
]


def _span(values: pd.Series) -> float:
    """Return the spatial extent of a coordinate series."""
    return values.max() - values.min()


def calculate_team_shape(tracking_players: pd.DataFrame) -> pd.DataFrame:
    """Calculate frame-level team shape metrics in native pitch coordinates.

    SkillCorner defines x along the pitch length and y along the pitch width.
    Accordingly, team length is the x span and team width is the y span. This
    function deliberately does not transform attacking direction.

    Goalkeepers are identified from the ``position`` metadata field, so no shirt
    number or player-ID assumption is made. The returned dataframe is indexed by
    frame, time, period, and team identity.
    """
    required = set(TEAM_SHAPE_INDEX + ["player_id", "position", "x", "y"])
    missing = required - set(tracking_players.columns)
    if missing:
        raise ValueError(
            f"tracking_players is missing required columns: {sorted(missing)}"
        )

    duplicate_keys = ["frame", "team_id", "player_id"]
    if tracking_players.duplicated(duplicate_keys).any():
        raise ValueError(
            "tracking_players must contain at most one row per frame, team, and player."
        )

    # Aggregate directly from the flattened dataframe. Avoiding a dataframe-wide
    # copy matters when processing an 800k+ row match one at a time.
    is_goalkeeper = (
        tracking_players["position"].fillna("").str.strip().str.casefold().eq("goalkeeper")
    )

    full_team = (
        tracking_players.groupby(TEAM_SHAPE_INDEX, dropna=False)
        .agg(
            full_team_width=("y", _span),
            full_team_length=("x", _span),
            full_team_centroid_x=("x", "mean"),
            full_team_centroid_y=("y", "mean"),
            player_count=("player_id", "nunique"),
        )
    )

    outfield = (
        tracking_players.loc[~is_goalkeeper]
        .groupby(TEAM_SHAPE_INDEX, dropna=False)
        .agg(
            outfield_width=("y", _span),
            outfield_length=("x", _span),
            outfield_centroid_x=("x", "mean"),
            outfield_centroid_y=("y", "mean"),
        )
    )

    return full_team.join(outfield, how="left")[TEAM_SHAPE_COLUMNS].sort_index()
