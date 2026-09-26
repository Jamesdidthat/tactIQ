"""Direct 1:1 matched-pair conditional logistic models."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.special import expit

CONTEXT={"ball_x_minus_5":("ball_normalized_x","value_minus_5"),"ball_progression_5s":("ball_normalized_x","change_minus_5_to_0")}
# The first three sources are converted below to response-to-ball movement:
# line displacement minus ball displacement in the same five-second window.
SOURCES={**CONTEXT,
    "deepest_defender_displacement":("deepest_defender_x","change_minus_5_to_0"),
    "attack_line_displacement":("attack_tactical_median_x","change_minus_5_to_0"),
    "midfield_displacement":("midfield_tactical_median_x","change_minus_5_to_0"),
    "total_length_change":("total_outfield_length","change_minus_5_to_0"),
    "defence_midfield_gap_change":("defence_to_midfield_gap","change_minus_5_to_0"),
    "midfield_attack_gap_change":("midfield_to_attack_gap","change_minus_5_to_0")}
TRAJECTORY=("deepest_defender_response","attack_line_response","midfield_response",
            "total_length_change","defence_midfield_gap_change","midfield_attack_gap_change")

def _fit(x):
    beta=np.zeros(x.shape[1]); converged=False
    for iteration in range(100):
        p=expit(x@beta); info=x.T@((p*(1-p))[:,None]*x); grad=x.T@(1-p)
        try: step=np.linalg.solve(info,grad)
        except np.linalg.LinAlgError: break
        scale=1.; loss=np.logaddexp(0,-x@beta).sum()
        while np.logaddexp(0,-x@(beta+scale*step)).sum()>loss and scale>1e-8: scale/=2
        beta+=scale*step
        if np.max(np.abs(scale*step))<1e-8: converged=True; break
    p=expit(x@beta); info=x.T@((p*(1-p))[:,None]*x); cond=float(np.linalg.cond(info))
    try: se=np.sqrt(np.diag(np.linalg.inv(info))) if cond<1e10 else np.full(len(beta),np.nan)
    except np.linalg.LinAlgError: se=np.full(len(beta),np.nan)
    return beta,se,converged,iteration+1,cond,float(-np.logaddexp(0,-x@beta).sum()),float((x@beta>0).mean())

def _sign_flip_pvalue(values: pd.Series, draws: int = 20_000, seed: int = 42) -> float:
    """Two-sided Monte-Carlo sign-flip test for a paired mean difference."""
    values = values.to_numpy(dtype=float)
    observed = abs(values.mean())
    rng = np.random.default_rng(seed)
    null = np.abs((rng.choice((-1.0, 1.0), size=(draws, len(values))) * values).mean(axis=1))
    return float((1 + (null >= observed).sum()) / (draws + 1))

def exploratory_conditional_outcomes(features: pd.DataFrame) -> dict[str,pd.DataFrame]:
    f=features.loc[features.segment.eq("open_play")].copy(); rows=[]
    for name,(metric,field) in SOURCES.items():
      t=f.loc[f.metric.eq(metric),["match_id","event_id","outcome",field]].rename(columns={field:name}); rows.append(t.set_index(["match_id","event_id","outcome"]))
    data=pd.concat(rows,axis=1).reset_index()
    data["deepest_defender_response"] = data.deepest_defender_displacement-data.ball_progression_5s
    data["attack_line_response"] = data.attack_line_displacement-data.ball_progression_5s
    data["midfield_response"] = data.midfield_displacement-data.ball_progression_5s
    data["pair_id"]=data.match_id.astype(str)+"_"+data.event_id.astype(str)
    model_features=list(CONTEXT)+list(TRAJECTORY)
    pair=data.pivot(index="pair_id",columns="outcome",values=model_features).dropna()
    deltas=pd.DataFrame({c:pair[(c,"shot")]-pair[(c,"control")] for c in model_features})
    corr=deltas.corr(); dist=pd.DataFrame([{ "feature":c,"pairs":len(deltas),"median_delta":deltas[c].median(),"q25":deltas[c].quantile(.25),"q75":deltas[c].quantile(.75),"pct_positive":(deltas[c]>0).mean(),"sign_flip_pvalue":_sign_flip_pvalue(deltas[c]) } for c in deltas])
    models=[]
    context_ll=None
    for added in [None,*TRAJECTORY]:
      # No intercept exists in the conditional likelihood. Centreing deltas
      # would erase their mean signal and make beta=0 artificially stationary.
      cols=list(CONTEXT)+([] if added is None else [added]); raw=deltas[cols]; x=(raw/raw.std(ddof=0)).to_numpy(); b,se,ok,it,cond,ll,acc=_fit(x)
      if context_ll is None: context_ll=ll
      for c,v,s in zip(cols,b,se): models.append({"model":"context_only" if added is None else f"context_plus_{added}","feature":c,"pairs":len(x),"coefficient_standardized":v,"odds_ratio":np.exp(v),"ci95_low":np.exp(v-1.96*s) if np.isfinite(s) else np.nan,"ci95_high":np.exp(v+1.96*s) if np.isfinite(s) else np.nan,"converged":ok,"iterations":it,"hessian_condition_number":cond,"log_likelihood":ll,"log_likelihood_gain_vs_null":ll+len(x)*np.log(2),"log_likelihood_gain_vs_context":ll-context_ll,"pair_accuracy":acc})
    return {"pair_deltas":deltas,"model_free_evidence":dist,"delta_correlations":corr.reset_index().rename(columns={"index":"feature"}),"conditional_models":pd.DataFrame(models)}
