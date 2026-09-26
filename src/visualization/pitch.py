"""Matplotlib pitch visualisations for SkillCorner tracking data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.patches import Arc, Circle, Rectangle


def _draw_pitch(ax: Axes, pitch_length: float, pitch_width: float) -> None:
    """Draw a centred football pitch using metres as its coordinate system.

    SkillCorner uses x for the pitch's long axis and y for its short axis.
    """
    half_length = pitch_length / 2
    half_width = pitch_width / 2
    line_colour = "#f5f5f5"

    ax.set_facecolor("#3c8d40")
    ax.add_patch(
        Rectangle(
            (-half_length, -half_width), pitch_length, pitch_width,
            fill=False, edgecolor=line_colour, linewidth=1.5,
        )
    )
    ax.axvline(0, color=line_colour, linewidth=1.5)
    ax.add_patch(Circle((0, 0), radius=9.15, fill=False, edgecolor=line_colour, linewidth=1.2))
    ax.scatter(0, 0, color=line_colour, s=8, zorder=2)

    # Standard markings are expressed in the same x/y metre coordinate system.
    penalty_depth, penalty_width = 16.5, 40.32
    goal_area_depth, goal_area_width = 5.5, 18.32
    for side in (-1, 1):
        edge_x = side * half_length
        direction = -side
        ax.add_patch(
            Rectangle(
                (min(edge_x, edge_x + direction * penalty_depth), -penalty_width / 2),
                penalty_depth, penalty_width, fill=False, edgecolor=line_colour, linewidth=1.2,
            )
        )
        ax.add_patch(
            Rectangle(
                (min(edge_x, edge_x + direction * goal_area_depth), -goal_area_width / 2),
                goal_area_depth, goal_area_width, fill=False, edgecolor=line_colour, linewidth=1.2,
            )
        )
        penalty_spot_x = edge_x + direction * 11
        ax.scatter(penalty_spot_x, 0, color=line_colour, s=8, zorder=2)
        arc_center_x = penalty_spot_x
        angles = (310, 50) if side == -1 else (130, 230)
        ax.add_patch(
            Arc((arc_center_x, 0), 18.3, 18.3, theta1=angles[0], theta2=angles[1],
                color=line_colour, linewidth=1.2)
        )

    ax.set_xlim(-half_length, half_length)
    ax.set_ylim(-half_width, half_width)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def _resolve_frame(
    tracking_players: pd.DataFrame,
    *,
    frame: int | None,
    elapsed_seconds: float | None,
    period: int | None,
) -> int:
    """Resolve a frame from either a frame number or match-clock time."""
    if (frame is None) == (elapsed_seconds is None):
        raise ValueError("Provide exactly one of frame or elapsed_seconds.")

    if frame is not None:
        return frame

    matches = tracking_players.loc[
        tracking_players["elapsed_seconds"].eq(elapsed_seconds), "frame"
    ].drop_duplicates()
    if period is not None:
        matches = tracking_players.loc[
            tracking_players["elapsed_seconds"].eq(elapsed_seconds)
            & tracking_players["period"].eq(period),
            "frame",
        ].drop_duplicates()
    if matches.empty:
        raise ValueError("No tracking frame matches the requested elapsed time.")
    if len(matches) > 1:
        raise ValueError("Elapsed time occurs in multiple periods; provide period as well.")
    return int(matches.iloc[0])


def plot_tracking_frame(
    tracking_players: pd.DataFrame,
    tracking_raw: pd.DataFrame,
    match_info: Mapping[str, Any],
    *,
    frame: int | None = None,
    elapsed_seconds: float | None = None,
    period: int | None = None,
    ax: Axes | None = None,
) -> Axes:
    """Plot all tracked players and the ball at one SkillCorner frame.

    No coordinate transformation is applied. The plot uses the dataset's native,
    centred coordinates: x runs along the 105 m pitch length and y along the
    68 m pitch width. Directional normalisation belongs in a later analysis step.
    """
    required = {"frame", "team_acronym", "player_number", "x", "y"}
    missing = required - set(tracking_players.columns)
    if missing:
        raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")

    selected_frame = _resolve_frame(
        tracking_players, frame=frame, elapsed_seconds=elapsed_seconds, period=period
    )
    frame_players = tracking_players.loc[tracking_players["frame"].eq(selected_frame)]
    if frame_players.empty:
        raise ValueError(f"No player tracking data exists for frame {selected_frame}.")

    raw_rows = tracking_raw.loc[tracking_raw["frame"].eq(selected_frame)]
    if raw_rows.empty:
        raise ValueError(f"No raw tracking data exists for frame {selected_frame}.")
    ball_data = raw_rows.iloc[0].get("ball_data") or {}

    if ax is None:
        _, ax = plt.subplots(figsize=(14, 9))

    _draw_pitch(ax, match_info["pitch_length"], match_info["pitch_width"])
    colours = {"MEL": "#0b2e59", "AUC": "#ffffff"}
    edge_colours = {"MEL": "#ffffff", "AUC": "#111111"}

    for team_acronym, team_players in frame_players.groupby("team_acronym", dropna=False):
        label = str(team_acronym) if pd.notna(team_acronym) else "Unknown team"
        colour = colours.get(label, "#ffbf00")
        edge_colour = edge_colours.get(label, "#111111")
        ax.scatter(
            team_players["x"], team_players["y"], s=250, c=colour,
            edgecolors=edge_colour, linewidths=1.5, label=label, zorder=3,
        )
        for player in team_players.itertuples(index=False):
            number = "" if pd.isna(player.player_number) else str(int(player.player_number))
            ax.text(
                player.x, player.y, number, ha="center", va="center", fontsize=8,
                fontweight="bold", color="#ffffff" if label == "MEL" else "#111111", zorder=4,
            )

    if ball_data.get("x") is not None and ball_data.get("y") is not None:
        ax.scatter(
            ball_data["x"], ball_data["y"], s=90, c="#f6c945", marker="o",
            edgecolors="#111111", linewidths=1.2, label="Ball", zorder=5,
        )

    timestamp = frame_players["timestamp"].iloc[0]
    frame_period = frame_players["period"].iloc[0]
    ax.set_title(f"SkillCorner tracking — frame {selected_frame} | {timestamp} | period {frame_period}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=3, frameon=False)
    return ax


def plot_canonical_tracking_frame(
    tracking_players: pd.DataFrame,
    ball_tracking: pd.DataFrame,
    match_info: Mapping[str, Any],
    *,
    frame: int | None = None,
    elapsed_seconds: float | None = None,
    period: int | None = None,
    ax: Axes | None = None,
    source_label: str = "Tracking",
) -> Axes:
    """Plot one frame from the provider-agnostic player/ball tables.

    Coordinates must already be centred pitch metres with x as the long axis;
    unlike :func:`plot_tracking_frame`, this does not rely on SkillCorner's
    nested raw JSONL representation.
    """
    required_players = {"frame", "team_acronym", "x", "y", "period", "timestamp", "elapsed_seconds"}
    required_ball = {"frame", "period", "ball_x", "ball_y"}
    if missing := required_players - set(tracking_players):
        raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")
    if missing := required_ball - set(ball_tracking):
        raise ValueError(f"ball_tracking is missing required columns: {sorted(missing)}")
    selected_frame = _resolve_frame(tracking_players, frame=frame, elapsed_seconds=elapsed_seconds, period=period)
    frame_players = tracking_players.loc[tracking_players.frame.eq(selected_frame)]
    if frame_players.empty:
        raise ValueError(f"No player tracking data exists for frame {selected_frame}.")
    frame_period = int(frame_players.period.iloc[0])
    ball = ball_tracking.loc[ball_tracking.frame.eq(selected_frame) & ball_tracking.period.eq(frame_period)]
    if ax is None:
        _, ax = plt.subplots(figsize=(14, 9))
    _draw_pitch(ax, match_info["pitch_length"], match_info["pitch_width"])
    colours = ["#0b2e59", "#ffffff", "#ffbf00", "#bd4b4b"]
    for index, (team, members) in enumerate(frame_players.groupby("team_acronym", dropna=False)):
        colour = colours[index % len(colours)]
        text_colour = "#111111" if colour == "#ffffff" else "#ffffff"
        label = str(team) if pd.notna(team) else "Unknown team"
        ax.scatter(members.x, members.y, s=250, c=colour, edgecolors="#111111", linewidths=1.2, label=label, zorder=3)
        if "player_number" in members:
            labels = members.player_number
        else:
            labels = members.player_id.astype(str).str.replace("Player", "", regex=False)
        for row, label_text in zip(members.itertuples(index=False), labels):
            ax.text(row.x, row.y, "" if pd.isna(label_text) else str(label_text), ha="center", va="center", fontsize=8, fontweight="bold", color=text_colour, zorder=4)
    if not ball.empty and pd.notna(ball.ball_x.iloc[0]) and pd.notna(ball.ball_y.iloc[0]):
        ax.scatter(ball.ball_x.iloc[0], ball.ball_y.iloc[0], s=90, c="#f6c945", edgecolors="#111111", linewidths=1.2, label="Ball", zorder=5)
    ax.set_title(f"{source_label} — frame {selected_frame} | {frame_players.timestamp.iloc[0]} | period {frame_period}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=3, frameon=False)
    return ax
