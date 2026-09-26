"""Paired 5-second pre-shot trajectory reconstruction."""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from .shot_sequence_temporal import audit_shot_sequence_timing
from .multimatch_pipeline import _build_team_shape_from_tracking_stream
from src.data import expand_phase_context, join_phase_context_to_team_shape

METRICS = ["ball_normalized_x","total_outfield_length","defence_to_midfield_gap","midfield_to_attack_gap","defence_tactical_median_x","midfield_tactical_median_x","attack_tactical_median_x","deepest_defender_x","defence_line_to_ball_distance","midfield_line_to_ball_distance","attack_line_to_ball_distance"]

def build_pre_shot_trajectory_analysis(matches_root: str | Path) -> dict[str,pd.DataFrame]:
    root=Path(matches_root); audit=audit_shot_sequence_timing(root)
    shots=audit["shots"]; controls=audit["control_windows"]; wins=audit["pre_shot_windows"]
    full= wins.loc[(wins.window_seconds==5)&(wins.player_tracking_frames==50),["match_id","event_id"]]
    pairs=shots.merge(full,on=["match_id","event_id"]).merge(controls,left_on=["match_id","event_id"],right_on=["match_id","shot_event_id"])
    records=[]
    for match_id, group in pairs.groupby("match_id"):
        d=root/str(match_id); info=json.loads((d/f"{match_id}_match.json").read_text(encoding="utf-8")); phases=pd.read_csv(d/f"{match_id}_phases_of_play.csv")
        shape=_build_team_shape_from_tracking_stream(d/f"{match_id}_tracking_extrapolated.jsonl",info)
        joined=join_phase_context_to_team_shape(shape,expand_phase_context(phases,info),info).reset_index()
        base=joined.loc[joined.possession_status.eq("out_of_possession")].groupby(["team_id","tactical_phase"])[METRICS].median().reset_index()
        for pair in group.itertuples(index=False):
            for outcome,end in (("shot",pair.shot_frame),("control",pair.control_frame)):
                rows=joined.loc[(joined.team_id==pair.defending_team_id)&(joined.frame.between(end-50,end))].copy()
                rows["relative_frame"]=rows.frame-end
                rows=rows.merge(base,on=["team_id","tactical_phase"],how="left",suffixes=("","_baseline"))
                for metric in METRICS: rows[metric]=rows[metric]-rows[f"{metric}_baseline"]
                for row in rows[["relative_frame"]+METRICS].itertuples(index=False):
                    for metric,value in zip(["relative_frame"]+METRICS,row):
                        if metric!="relative_frame": records.append({"match_id":match_id,"event_id":pair.event_id,"defending_phase":pair.defending_phase,"outcome":outcome,"relative_frame":row[0],"metric":metric,"value":value})
    values=pd.DataFrame(records); valid=[]
    for metric,g in values.groupby("metric"):
        pivot=g.pivot_table(index=["match_id","event_id","outcome"],columns="relative_frame",values="value")
        ok=pivot.dropna().reset_index()[["match_id","event_id","outcome"]]; valid.append(ok.assign(metric=metric))
    valid=pd.concat(valid,ignore_index=True)
    paired=valid.groupby(["match_id","event_id","metric"])["outcome"].nunique().eq(2).rename("paired").reset_index()
    paired=paired.loc[paired.paired].drop(columns="paired")
    filtered=values.merge(paired,on=["match_id","event_id","metric"])
    segments=pd.concat([filtered.assign(segment="all"),filtered.loc[filtered.defending_phase.ne("defending_set_play")].assign(segment="open_play"),filtered.loc[filtered.defending_phase.eq("defending_set_play")].assign(segment="defending_set_play")])
    trajectories=segments.groupby(["segment","metric","outcome","relative_frame"]).agg(n=("value","size"),median=("value","median")).reset_index()
    wide=segments.pivot(index=["segment","match_id","event_id","metric","relative_frame"],columns="outcome",values="value").dropna().reset_index(); wide["paired_difference"]=wide.shot-wide.control
    diffs=wide.groupby(["segment","metric","relative_frame"]).agg(pair_count=("paired_difference","size"),paired_difference_median=("paired_difference","median")).reset_index()
    feats=[]
    for (segment,m,e,metric,outcome),g in segments.groupby(["segment","match_id","event_id","metric","outcome"]):
        s=g.set_index("relative_frame").value
        feats.append({"segment":segment,"defending_phase":g.defending_phase.iloc[0],"match_id":m,"event_id":e,"metric":metric,"outcome":outcome,"value_minus_5":s[-50],"value_minus_2":s[-20],"value_at_0":s[0],"change_minus_5_to_0":s[0]-s[-50],"change_minus_2_to_0":s[0]-s[-20],"maximum":s.max(),"minimum":s.min()})
    features=pd.DataFrame(feats); feature_summary=features.melt(id_vars=["segment","defending_phase","match_id","event_id","metric","outcome"],var_name="feature",value_name="value").groupby(["segment","metric","outcome","feature"]).agg(n=("value","size"),median=("value","median"),q25=("value",lambda x:x.quantile(.25)),q75=("value",lambda x:x.quantile(.75))).reset_index()
    fw=features.pivot(index=["segment","match_id","event_id","metric"],columns="outcome",values=["value_minus_5","value_minus_2","value_at_0","change_minus_5_to_0","change_minus_2_to_0","maximum","minimum"]).dropna(); fd=[]
    for (segment,m,e,metric),r in fw.iterrows():
        for feature in [x[0] for x in fw.columns[::2]]: fd.append({"segment":segment,"match_id":m,"event_id":e,"metric":metric,"feature":feature,"paired_difference":r[(feature,"shot")]-r[(feature,"control")]})
    feature_differences=pd.DataFrame(fd).groupby(["segment","metric","feature"]).agg(pair_count=("paired_difference","size"),median_paired_difference=("paired_difference","median"),q25=("paired_difference",lambda x:x.quantile(.25)),q75=("paired_difference",lambda x:x.quantile(.75))).reset_index()
    coverage=segments.groupby(["segment","metric","outcome"]).size().unstack(fill_value=0).reset_index(); coverage["valid_pairs"]=coverage[["shot","control"]].min(axis=1)
    ball=features.loc[(features.segment=="all")&(features.metric=="ball_normalized_x")].pivot(index=["match_id","event_id"],columns="outcome",values=["value_minus_5","change_minus_5_to_0"])
    sensitive=ball.loc[(ball[("value_minus_5","shot")]-ball[("value_minus_5","control")]).abs().le(5)&(ball[("change_minus_5_to_0","shot")]-ball[("change_minus_5_to_0","control")]).abs().le(5)].reset_index()[["match_id","event_id"]]
    response=[]
    positions={"defence_tactical_median_x":"defence","midfield_tactical_median_x":"midfield","attack_tactical_median_x":"attack","deepest_defender_x":"deepest_defender"}
    for segment in ["all","open_play","defending_set_play"]:
      f=features.loc[features.segment.eq(segment)]
      for (m,e,outcome),g in f.groupby(["match_id","event_id","outcome"]):
       b=g.loc[g.metric.eq("ball_normalized_x")].iloc[0]
       for metric,label in positions.items():
        x=g.loc[g.metric.eq(metric)].iloc[0]
        for change in ["change_minus_5_to_0","change_minus_2_to_0"]: response.append({"segment":segment,"match_id":m,"event_id":e,"outcome":outcome,"metric":f"{label}_response_to_ball_{change}","value":x[change]-b[change]})
    response=pd.DataFrame(response); rw=response.pivot(index=["segment","match_id","event_id","metric"],columns="outcome",values="value").dropna().reset_index(); rw["paired_difference"]=rw.shot-rw.control
    response_differences=rw.groupby(["segment","metric"]).agg(pair_count=("paired_difference","size"),median_paired_difference=("paired_difference","median")).reset_index()
    return {"coverage":coverage,"window_features":features,"trajectories":trajectories,"trajectory_differences":diffs,"feature_summary":feature_summary,"feature_paired_differences":feature_differences,"response_to_ball_differences":response_differences,"sensitivity_pairs":sensitive}
