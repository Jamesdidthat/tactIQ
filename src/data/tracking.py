"""Transform SkillCorner tracking data into analysis-ready tables."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


PLAYER_TRACKING_COLUMNS = [
    "frame",
    "timestamp",
    "elapsed_seconds",
    "period",
    "player_id",
    "team_id",
    "team_acronym",
    "player_name",
    "player_number",
    "position",
    "position_group",
    "x",
    "y",
    "is_detected",
]


def _timestamp_to_seconds(timestamp: str | None) -> float | None:
    """Convert a SkillCorner ``HH:MM:SS.ss`` timestamp to elapsed seconds."""
    if timestamp is None or pd.isna(timestamp):
        return None

    hours, minutes, seconds = str(timestamp).split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _player_metadata(match_info: Mapping[str, Any]) -> pd.DataFrame:
    """Create a player lookup keyed by SkillCorner's tracking player identifier."""
    player_rows = []
    for player in match_info["players"]:
        role = player.get("player_role") or {}
        player_rows.append(
            {
                "player_id": player["id"],
                "team_id": player.get("team_id"),
                "player_name": " ".join(
                    part.strip()
                    for part in (player.get("first_name", ""), player.get("last_name", ""))
                    if part and part.strip()
                ),
                "player_number": player.get("number"),
                "position": role.get("name"),
                "position_group": role.get("position_group"),
            }
        )

    metadata = pd.DataFrame(player_rows)
    if metadata["player_id"].duplicated().any():
        raise ValueError("match_info contains duplicate player IDs.")

    teams = (match_info["home_team"], match_info["away_team"])
    acronym_by_team_id = {team["id"]: team["acronym"] for team in teams}
    metadata["team_acronym"] = metadata["team_id"].map(acronym_by_team_id)
    return metadata


def flatten_player_tracking(
    tracking_raw: pd.DataFrame, match_info: Mapping[str, Any]
) -> pd.DataFrame:
    """Flatten nested SkillCorner player tracking records.

    The raw tracking dataframe is never modified. A row is returned only when a
    player appears in a frame; metadata players who never appear (for example,
    unused substitutes) are consequently absent from the result. Their absence
    can be identified by comparing ``match_info['players']`` with ``player_id``.

    Player identities are joined using the verified relationship:
    ``tracking_raw.player_data[].player_id == match_info['players'][].id``.
    """
    required_columns = {"frame", "timestamp", "period", "player_data"}
    missing = required_columns - set(tracking_raw.columns)
    if missing:
        raise ValueError(f"tracking_raw is missing required columns: {sorted(missing)}")

    metadata = _player_metadata(match_info)
    records: list[dict[str, Any]] = []

    frame_columns = ["frame", "timestamp", "period", "player_data"]
    for frame, timestamp, period, player_data in tracking_raw[frame_columns].itertuples(
        index=False, name=None
    ):
        if not player_data:
            continue

        elapsed_seconds = _timestamp_to_seconds(timestamp)
        for player in player_data:
            records.append(
                {
                    "frame": frame,
                    "timestamp": timestamp,
                    "elapsed_seconds": elapsed_seconds,
                    "period": period,
                    "player_id": player.get("player_id"),
                    "x": player.get("x"),
                    "y": player.get("y"),
                    "is_detected": player.get("is_detected"),
                }
            )

    tracking_players = pd.DataFrame.from_records(records)
    if tracking_players.empty:
        return pd.DataFrame(columns=PLAYER_TRACKING_COLUMNS)

    tracking_players = tracking_players.merge(
        metadata,
        on="player_id",
        how="left",
        validate="many_to_one",
    )

    tracking_players["period"] = tracking_players["period"].astype("Int64")
    tracking_players["team_id"] = tracking_players["team_id"].astype("Int64")
    tracking_players["player_number"] = tracking_players["player_number"].astype("Int64")
    tracking_players["is_detected"] = tracking_players["is_detected"].astype("boolean")

    return tracking_players[PLAYER_TRACKING_COLUMNS]
