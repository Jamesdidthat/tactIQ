"""Stable v1 JSON response serializers for product-facing match analysis."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.ai import ExplanationResult, MatchStoryExplanationResult
from src.analysis.finding_prioritization import EvidencePack, FindingPrioritizationResult
from src.analysis.tactical_findings import MatchAnalysisResult, TacticalFinding
from src.data import CanonicalMatchBundle


SCHEMA_VERSION = "v1"


def json_safe(value: Any) -> Any:
    """Convert analysis values into standard-library JSON-compatible values."""
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def _capabilities(bundle: CanonicalMatchBundle) -> dict[str, bool]:
    return json_safe(bundle.capabilities)


def serialize_analysis_coverage(result: MatchAnalysisResult) -> dict[str, Any]:
    """`AnalysisCoverageResponse v1`: availability, execution, and reasons."""
    columns = [column for column in ("analysis", "supported", "status", "reason", "finding_count") if column in result.analysis_coverage]
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_coverage": json_safe(result.analysis_coverage[columns].to_dict("records")),
    }


def serialize_match_summary(bundle: CanonicalMatchBundle, result: MatchAnalysisResult, ranked: FindingPrioritizationResult) -> dict[str, Any]:
    """`MatchSummaryResponse v1`: compact match and analysis status."""
    match = bundle.matches.iloc[0]
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "match": {
            "match_id": match.match_id, "provider": bundle.provider,
            "pitch_length_m": match.pitch_length_m, "pitch_width_m": match.pitch_width_m,
            "date_time": bundle.match_info.get("date_time"),
            "home_team": {
                "team_id": bundle.match_info.get("home_team", {}).get("id"),
                "name": bundle.match_info.get("home_team", {}).get("name"),
                "code": bundle.match_info.get("home_team", {}).get("acronym"),
                "score": bundle.match_info.get("home_team_score"),
                "crest_url": bundle.match_info.get("home_team", {}).get("crest_url") or bundle.match_info.get("home_team", {}).get("logo_url"),
            },
            "away_team": {
                "team_id": bundle.match_info.get("away_team", {}).get("id"),
                "name": bundle.match_info.get("away_team", {}).get("name"),
                "code": bundle.match_info.get("away_team", {}).get("acronym"),
                "score": bundle.match_info.get("away_team_score"),
                "crest_url": bundle.match_info.get("away_team", {}).get("crest_url") or bundle.match_info.get("away_team", {}).get("logo_url"),
            },
        },
        "capabilities": _capabilities(bundle),
        "finding_count": len(result.findings),
        "shortlist_count": len(ranked.shortlist),
        "warnings": result.warnings,
        "analysis_coverage": serialize_analysis_coverage(result)["analysis_coverage"],
    })


def _finding_payload(finding: TacticalFinding, rank: int | None, priority: Mapping[str, Any], selection_reason: str | None = None) -> dict[str, Any]:
    return json_safe({
        "rank": rank, "finding_id": finding.finding_id, "match_id": finding.match_id,
        "team_id": finding.team_id, "finding_type": finding.finding_type,
        "title": finding.title, "description": finding.description,
        "sample_size": finding.sample_size, "confidence_level": finding.confidence_level,
        "priority": priority, "selection_reason": selection_reason, "limitations": finding.limitations,
    })


def serialize_ranked_findings(result: MatchAnalysisResult, ranked: FindingPrioritizationResult) -> dict[str, Any]:
    """`RankedFindingsResponse v1`: deterministic shortlist with components."""
    priority_by_id = ranked.priorities.set_index("finding_id").to_dict("index") if not ranked.priorities.empty else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "ranked_findings": [
            _finding_payload(finding, rank, priority_by_id[finding.finding_id], ranked.selection_reasons.get(finding.finding_id))
            for rank, finding in enumerate(ranked.shortlist, start=1)
        ],
    }


def serialize_finding_detail(finding: TacticalFinding, pack: EvidencePack, rank: int | None, selection_reason: str | None = None) -> dict[str, Any]:
    """`FindingDetailResponse v1`: full deterministic evidence trace."""
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "finding": _finding_payload(finding, rank, asdict(pack.priority), selection_reason),
        "evidence": {
            "exact_metrics": pack.exact_metrics, "comparator": pack.comparator,
            "supporting_references": pack.supporting_references,
            "representative_moments": pack.representative_moments,
            "capability_provenance": pack.capability_provenance,
            "coverage": pack.coverage, "limitations": pack.limitations,
        },
    })


def serialize_finding_explanation(result: ExplanationResult) -> dict[str, Any]:
    """`FindingExplanationResponse v1`: bounded prose plus audit metadata."""
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "finding_id": result.finding_id,
        "explanation": asdict(result.explanation),
        "metadata": {
            "evidence_hash": result.evidence_hash,
            "prompt_version": result.prompt_version,
            "model_id": result.model_id,
            "source": result.source,
            "cache_hit": result.cache_hit,
            "validation_warnings": result.validation_warnings,
        },
    })


def serialize_match_story_explanation(result: MatchStoryExplanationResult) -> dict[str, Any]:
    """`MatchStoryExplanationResponse v1`: grounded prose plus cache provenance."""
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "match_id": result.match_id,
        "explanation": asdict(result.explanation),
        "metadata": {
            "evidence_hash": result.evidence_hash,
            "prompt_version": result.prompt_version,
            "provider_id": result.provider_id,
            "model_id": result.model_id,
            "source": result.source,
            "cache_hit": result.cache_hit,
            "validation_warnings": result.validation_warnings,
        },
    })


def serialize_pitch_frame(bundle: CanonicalMatchBundle, *, frame: int, period: int) -> dict[str, Any]:
    """`RepresentativePitchFrameResponse v1` from canonical positions only."""
    players = bundle.player_positions.loc[
        bundle.player_positions.frame.eq(frame) & bundle.player_positions.period.eq(period)
    ].copy()
    if players.empty:
        raise KeyError(f"No canonical player positions for frame={frame}, period={period}.")
    ball = bundle.ball_positions.loc[
        bundle.ball_positions.frame.eq(frame) & bundle.ball_positions.period.eq(period)
    ]
    match = bundle.matches.iloc[0]
    if 'player_number' in bundle.roster:
        roster = bundle.roster[['player_id', 'team_id', 'player_number']].rename(columns={'player_number': 'roster_number'})
        players = players.merge(roster, on=['player_id', 'team_id'], how='left', validate='many_to_one')
        players['player_number'] = players.roster_number.combine_first(players.get('player_number', pd.Series(index=players.index, dtype=object)))
    player_columns = [column for column in ("player_id", "player_number", "team_id", "team_acronym", "position", "position_group", "x", "y", "is_detected") if column in players]
    timestamp = players.timestamp.iloc[0] if "timestamp" in players else None
    elapsed = players.elapsed_seconds.iloc[0]
    ball_row = ball.iloc[0] if not ball.empty else None
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "match_id": match.match_id, "frame": frame, "period": period,
        "timestamp": timestamp, "elapsed_seconds": elapsed,
        "pitch": {"length_m": match.pitch_length_m, "width_m": match.pitch_width_m},
        "players": players[player_columns].to_dict("records"),
        "ball": None if ball_row is None else {"x": ball_row.ball_x, "y": ball_row.ball_y, "is_observed": pd.notna(ball_row.ball_x) and pd.notna(ball_row.ball_y)},
    })


def serialize_pitch_clip(
    bundle: CanonicalMatchBundle,
    *,
    centre_frame: int,
    period: int,
    before_frames: int = 25,
    after_frames: int = 25,
    step: int = 1,
    before_seconds: float | None = None,
    after_seconds: float | None = None,
) -> dict[str, Any]:
    """Return a bounded, same-period tracking clip around an observed frame."""
    if before_frames < 0 or after_frames < 0:
        raise ValueError("Clip frame bounds must be non-negative.")
    if step < 1:
        raise ValueError("Clip step must be at least one frame.")
    if before_frames + after_frames > 200:
        raise ValueError("A pitch clip may span at most 200 source frames.")
    if before_seconds is not None or after_seconds is not None:
        before_seconds = 0.0 if before_seconds is None else float(before_seconds)
        after_seconds = 0.0 if after_seconds is None else float(after_seconds)
        if before_seconds < 0 or after_seconds < 0:
            raise ValueError("Clip time bounds must be non-negative.")
        if before_seconds + after_seconds > 20:
            raise ValueError("A pitch clip may span at most 20 seconds.")

    observations = (
        bundle.player_positions.loc[bundle.player_positions.period.eq(period), ["frame", "elapsed_seconds"]]
        .drop_duplicates("frame")
        .sort_values("frame")
    )
    if observations.empty or centre_frame not in set(observations.frame.astype(int)):
        raise KeyError(f"No canonical player positions for frame={centre_frame}, period={period}.")

    if before_seconds is not None and after_seconds is not None:
        centre_time = float(observations.loc[observations.frame.astype(int).eq(centre_frame), "elapsed_seconds"].iloc[0])
        selected = observations.loc[observations.elapsed_seconds.between(
            centre_time - before_seconds, centre_time + after_seconds
        )].copy()
    else:
        start = centre_frame - before_frames
        end = centre_frame + after_frames
        selected = observations.loc[observations.frame.between(start, end)].copy()
    selected = selected.loc[((selected.frame.astype(int) - centre_frame).abs() % step).eq(0)]
    if selected.empty:
        raise KeyError("No canonical frames fall inside the requested clip.")

    timing = observations.assign(
        frame_delta=observations.frame.diff(),
        time_delta=observations.elapsed_seconds.diff(),
    )
    rates = timing.loc[timing.time_delta.gt(0) & timing.frame_delta.gt(0), "frame_delta"] / timing.loc[
        timing.time_delta.gt(0) & timing.frame_delta.gt(0), "time_delta"
    ]
    source_rate_hz = float(rates.median()) if not rates.empty else None
    frames = [
        serialize_pitch_frame(bundle, frame=int(frame), period=int(period))
        for frame in selected.frame.astype(int).tolist()
    ]
    focus_index = next(index for index, item in enumerate(frames) if int(item["frame"]) == centre_frame)
    return json_safe({
        "schema_version": SCHEMA_VERSION,
        "provider": bundle.provider,
        "match_id": bundle.matches.iloc[0].match_id,
        "period": period,
        "centre_frame": centre_frame,
        "focus_index": focus_index,
        "source_frame_rate_hz": source_rate_hz,
        "playback_frame_rate_hz": None if source_rate_hz is None else source_rate_hz / step,
        "requested": {
            "before_frames": before_frames, "after_frames": after_frames,
            "before_seconds": before_seconds, "after_seconds": after_seconds, "step": step,
        },
        "actual_start_frame": frames[0]["frame"],
        "actual_end_frame": frames[-1]["frame"],
        "actual_duration_seconds": float(frames[-1]["elapsed_seconds"] - frames[0]["elapsed_seconds"]),
        "frames": frames,
        "limitations": [
            "The clip contains only available tracking frames from the same match period.",
            "Extrapolated player positions are preserved and identified rather than hidden or imputed.",
            "The structural overlay describes observed geometry and does not infer tactical intent.",
        ],
    })
