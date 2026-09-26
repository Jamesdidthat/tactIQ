"""Run a reproducible multi-matchup QA evidence audit for pre-match review priorities."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import re

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import (
    analyze_matchup_interactions, build_pre_match_review_priorities,
    compare_event_team_profiles, generate_event_profile_findings,
)
from src.api import load_event_profile_artifact
from src.analysis.pre_match_review import METRIC_CONCEPT_LABELS


STYLE_METRICS = (
    "possession_share_estimate", "shots_per90", "high_regains_per90",
    "progressive_passes_per90", "passes_into_penalty_area_per90", "xg_per90",
    "pressures_per90", "turnovers_leading_to_shot_per90",
)

INTERACTION_TITLE_CONCEPTS = {
    "penalty_area_access": "Penalty-area entries",
    "shot_volume": "Shots",
    "xg_production": "xG",
    "shot_quality": "xG per shot",
    "explicit_counter_attack_shots": "Explicit counter-attack shots",
    "set_play_shots": "Set-play shots",
}
PLURAL_WITH_SINGULAR_VERB = re.compile(
    r"\b(patterns|entries|shots|passes|carries|pressures|tackles|interceptions|recoveries|regains|exposures) differs\b",
    re.IGNORECASE,
)


def _safe(value):
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def _load_profiles(directory: Path) -> dict[int, object]:
    manifest_path = next(directory.glob("*_manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = {}
    for item in manifest["teams"]:
        path = Path(item["artifact"])
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        profiles[int(item["team_id"])] = load_event_profile_artifact(path)
    return profiles


def _style_table(profiles: dict[int, object]) -> pd.DataFrame:
    rows = []
    for team_id, profile in profiles.items():
        row = {"team_id": team_id, "team_name": profile.team_name}
        for metric in STYLE_METRICS:
            row[metric] = float(pd.to_numeric(profile.match_metrics[metric], errors="coerce").median())
        rows.append(row)
    frame = pd.DataFrame(rows).sort_values("team_name", kind="stable").reset_index(drop=True)
    for metric in STYLE_METRICS:
        frame[f"{metric}_rank_high"] = frame[metric].rank(method="min", ascending=False).astype(int)
    return frame


def _closest_pairs(styles: pd.DataFrame) -> list[tuple[int, int, float]]:
    values = styles[list(STYLE_METRICS)].copy()
    scaled = (values - values.median()) / values.apply(lambda column: max((column.quantile(.75) - column.quantile(.25)) / 1.349, 1e-9))
    rows = []
    for left in range(len(styles)):
        for right in range(left + 1, len(styles)):
            distance = float(np.sqrt(np.square(scaled.iloc[left] - scaled.iloc[right]).mean()))
            rows.append((int(styles.iloc[left].team_id), int(styles.iloc[right].team_id), distance))
    return sorted(rows, key=lambda row: (row[2], row[0], row[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", default="artifacts/event_profiles/statsbomb_11_27")
    parser.add_argument("--output", default="artifacts/pre_match_review_priority_qa_v1.json")
    options = parser.parse_args()
    profiles = _load_profiles(Path(options.profile_dir))
    styles = _style_table(profiles)
    tendencies = {team_id: generate_event_profile_findings(profile).recurring_tendencies for team_id, profile in profiles.items()}

    pair_cache = {}
    ids = sorted(profiles)
    for left_index, left in enumerate(ids):
        for right in ids[left_index + 1:]:
            comparison = compare_event_team_profiles(profiles[left], profiles[right])
            interactions = analyze_matchup_interactions(profiles[left], profiles[right])
            review = build_pre_match_review_priorities(
                comparison, interactions,
                target_recurring_tendencies=tendencies[left],
                opponent_recurring_tendencies=tendencies[right],
            )
            baseline_review = build_pre_match_review_priorities(
                comparison, interactions,
                target_recurring_tendencies=tendencies[left],
                opponent_recurring_tendencies=tendencies[right],
                slot_admission_thresholds=(.58, .58, .58, .58, .58),
                enable_semantic_group_suppression=False,
            )
            baseline_ids = {item.primary_evidence["finding_id"] for item in baseline_review.priorities}
            review_ids = {item.primary_evidence["finding_id"] for item in review.priorities}
            removed_ids = baseline_ids - review_ids
            audit_lookup = review.candidate_audit.set_index("source_finding_id")
            baseline_by_id = {
                item.primary_evidence["finding_id"]: item for item in baseline_review.priorities
            }
            wording_issues = []
            title_specificity_issues = []
            for item in review.priorities:
                if PLURAL_WITH_SINGULAR_VERB.search(item.review_question):
                    wording_issues.append({"priority_id": item.priority_id, "text": item.review_question})
                primary = item.primary_evidence
                if item.primary_source_role == "general_team_comparison":
                    expected = METRIC_CONCEPT_LABELS.get(str(primary.get("metric")), "")
                else:
                    family = item.priority_id.rsplit(":", 1)[-1]
                    expected = INTERACTION_TITLE_CONCEPTS.get(family, "")
                if expected and expected.casefold() not in item.title.casefold():
                    title_specificity_issues.append({
                        "priority_id": item.priority_id, "title": item.title,
                        "expected_concept": expected,
                    })
            pair_cache[(left, right)] = {
                "comparison": comparison, "interactions": interactions,
                "qualified_comparisons": len(comparison.findings),
                "qualified_interactions": len(interactions.findings),
                "review_priority_count": len(review.priorities),
                "review_source_role_counts": pd.Series(
                    [item.primary_source_role for item in review.priorities], dtype="object",
                ).value_counts().to_dict(),
                "demoted_general_comparisons": int(review.candidate_audit.status.eq("demoted_to_support").sum()),
                "baseline_review_priority_count": len(baseline_review.priorities),
                "removed_priority_statuses": [
                    str(audit_lookup.loc[source_id, "status"]) for source_id in sorted(removed_ids)
                    if source_id in audit_lookup.index
                ],
                "removed_priority_details": [
                    {
                        "source_finding_id": source_id,
                        "baseline_rank": baseline_by_id[source_id].rank,
                        "priority_score": baseline_by_id[source_id].priority_score,
                        "primary_source_role": baseline_by_id[source_id].primary_source_role,
                        "title": baseline_by_id[source_id].title,
                        "removal_status": str(audit_lookup.loc[source_id, "status"]),
                        "supporting_priority_source_id": audit_lookup.loc[source_id, "supporting_priority_source_id"],
                    }
                    for source_id in sorted(removed_ids) if source_id in audit_lookup.index
                ],
                "removed_strong_directional_ids": [
                    item.primary_evidence["finding_id"] for item in baseline_review.priorities
                    if item.primary_source_role == "directional_matchup_interaction"
                    and item.priority_score >= .72
                    and item.primary_evidence["finding_id"] in removed_ids
                ],
                "kept_related_directional": [
                    [first.primary_evidence["finding_id"], second.primary_evidence["finding_id"]]
                    for index, first in enumerate(review.priorities)
                    for second in review.priorities[index + 1:]
                    if first.primary_source_role == second.primary_source_role == "directional_matchup_interaction"
                    and first.direction == second.direction
                    and (
                        {first.football_family, second.football_family} <= {"chance_creation", "shot_quality"}
                        or {first.football_family, second.football_family} <= {"territorial_access", "penalty_area_access"}
                    )
                ],
                "wording_issues": wording_issues,
                "title_specificity_issues": title_specificity_issues,
            }

    selected: list[tuple[str, int, int, dict]] = []
    seen: set[frozenset[int]] = set()

    def add(category: str, left: int, right: int, basis: dict) -> bool:
        key = frozenset((left, right))
        if left == right or key in seen:
            return False
        seen.add(key)
        selected.append((category, left, right, basis))
        return True

    def cross_ranked(category: str, metric: str, high_positions: range, low_positions: range) -> None:
        ranked = styles.sort_values(metric, ascending=False, kind="stable")
        for high in high_positions:
            for low in low_positions:
                left, right = int(ranked.iloc[high].team_id), int(ranked.iloc[-1 - low].team_id)
                if add(category, left, right, {
                    "selection_metric": metric, "target_value": float(ranked.iloc[high][metric]),
                    "opponent_value": float(ranked.iloc[-1 - low][metric]),
                }):
                    return

    possession = styles.sort_values("possession_share_estimate", ascending=False, kind="stable")
    add("dominant_possession_vs_dominant_possession", int(possession.iloc[0].team_id), int(possession.iloc[1].team_id), {
        "selection_metric": "possession_share_estimate", "target_value": float(possession.iloc[0].possession_share_estimate),
        "opponent_value": float(possession.iloc[1].possession_share_estimate),
    })
    cross_ranked("dominant_possession_vs_low_possession", "possession_share_estimate", range(0, 3), range(0, 4))
    cross_ranked("dominant_possession_vs_low_possession_secondary", "possession_share_estimate", range(1, 5), range(1, 6))
    cross_ranked("high_shot_volume_vs_low_shot_volume", "shots_per90", range(0, 4), range(0, 5))
    cross_ranked("high_regain_vs_low_regain", "high_regains_per90", range(0, 4), range(0, 5))
    cross_ranked("high_regain_vs_low_regain_secondary", "high_regains_per90", range(1, 6), range(1, 7))

    for number, (left, right, distance) in enumerate(_closest_pairs(styles)[:20], start=1):
        if add("closely_matched_teams" if number == 1 else "closely_matched_teams_secondary", left, right, {"robust_multimetric_distance": distance}):
            if sum(category.startswith("closely_matched") for category, *_ in selected) == 2:
                break

    few = sorted(pair_cache.items(), key=lambda item: (
        item[1]["qualified_interactions"], item[1]["qualified_comparisons"], item[0][0], item[0][1],
    ))
    for (left, right), evidence in few:
        if add("few_or_zero_qualified_interactions", left, right, {
            "qualified_interactions": evidence["qualified_interactions"],
            "qualified_comparisons": evidence["qualified_comparisons"],
        }) and sum(category == "few_or_zero_qualified_interactions" for category, *_ in selected) == 2:
            break

    reports = []
    for qa_index, (category, target_id, opponent_id, selection_basis) in enumerate(selected, start=1):
        key = tuple(sorted((target_id, opponent_id)))
        cached = pair_cache[key]
        comparison = compare_event_team_profiles(profiles[target_id], profiles[opponent_id])
        interactions = analyze_matchup_interactions(profiles[target_id], profiles[opponent_id])
        priorities = build_pre_match_review_priorities(
            comparison, interactions,
            target_recurring_tendencies=tendencies[target_id],
            opponent_recurring_tendencies=tendencies[opponent_id],
        )
        baseline_priorities = build_pre_match_review_priorities(
            comparison, interactions,
            target_recurring_tendencies=tendencies[target_id],
            opponent_recurring_tendencies=tendencies[opponent_id],
            slot_admission_thresholds=(.58, .58, .58, .58, .58),
            enable_semantic_group_suppression=False,
        )
        priority_rows = []
        for item in priorities.priorities:
            primary = item.primary_evidence
            overlap = primary.get("iqr_overlap_ratio")
            priority_rows.append({
                **asdict(item),
                "overlap_separation_summary": {
                    "iqr_overlap_ratio": overlap,
                    "separation_ratio": None if overlap is None else 1.0 - float(overlap),
                    "material_overlap": primary.get("distributions_materially_overlap"),
                },
            })
        semantic_keys = [(item.direction, item.football_family) for item in priorities.priorities]
        role_counts = pd.Series(
            [item.primary_source_role for item in priorities.priorities], dtype="object",
        ).value_counts().to_dict()
        demoted = priorities.candidate_audit.loc[
            priorities.candidate_audit.status.eq("demoted_to_support")
        ]
        reports.append({
            "qa_index": qa_index, "selection_category": category, "selection_basis": selection_basis,
            "target_team_id": target_id, "target_team_name": profiles[target_id].team_name,
            "opponent_team_id": opponent_id, "opponent_team_name": profiles[opponent_id].team_name,
            "comparable_metrics": len(comparison.metric_comparisons),
            "qualified_directional_interactions": len(interactions.findings),
            "final_review_priorities": len(priorities.priorities),
            "baseline_review_priorities": len(baseline_priorities.priorities),
            "ordered_priorities": priority_rows,
            "primary_source_role_counts": role_counts,
            "demoted_general_comparisons": demoted[[
                "source_finding_id", "football_family", "priority_score",
                "supporting_priority_source_id", "reason",
            ]].to_dict("records"),
            "semantic_duplicate_survived": len(semantic_keys) != len(set(semantic_keys)),
            "candidate_status_counts": priorities.candidate_audit.status.value_counts().to_dict(),
            "manual_assessment": {
                "coherence": None, "redundancy": None, "directional_correctness": None,
                "football_usefulness": None, "evidence_adequacy": None, "overstatement": None,
                "missing_obvious_matchup_themes": None, "shortlist_caution": None,
                "cross_metric_comparison_misleading": None, "generic_priority": None,
            },
        })

    output = Path(options.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    interaction_count_distribution = pd.Series(
        [item["qualified_interactions"] for item in pair_cache.values()], dtype=int,
    ).value_counts().sort_index().to_dict()
    comparison_count_distribution = pd.Series(
        [item["qualified_comparisons"] for item in pair_cache.values()], dtype=int,
    ).value_counts().sort_index().to_dict()
    final_source_role_counts = pd.Series([
        priority["primary_source_role"]
        for report in reports for priority in report["ordered_priorities"]
    ], dtype="object").value_counts().to_dict()
    demoted_general_count = sum(len(report["demoted_general_comparisons"]) for report in reports)
    all_pair_source_role_counts: dict[str, int] = {}
    for evidence in pair_cache.values():
        for role, count in evidence["review_source_role_counts"].items():
            all_pair_source_role_counts[role] = all_pair_source_role_counts.get(role, 0) + int(count)
    all_pair_demoted_general_count = sum(
        int(evidence["demoted_general_comparisons"]) for evidence in pair_cache.values()
    )
    all_pair_priority_count_distribution = pd.Series(
        [item["review_priority_count"] for item in pair_cache.values()], dtype=int,
    ).value_counts().sort_index().to_dict()
    all_pair_baseline_priority_count_distribution = pd.Series(
        [item["baseline_review_priority_count"] for item in pair_cache.values()], dtype=int,
    ).value_counts().sort_index().to_dict()
    all_pair_removal_status_counts = pd.Series([
        status for evidence in pair_cache.values() for status in evidence["removed_priority_statuses"]
    ], dtype="object").value_counts().to_dict()
    all_pair_removed_strong_directional_ids = sorted({
        source_id for evidence in pair_cache.values()
        for source_id in evidence["removed_strong_directional_ids"]
    })
    all_pair_removed_by_baseline_rank = pd.Series([
        detail["baseline_rank"] for evidence in pair_cache.values()
        for detail in evidence["removed_priority_details"]
    ], dtype=int).value_counts().sort_index().to_dict()
    semantic_suppression_examples = [
        {"team_ids": list(pair), **detail}
        for pair, evidence in pair_cache.items()
        for detail in evidence["removed_priority_details"]
        if detail["removal_status"] == "suppressed_semantic_group"
    ][:10]
    kept_related_directional_examples = [
        {"team_ids": list(pair), "source_finding_ids": ids}
        for pair, evidence in pair_cache.items() for ids in evidence["kept_related_directional"]
    ][:10]
    all_pair_wording_issues = [
        {"team_ids": list(pair), **issue} for pair, evidence in pair_cache.items()
        for issue in evidence["wording_issues"]
    ]
    all_pair_title_specificity_issues = [
        {"team_ids": list(pair), **issue} for pair, evidence in pair_cache.items()
        for issue in evidence["title_specificity_issues"]
    ]
    output.write_text(json.dumps(_safe({
        "schema_version": "tactiq.pre-match-review-qa.v3",
        "provider": "statsbomb_open_data", "competition_id": 11, "season_id": 27,
        "team_profile_count": len(profiles), "matches_per_team": 38,
        "pairings_evaluated_for_selection": len(pair_cache),
        "all_pair_qualified_interaction_count_distribution": interaction_count_distribution,
        "all_pair_qualified_comparison_count_distribution": comparison_count_distribution,
        "all_pair_final_priority_count_distribution": all_pair_priority_count_distribution,
        "all_pair_baseline_priority_count_distribution": all_pair_baseline_priority_count_distribution,
        "all_pair_removed_priority_status_counts": all_pair_removal_status_counts,
        "all_pair_removed_strong_directional_ids": all_pair_removed_strong_directional_ids,
        "all_pair_removed_by_baseline_rank": all_pair_removed_by_baseline_rank,
        "semantic_suppression_examples": semantic_suppression_examples,
        "kept_related_directional_examples": kept_related_directional_examples,
        "all_pair_wording_issues": all_pair_wording_issues,
        "all_pair_title_specificity_issues": all_pair_title_specificity_issues,
        "all_pair_final_priority_source_role_counts": all_pair_source_role_counts,
        "all_pair_demoted_general_comparison_count": all_pair_demoted_general_count,
        "qa_final_priority_source_role_counts": final_source_role_counts,
        "qa_demoted_general_comparison_count": demoted_general_count,
        "selection_is_data_driven": True, "ranking_or_threshold_changes_during_audit": False,
        "team_style_medians": styles.to_dict("records"), "pairings": reports,
    }), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "profiles": len(profiles), "candidate_pairings": len(pair_cache),
        "qa_pairings": len(reports), "output": str(output),
        "selected": [(row["selection_category"], row["target_team_name"], row["opponent_team_name"], row["qualified_directional_interactions"], row["final_review_priorities"]) for row in reports],
    }, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
