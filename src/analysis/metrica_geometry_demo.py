"""Run the provider-independent geometry stack on a Metrica sample window."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data import load_metrica_sample_game, require_analysis_support
from src.metrics import (
    calculate_ball_goal_passing_lanes,
    calculate_defensive_line_structure,
    calculate_local_defensive_context,
    calculate_team_shape,
)
from src.visualization import plot_canonical_tracking_frame


def run_metrica_geometry_demo(
    data_dir: str | Path,
    *,
    start_frame: int = 1001,
    frame_count: int = 300,
    frame_stride: int = 5,
    figure_path: str | Path | None = None,
) -> dict[str, pd.DataFrame | dict]:
    """Adapt Sample Game 1 then run a bounded, actual geometry window.

    The adapter converts the entire selected Metrica match.  The metric stack
    is intentionally limited to a 60-second 5 Hz window by default, because
    local context is a per-team-frame calculation and this is a readiness
    demonstration rather than a batch product run.
    """
    adapted = load_metrica_sample_game(
        data_dir, frame_stride=frame_stride, allow_assumed_roles=True
    )
    for analysis in ("pitch_visualization", "team_shape", "defensive_line_structure", "local_defensive_context", "ball_goal_geometry"):
        require_analysis_support(adapted, analysis, allow_assumed_roles=True)
    players = adapted["player_positions"]
    balls = adapted["ball_positions"]
    stop_frame = start_frame + frame_count * frame_stride
    player_window = players.loc[players.frame.between(start_frame, stop_frame)].copy()
    periods = player_window[["frame", "period"]].drop_duplicates()
    ball_window = balls.merge(periods, on=["frame", "period"], how="inner")
    if player_window.empty or ball_window.empty:
        raise ValueError("Requested Metrica geometry window has no canonical tracking frames.")
    shape = calculate_team_shape(player_window)
    lines = calculate_defensive_line_structure(player_window, adapted["match_info"])
    local = calculate_local_defensive_context(player_window, ball_window, lines, adapted["match_info"])
    geometry = calculate_ball_goal_passing_lanes(player_window, ball_window, adapted["match_info"])
    selected_frame = int(player_window.frame.iloc[0])
    if figure_path is not None:
        axis = plot_canonical_tracking_frame(player_window, ball_window, adapted["match_info"], frame=selected_frame, source_label="Metrica Sample Game 1")
        output = Path(figure_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        axis.figure.savefig(output, dpi=150, bbox_inches="tight")

    shape_values = shape.reset_index()
    line_values = lines.reset_index()
    local_values = local
    geometry_values = geometry["frame_metrics"]
    invariants = {
        "source_sample_rate_hz": adapted["match_info"]["sample_rate_hz"],
        "canonical_player_rows": len(players),
        "canonical_ball_frames": len(balls),
        "canonical_observed_ball_frames": int(balls.ball_x.notna().sum()),
        "window_player_rows": len(player_window),
        "window_ball_frames": len(ball_window),
        "player_frame_duplicates": int(player_window.duplicated(["frame", "period", "player_id"]).sum()),
        "ball_frame_duplicates": int(ball_window.duplicated(["frame", "period"]).sum()),
        "team_shape_negative_spans": int(((shape_values.full_team_width < 0) | (shape_values.full_team_length < 0)).sum()),
        "line_complete_team_frames": int(line_values.line_structure_complete.sum()),
        "local_ball_available_team_frames": int(local_values.ball_x.notna().sum()),
        "geometry_negative_goal_distances": int((geometry_values.ball_distance_to_goal_centre < 0).sum()),
        "geometry_invalid_angles_when_ball_observed": int((
            ~geometry_values.loc[
                geometry_values.ball_angle_to_goal_degrees.notna(),
                "ball_angle_to_goal_degrees",
            ].between(0, 180)
        ).sum()),
    }
    return {
        "canonical": adapted,
        "team_shape": shape,
        "line_structure": lines,
        "local_context": local,
        "ball_goal_geometry": geometry_values,
        "passing_lanes": geometry["penalty_lane_context"],
        "invariants": invariants,
    }
