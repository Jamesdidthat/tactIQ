"""Temporal reconstruction and audit of dynamic-event shot sequences."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


SHOT_EVENT_COLUMNS = [
    "match_id", "event_id", "frame_start", "frame_end", "time_start", "time_end",
    "period", "team_id", "team_shortname", "team_in_possession_phase_type",
    "team_out_of_possession_phase_type", "lead_to_goal",
]


def audit_shot_sequence_timing(matches_root: str | Path) -> dict[str, pd.DataFrame]:
    """Audit shot timing and 5/10-second pre-shot frame/phase coverage.

    A shot is a Dynamic Events ``player_possession`` ending with ``end_type``
    equal to ``shot``. Its event endpoint (``frame_end``, ``time_end``) is the
    shot instant. Matches with proven phase/tracking period disagreement are
    skipped, preserving the existing strict validation convention.
    """
    root = Path(matches_root)
    shot_rows: list[dict] = []
    phase_rows: list[dict] = []
    control_rows: list[dict] = []
    logs: list[dict] = []
    for match_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda p: int(p.name)):
        match_id = int(match_dir.name)
        try:
            dynamic = pd.read_csv(match_dir / f"{match_id}_dynamic_events.csv", low_memory=False)
            phases = pd.read_csv(match_dir / f"{match_id}_phases_of_play.csv")
            with (match_dir / f"{match_id}_match.json").open(encoding="utf-8") as file:
                match_info = json.load(file)
            tracking = []
            with (match_dir / f"{match_id}_tracking_extrapolated.jsonl").open(encoding="utf-8") as file:
                for line in file:
                    record = json.loads(line)
                    if record.get("period") is not None:
                        tracking.append({
                            "frame": record["frame"], "period": record["period"],
                            "timestamp": record["timestamp"], "has_player_data": bool(record.get("player_data")),
                            "ball_x": (record.get("ball_data") or {}).get("x"),
                        })
            tracked = pd.DataFrame(tracking)
            # Validate only represented phase frames, using the same interval rule.
            phase_frames = pd.concat([
                pd.DataFrame({
                    "frame": range(int(row.frame_start), int(row.frame_end)), "period": row.period,
                    "possession_team_id": row.team_in_possession_id,
                    "defending_phase": row.team_out_of_possession_phase_type,
                })
                for row in phases[[
                    "frame_start", "frame_end", "period", "team_in_possession_id",
                    "team_out_of_possession_phase_type",
                ]].itertuples(index=False)
            ], ignore_index=True)
            agreement = phase_frames.merge(tracked[["frame", "period"]], on="frame", how="inner", suffixes=("_phase", "_tracking"))
            if not agreement["period_phase"].eq(agreement["period_tracking"]).all():
                raise ValueError("Phase and tracking period values disagree for the same frame.")

            shots = dynamic.loc[
                dynamic["event_type"].eq("player_possession") & dynamic["end_type"].eq("shot"),
                SHOT_EVENT_COLUMNS,
            ].copy()
            shot_frames = shots["frame_end"].astype(int).tolist()
            tracking_by_frame = tracked.set_index("frame")
            for shot in shots.itertuples(index=False):
                shot_data = shot._asdict()
                shot_frame = int(shot_data["frame_end"])
                tracking_at_shot = tracking_by_frame.loc[shot_frame] if shot_frame in tracking_by_frame.index else None
                period_matches = tracking_at_shot is not None and int(tracking_at_shot["period"]) == int(shot_data["period"])
                timestamp_delta = None
                if tracking_at_shot is not None:
                    event_seconds = _time_to_seconds(shot_data["time_end"])
                    tracking_seconds = _time_to_seconds(tracking_at_shot["timestamp"])
                    timestamp_delta = tracking_seconds - event_seconds
                before = phases.loc[
                    phases["frame_start"].le(shot_frame) & phases["frame_end"].gt(shot_frame)
                ]
                prior = phases.loc[
                    phases["frame_start"].le(shot_frame - 1)
                    & phases["frame_end"].gt(shot_frame - 1)
                ]
                defending_team_id = next(
                    team_id for team_id in (match_info["home_team"]["id"], match_info["away_team"]["id"])
                    if team_id != shot_data["team_id"]
                )
                phase_label = before["team_out_of_possession_phase_type"].iloc[0] if len(before) else None
                home_sign = {"left_to_right": 1, "right_to_left": -1}[match_info["home_team_side"][int(shot_data["period"]) - 1]]
                defending_sign = home_sign if defending_team_id == match_info["home_team"]["id"] else -home_sign
                candidates = tracked.merge(phase_frames, on=["frame", "period"], how="inner")
                candidates = candidates.loc[
                    candidates["period"].eq(shot_data["period"])
                    & candidates["possession_team_id"].eq(shot_data["team_id"])
                    & candidates["defending_phase"].eq(phase_label)
                    & candidates["ball_x"].notna()
                ].copy()
                candidates["ball_zone"] = (candidates["ball_x"] * defending_sign).map(_ball_zone)
                shot_ball_zone = None
                if tracking_at_shot is not None and pd.notna(tracking_at_shot["ball_x"]):
                    shot_ball_zone = _ball_zone(tracking_at_shot["ball_x"] * defending_sign)
                candidates = candidates.loc[
                    candidates["ball_zone"].eq(shot_ball_zone)
                    & ~candidates["frame"].apply(lambda frame: any(abs(frame - other) <= 100 for other in shot_frames))
                ]
                if not candidates.empty:
                    control_frame = int(candidates.iloc[(candidates["frame"] - shot_frame).abs().argmin()]["frame"])
                    control_rows.append({
                        "match_id": match_id, "shot_event_id": shot_data["event_id"],
                        "control_frame": control_frame, "period": shot_data["period"],
                        "defending_team_id": defending_team_id, "defending_phase": phase_label,
                        "ball_depth_zone": shot_ball_zone,
                        "distance_from_shot_seconds": abs(control_frame - shot_frame) / 10,
                    })
                for seconds in (5, 10):
                    start = shot_frame - seconds * 10
                    window = tracked.loc[
                        tracked["frame"].ge(start) & tracked["frame"].lt(shot_frame)
                        & tracked["period"].eq(shot_data["period"])
                    ]
                    phase_window = phase_frames.loc[
                        phase_frames["frame"].ge(start) & phase_frames["frame"].lt(shot_frame)
                        & phase_frames["period"].eq(shot_data["period"])
                    ]
                    phase_rows.append({
                        "match_id": match_id, "event_id": shot_data["event_id"],
                        "window_seconds": seconds, "expected_frames": seconds * 10,
                        "tracking_frames": len(window), "player_tracking_frames": int(window["has_player_data"].sum()),
                        "phase_context_frames": len(phase_window),
                    })
                shot_rows.append({
                    **shot_data, "shot_frame": shot_frame,
                    "tracking_frame_available": tracking_at_shot is not None,
                    "tracking_period_matches_event": period_matches,
                    "tracking_minus_event_seconds": timestamp_delta,
                    "phase_at_shot": before["team_out_of_possession_phase_type"].iloc[0] if len(before) else None,
                    "phase_immediately_before": prior["team_out_of_possession_phase_type"].iloc[0] if len(prior) else None,
                })
            logs.append({"match_id": match_id, "status": "processed", "message": ""})
        except Exception as error:
            logs.append({"match_id": match_id, "status": "skipped", "message": str(error)})
    return {
        "shots": pd.DataFrame(shot_rows),
        "pre_shot_windows": pd.DataFrame(phase_rows),
        "control_windows": pd.DataFrame(control_rows),
        "processing_log": pd.DataFrame(logs),
    }


def _time_to_seconds(value: str) -> float:
    parts = str(value).split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"Unsupported timestamp format: {value!r}")


def _ball_zone(normalized_x: float) -> str | None:
    if pd.isna(normalized_x) or normalized_x >= 0:
        return None
    if normalized_x < -35:
        return "deep_defending_half"
    if normalized_x < -17.5:
        return "middle_defending_half"
    return "front_defending_half"
