"""Deterministic typical-versus-high-tail evidence for Team Shape findings."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


PHASE_INTERVAL_COLUMNS = ("period", "phase_frame_start", "phase_frame_end")


def group_high_tail_episodes(
    rows: pd.DataFrame,
    metric: str,
    *,
    high_tail_threshold: float,
) -> pd.DataFrame:
    """Label contiguous high-tail frames as episodes within each period.

    Frame numbers must be consecutive to belong to the same episode. Period
    boundaries always start a new episode, even when providers reuse frame
    numbers or happen to make them numerically consecutive.
    """
    required = {"frame", "period", metric}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"Team-shape evidence is missing columns: {sorted(missing)}")

    valid = rows.dropna(subset=["frame", "period", metric]).copy()
    valid = valid.loc[np.isfinite(valid[metric]) & valid[metric].ge(high_tail_threshold)]
    if valid.empty:
        return valid.assign(
            extreme_episode_id=pd.Series(dtype="int64"),
            episode_frame_start=pd.Series(dtype="int64"),
            episode_frame_end_inclusive=pd.Series(dtype="int64"),
            episode_frame_count=pd.Series(dtype="int64"),
        )

    valid = valid.sort_values(["period", "frame"], kind="stable").copy()
    new_episode = valid["period"].ne(valid["period"].shift()) | valid["frame"].sub(valid["frame"].shift()).ne(1)
    valid["extreme_episode_id"] = new_episode.cumsum().astype(int)
    grouped = valid.groupby("extreme_episode_id", sort=True)
    valid["episode_frame_start"] = grouped["frame"].transform("min").astype(int)
    valid["episode_frame_end_inclusive"] = grouped["frame"].transform("max").astype(int)
    valid["episode_frame_count"] = grouped["frame"].transform("size").astype(int)
    return valid


def _phase_interval(row: pd.Series) -> tuple[Any, Any, Any] | None:
    if not all(column in row.index and pd.notna(row[column]) for column in PHASE_INTERVAL_COLUMNS):
        return None
    return tuple(row[column] for column in PHASE_INTERVAL_COLUMNS)


def _reference(row: pd.Series, *, label: str, metric: str, target: float, quantile: float) -> dict[str, Any]:
    columns = (
        "frame", "period", "timestamp", "elapsed_seconds", "tactical_phase",
        "possession_status", "phase_frame_start", "phase_frame_end",
        "extreme_episode_id", "episode_frame_start", "episode_frame_end_inclusive",
        "episode_frame_count",
    )
    reference = {column: row[column] for column in columns if column in row.index and pd.notna(row[column])}
    reference.update(
        label=label,
        metric=metric,
        metric_value_metres=float(row[metric]),
        target_quantile=quantile,
        target_value_metres=float(target),
        target_error_metres=abs(float(row[metric]) - float(target)),
    )
    return reference


def select_typical_and_extreme_moments(rows: pd.DataFrame, metric: str) -> dict[str, Any] | None:
    """Select a median-like frame and one representative Q95 episode peak.

    The typical frame is selected outside the chosen extreme episode. When
    phase intervals are available, a different source interval is preferred.
    The extreme moment is the peak of the strongest contiguous Q95 episode;
    consecutive frames are therefore never presented as separate evidence.
    """
    required = {"frame", "period", metric}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"Team-shape evidence is missing columns: {sorted(missing)}")
    valid = rows.dropna(subset=["frame", "period", metric]).copy()
    valid = valid.loc[np.isfinite(valid[metric])]
    if len(valid) < 20:
        return None

    median = float(valid[metric].median())
    q95 = float(valid[metric].quantile(0.95))
    episodes = group_high_tail_episodes(valid, metric, high_tail_threshold=q95)
    if episodes.empty or q95 <= median:
        return None

    # When phase context exists, prefer a high-tail frame whose football
    # context can be surfaced in the product. Unlabelled tracking gaps remain
    # valid data, but they are weaker representative evidence than an equally
    # valid labelled high-tail episode.
    episode_candidates = episodes
    if "tactical_phase" in episodes and episodes["tactical_phase"].notna().any():
        episode_candidates = episodes.loc[episodes["tactical_phase"].notna()]

    # One peak represents each episode. Stable sorting makes ties reproducible.
    episode_peaks = (
        episode_candidates.sort_values([metric, "period", "frame"], ascending=[False, True, True], kind="stable")
        .drop_duplicates("extreme_episode_id")
    )
    extreme = episode_peaks.iloc[0]
    if float(extreme[metric]) <= median:
        return None

    outside_episode = ~(
        valid["period"].eq(extreme["period"])
        & valid["frame"].between(extreme["episode_frame_start"], extreme["episode_frame_end_inclusive"])
    )
    typical_candidates = valid.loc[outside_episode].copy()
    if typical_candidates.empty:
        return None

    extreme_interval = _phase_interval(extreme)
    if extreme_interval is not None and all(column in typical_candidates for column in PHASE_INTERVAL_COLUMNS):
        candidate_intervals = typical_candidates.apply(_phase_interval, axis=1)
        typical_candidates["context_preference"] = candidate_intervals.map(
            lambda interval: 0 if interval is not None and interval != extreme_interval else 1
        )
    else:
        typical_candidates["context_preference"] = 0
    typical_candidates["median_error"] = (typical_candidates[metric] - median).abs()
    typical = typical_candidates.sort_values(
        ["context_preference", "median_error", "period", "frame"], kind="stable"
    ).iloc[0]

    dimension = metric.removeprefix("outfield_")
    extreme_label = "Wide example" if dimension == "width" else "Extended example"
    typical_reference = _reference(typical, label="Typical example", metric=metric, target=median, quantile=0.5)
    extreme_reference = _reference(extreme, label=extreme_label, metric=metric, target=q95, quantile=0.95)
    extreme_reference["is_at_or_above_q95"] = True

    typical_interval = _phase_interval(typical)
    if extreme_interval is not None and typical_interval is not None and typical_interval != extreme_interval:
        separation = "different_tactical_phase" if (
            "tactical_phase" in extreme.index and "tactical_phase" in typical.index
            and pd.notna(extreme.get("tactical_phase")) and pd.notna(typical.get("tactical_phase"))
            and extreme.get("tactical_phase") != typical.get("tactical_phase")
        ) else "different_phase_interval"
    else:
        separation = "different_extreme_episode"

    return {
        "median_metres": median,
        "q95_metres": q95,
        "extreme_metres": float(extreme[metric]),
        "absolute_deviation_from_median_metres": abs(float(extreme[metric]) - median),
        "extreme_episode_count": int(episodes["extreme_episode_id"].nunique()),
        "evidence_context_separation": separation,
        "extreme_timestamp": extreme.get("timestamp", pd.NA),
        "extreme_period": int(extreme["period"]),
        "extreme_tactical_phase": extreme.get("tactical_phase", pd.NA),
        "references": (typical_reference, extreme_reference),
    }
