"""Ball-to-goal and direct passing-lane geometry."""
from __future__ import annotations
from collections.abc import Mapping
import numpy as np
import pandas as pd
from .defensive_line_structure import _home_attacking_signs

GEOMETRY_METRICS = [
    "ball_distance_to_goal_centre", "ball_angle_to_goal_degrees", "defenders_in_ball_goal_corridor",
    "minimum_defender_clearance_to_ball_goal_segment", "open_penalty_corridor_passing_options_over_1m",
    "open_penalty_corridor_passing_options_over_2m", "open_penalty_corridor_passing_options_over_3m",
    "carrier_proxy_central_route_unobstructed",
]

def _segment_clearances(points: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    vector = end - start; squared = float(vector @ vector)
    if squared == 0: return np.linalg.norm(points - start, axis=1)
    fraction = np.clip(((points - start) @ vector) / squared, 0, 1)
    return np.linalg.norm(points - (start + fraction[:, None] * vector), axis=1)

def calculate_ball_goal_passing_lanes(
    tracking_players: pd.DataFrame, ball_tracking: pd.DataFrame, match_info: Mapping,
    *, goal_corridor_half_width_metres: float = 3.0,
    lane_clearance_thresholds: tuple[float, ...] = (1.0, 2.0, 3.0),
    central_route_clearance_metres: float = 2.0,
) -> dict[str, pd.DataFrame]:
    """Calculate attacking-direction goal route and passing-lane geometry.

    Goal geometry uses the attacking team's coordinates: the goal centre is
    ``(+pitch_length/2, 0)``. A defender occupies the ball-goal corridor when
    its perpendicular clearance to the finite ball-to-goal segment is at most
    ``goal_corridor_half_width_metres``. A passing lane is open when every
    defender is farther than the stated threshold from its finite ball-to-
    attacker segment. Penalty corridor: attacking x >= half_length-16.5 and
    |y| <= 20.16. The nearest attacker to the ball is only a carrier proxy.
    """
    if goal_corridor_half_width_metres <= 0 or central_route_clearance_metres <= 0 or any(x <= 0 for x in lane_clearance_thresholds):
        raise ValueError("All geometry thresholds must be positive.")
    required = {"frame","timestamp","elapsed_seconds","period","team_id","team_acronym","player_id","position","x","y"}
    if missing := required - set(tracking_players.columns): raise ValueError(f"tracking_players is missing required columns: {sorted(missing)}")
    if missing := {"frame","period","ball_x","ball_y"} - set(ball_tracking.columns): raise ValueError(f"ball_tracking is missing required columns: {sorted(missing)}")
    home_id = match_info["home_team"]["id"]; team_ids={home_id,match_info["away_team"]["id"]}; signs=_home_attacking_signs(match_info)
    half_length=float(match_info.get("pitch_length",105))/2; goal=np.array([half_length,0.]); penalty_x=half_length-16.5
    keys=["frame","timestamp","elapsed_seconds","period","team_id","team_acronym"]
    frames=tracking_players[keys].drop_duplicates(); available=tracking_players.loc[tracking_players.x.notna()&tracking_players.y.notna()&tracking_players.position.ne("Goalkeeper")]
    groups={key:g for key,g in available.groupby(["frame","period","team_id"],sort=False)}
    balls={(r.frame,r.period):r for r in ball_tracking.drop_duplicates(["frame","period"])[["frame","period","ball_x","ball_y"]].itertuples(index=False)}
    rows=[]; lane_rows=[]
    for item in frames.itertuples(index=False):
        frame,timestamp,elapsed,period,defending_id,acronym=item; base={"frame":frame,"timestamp":timestamp,"elapsed_seconds":elapsed,"period":period,"team_id":defending_id,"team_acronym":acronym}
        ball=balls.get((frame,period)); attacking_id=next(t for t in team_ids if t!=defending_id); defenders=groups.get((frame,period,defending_id)); attackers=groups.get((frame,period,attacking_id))
        if ball is None or pd.isna(ball.ball_x) or pd.isna(ball.ball_y) or defenders is None or attackers is None or defenders.empty or attackers.empty: rows.append(base); continue
        attack_sign=-signs[int(period)]*(1 if defending_id==home_id else -1)
        ball_point=np.array([ball.ball_x*attack_sign,ball.ball_y]); defender_points=np.column_stack((defenders.x.to_numpy()*attack_sign,defenders.y.to_numpy()))
        attacker_points=np.column_stack((attackers.x.to_numpy()*attack_sign,attackers.y.to_numpy()))
        goal_clearance=_segment_clearances(defender_points,ball_point,goal); ball_goal_distance=float(np.linalg.norm(goal-ball_point)); angle=float(np.degrees(np.arctan2(abs(ball_point[1]),goal[0]-ball_point[0])))
        carrier=int(np.linalg.norm(attacker_points-ball_point,axis=1).argmin()); penalty=(attacker_points[:,0]>=penalty_x)&(np.abs(attacker_points[:,1])<=20.16)
        lane_clearances=[]
        for index in np.flatnonzero(penalty):
            clearances=_segment_clearances(defender_points,ball_point,attacker_points[index]); minimum=float(clearances.min()); lane_clearances.append((index,minimum))
            lane_rows.append({**base,"attacking_team_id":attacking_id,"attacker_player_id":attackers.iloc[index].player_id,"is_ball_carrier_proxy":index==carrier,"attacker_attacking_x":attacker_points[index,0],"attacker_y":attacker_points[index,1],"minimum_defender_lane_clearance":minimum})
        base.update({"ball_distance_to_goal_centre":ball_goal_distance,"ball_angle_to_goal_degrees":angle,"defenders_in_ball_goal_corridor":int((goal_clearance<=goal_corridor_half_width_metres).sum()),"minimum_defender_clearance_to_ball_goal_segment":float(goal_clearance.min()),"carrier_proxy_central_route_unobstructed":bool(goal_clearance.min()>central_route_clearance_metres)})
        for threshold in lane_clearance_thresholds: base[f"open_penalty_corridor_passing_options_over_{int(threshold)}m"]=int(sum(value>threshold for _,value in lane_clearances))
        rows.append(base)
    metrics=pd.DataFrame(rows)
    for col in GEOMETRY_METRICS:
        if col not in metrics: metrics[col]=np.nan
    return {"frame_metrics":metrics,"penalty_lane_context":pd.DataFrame(lane_rows)}
