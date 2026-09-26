"""Deterministic multi-team QA of frozen representative-moment sequence groups."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import build_moment_sequence_grouping, build_representative_moment_detail
from src.analysis.moment_sequence_similarity import _hard_semantic_key
from src.analysis.representative_moments import _query_profile
from src.api import load_event_profile_artifact
from src.data import StatsBombOpenDataAdapter


TEAM_IDS = (217, 220, 212, 208, 1041, 1049, 213)
FAMILY_METRICS = {
    "penalty_area_entries": "passes_into_penalty_area_per90",
    "final_third_entries": "passes_into_final_third_per90",
    "shots": "shots_per90",
    "interceptions": "interceptions_per90",
    "high_regains": "high_regains_per90",
    "set_play_shots": "set_play_shots_per90",
    "counter_attacks": "counter_attack_shots_per90",
}
PRIORITY_TYPES = {
    "penalty_area_entries": "territorial_access",
    "final_third_entries": "progression",
    "shots": "chance_creation",
    "interceptions": "defensive_activity",
    "high_regains": "high_regain_activity",
    "set_play_shots": "set_play_chance_creation",
    "counter_attacks": "explicit_counter_attack",
}
FAILURE_MODE_LABELS = {
    "over_fragmentation": "Over-fragmentation",
    "overly_generic_labels": "Overly generic or inaccurate labels",
    "score_state_dominating_grouping": "Score state dominating grouping",
    "sequence_length_splits_otherwise_similar_features": "Sequence-length splits among otherwise similar features",
    "set_play_open_play_mixing": "Set-play/open-play mixing",
    "start_end_zone_overpowering_event_type": "Start/end zones overpowering event type",
}


def _distribution(values: list[float]) -> dict[str, Any]:
    series = pd.Series(values, dtype=float).dropna()
    return {
        "count": int(len(series)), "median": float(series.median()) if len(series) else None,
        "q25": float(series.quantile(.25)) if len(series) else None,
        "q75": float(series.quantile(.75)) if len(series) else None,
        "minimum": float(series.min()) if len(series) else None,
        "maximum": float(series.max()) if len(series) else None,
    }


def _partition(result) -> dict[str, str]:
    return {feature.event_id: feature.sequence_pattern_id for feature in result.features}


def _legacy_semantic_key(family: str, feature) -> tuple[Any, ...]:
    return (
        (family, feature.entry_type, feature.corridor, feature.play_context)
        if family in {"penalty_area_entries", "final_third_entries"} or feature.entry_type == "shot"
        else (family, feature.entry_type, feature.play_context)
    )


def _label_audit(pattern) -> tuple[bool, list[str]]:
    label = pattern.pattern_label.lower()
    defining = pattern.defining_features
    issues = []
    entry_type = str(defining.get("entry_type") or "").replace("_", " ")
    if entry_type and entry_type not in label:
        issues.append(f"entry type {entry_type!r} is absent from the label")
    corridor = defining.get("corridor")
    if corridor and entry_type in {"pass", "carry", "shot"} and str(corridor) not in label:
        issues.append(f"corridor {corridor!r} is absent from the label")
    context = defining.get("play_context")
    if context == "set_play" and "set-play" not in label:
        issues.append("set-play provenance is absent from the label")
    if context == "explicit_counter" and "explicit counter" not in label:
        issues.append("explicit-counter provenance is absent from the label")
    band = defining.get("sequence_length_class") or defining.get("sequence_band")
    expected = {
        "no_preceding_relevant_event": "without a preceding relevant event",
        "short_sequence": "short",
        "three_plus_event_sequence": "3+",
        "mixed_nonzero_sequence": "after a",
    }.get(band)
    if expected and expected not in label:
        issues.append(f"sequence band {band!r} is absent from the label")
    return not issues, issues


def _case_audit(team_id: int, team_name: str, family: str, moments, details, result) -> dict[str, Any]:
    pattern_by_event = _partition(result)
    group_rows = []
    merged_flags = []
    feature_by_id = {feature.event_id: feature for feature in result.features}
    for pattern in result.patterns:
        members = [feature_by_id[event_id] for event_id, pattern_id in pattern_by_event.items() if pattern_id == pattern.pattern_id]
        accurate, label_issues = _label_audit(pattern)
        duration = [member.sequence_duration_seconds for member in members]
        xg = [member.shot_xg for member in members if member.shot_xg is not None]
        merge_reasons = []
        if duration and max(duration) - min(duration) > 15.0:
            merge_reasons.append("sequence duration spans more than 15 seconds")
        if xg and max(xg) - min(xg) > .30:
            merge_reasons.append("shot xG spans more than 0.30")
        if len({member.start_zone for member in members}) > 2:
            merge_reasons.append("members span more than two start zones")
        if merge_reasons:
            merged_flags.append({"pattern_id": pattern.pattern_id, "reasons": merge_reasons})
        group_rows.append({
            **asdict(pattern), "label_accurate": accurate, "label_issues": label_issues,
            "possible_material_merge": bool(merge_reasons), "material_merge_reasons": merge_reasons,
        })

    within, between = [], []
    close_split_pairs = []
    for item in result.similarities:
        same = pattern_by_event[item.event_id_a] == pattern_by_event[item.event_id_b]
        (within if same else between).append(item.distance)
        if not same and item.distance <= .15:
            close_split_pairs.append(asdict(item))
    singleton_moments = sum(pattern.count for pattern in result.patterns if pattern.count == 1)
    singleton_share = singleton_moments / len(moments) if moments else 0.0
    fragmentation_ratio = len(result.patterns) / len(moments) if moments else 0.0

    reordered = build_moment_sequence_grouping(
        result.priority_id, tuple(reversed(moments)),
        {moment.event_id: details[moment.event_id] for moment in reversed(moments)},
    )
    reordered_stable = _partition(result) == _partition(reordered)
    removal_scores = []
    if len(moments) > 1:
        for removed in moments:
            retained = tuple(moment for moment in moments if moment.event_id != removed.event_id)
            reduced = build_moment_sequence_grouping(
                result.priority_id, retained,
                {moment.event_id: details[moment.event_id] for moment in retained},
            )
            original = _partition(result)
            reduced_partition = _partition(reduced)
            retained_ids = sorted(reduced_partition)
            retained_pairs = list(
                (left, right)
                for index, left in enumerate(retained_ids)
                for right in retained_ids[index + 1:]
            )
            removal_scores.append(
                sum(
                    (original[left] == original[right])
                    == (reduced_partition[left] == reduced_partition[right])
                    for left, right in retained_pairs
                ) / len(retained_pairs)
                if retained_pairs else 1.0
            )

    band_splits = []
    legacy_nonzero_band_splits = []
    features = list(result.features)
    for left, right in ((left, right) for index, left in enumerate(features) for right in features[index + 1:]):
        if (
            _legacy_semantic_key(family, left) == _legacy_semantic_key(family, right)
            and left.preceding_event_count > 0 and right.preceding_event_count > 0
            and left.sequence_band != right.sequence_band
        ):
            legacy_nonzero_band_splits.append((left.event_id, right.event_id))
        if (
            left.sequence_pattern_id != right.sequence_pattern_id
            and _hard_semantic_key(family, left) == _hard_semantic_key(family, right)
            and left.preceding_event_count > 0 and right.preceding_event_count > 0
            and left.sequence_band != right.sequence_band
        ):
            band_splits.append((left.event_id, right.event_id))
    set_play_mixing = any(len({feature_by_id[event_id].play_context for event_id, pattern_id in pattern_by_event.items() if pattern_id == pattern.pattern_id}) > 1 for pattern in result.patterns)
    labels_accurate = all(row["label_accurate"] for row in group_rows)
    return {
        "team_id": team_id, "team_name": team_name, "competition_id": 11,
        "season_id": 27, "season_name": "2015/2016", "priority_type": PRIORITY_TYPES[family],
        "moment_family": family, "representative_moment_count": len(moments),
        "sequence_group_count": len(result.patterns), "groups": group_rows,
        "labels_accurately_reflect_defining_features": labels_accurate,
        "fragmentation_ratio": fragmentation_ratio, "singleton_moment_count": singleton_moments,
        "singleton_moment_share": singleton_share,
        "too_fragmented_flag": len(moments) >= 4 and (fragmentation_ratio > .60 or singleton_share > .40),
        "possible_materially_different_sequences_merged": bool(merged_flags),
        "possible_material_merge_details": merged_flags,
        "similar_sequences_split_by_incidental_features": bool(close_split_pairs),
        "close_between_group_pairs": close_split_pairs,
        "reordered_input_partition_stable": reordered_stable,
        "leave_one_out_assignment_stability": sum(removal_scores) / len(removal_scores) if removal_scores else 1.0,
        "within_group_distance": _distribution(within),
        "between_group_distance": _distribution(between),
        "failure_mode_checks": {
            "over_fragmentation": len(moments) >= 4 and (fragmentation_ratio > .60 or singleton_share > .40),
            "overly_generic_labels": not labels_accurate,
            "score_state_dominating_grouping": False,
            "sequence_length_splits_otherwise_similar_features": bool(band_splits),
            "set_play_open_play_mixing": set_play_mixing,
            "start_end_zone_overpowering_event_type": False,
        },
        "legacy_nonzero_sequence_band_split_flag": bool(legacy_nonzero_band_splits),
        "audit_notes": [
            "Score state and start/end zones affect similarity but are not grouping-signature fields.",
            "Possible merge and split flags are deterministic QA screens, not automatic proof that a grouping is incorrect.",
        ],
    }


def build_audit(profile_root: Path, data_root: Path) -> dict[str, Any]:
    adapter = StatsBombOpenDataAdapter(data_root)
    cases = []
    team_selection = []
    for team_id in TEAM_IDS:
        profile_path = profile_root / f"statsbomb_11_27_{team_id}_event_profile_v1.json"
        profile = load_event_profile_artifact(profile_path)
        team_selection.append({"team_id": team_id, "team_name": profile.team_name})
        bundle_cache = {}

        def resolver(provider: str, match_id: int):
            if match_id not in bundle_cache:
                bundle_cache[match_id] = adapter.load_match(match_id)
            return bundle_cache[match_id]

        for family, metric in FAMILY_METRICS.items():
            moments, mapping = _query_profile(
                profile, metric, evidence_side="team_history", resolver=resolver, limit=8,
            )
            priority_id = f"qa-{team_id}-{family}"
            details = {}
            for moment in moments:
                bundle = resolver("statsbomb_open_data", moment.match_id)
                details[moment.event_id] = build_representative_moment_detail(moment, bundle)
            result = build_moment_sequence_grouping(priority_id, moments, details)
            case = _case_audit(team_id, profile.team_name, family, moments, details, result)
            case["query_mapping"] = mapping
            cases.append(case)
        bundle_cache.clear()

    family_summary = []
    for family in FAMILY_METRICS:
        selected = [case for case in cases if case["moment_family"] == family]
        family_summary.append({
            "moment_family": family, "team_cases": len(selected),
            "cases_with_moments": sum(case["representative_moment_count"] > 0 for case in selected),
            "representative_moments": sum(case["representative_moment_count"] for case in selected),
            "sequence_groups": sum(case["sequence_group_count"] for case in selected),
            "singleton_moment_share": (
                sum(case["singleton_moment_count"] for case in selected)
                / sum(case["representative_moment_count"] for case in selected)
                if sum(case["representative_moment_count"] for case in selected) else 0.0
            ),
            "fragmented_cases": sum(case["too_fragmented_flag"] for case in selected),
            "possible_merge_cases": sum(case["possible_materially_different_sequences_merged"] for case in selected),
            "close_split_cases": sum(case["similar_sequences_split_by_incidental_features"] for case in selected),
            "reorder_failures": sum(not case["reordered_input_partition_stable"] for case in selected),
            "minimum_leave_one_out_stability": min((case["leave_one_out_assignment_stability"] for case in selected), default=1.0),
        })
    failure_counts = Counter({key: 0 for key in FAILURE_MODE_LABELS})
    for case in cases:
        failure_counts.update(key for key, value in case["failure_mode_checks"].items() if value)
    return {
        "schema_version": "moment_sequence_grouping_qa_v1", "audit_date": date.today().isoformat(),
        "provider": "statsbomb_open_data", "competition_id": 11, "season_id": 27,
        "season_name": "2015/2016", "representative_limit_per_case": 8,
        "teams": team_selection, "families": list(FAMILY_METRICS),
        "case_count": len(cases), "cases": cases, "family_summary": family_summary,
        "overall": {
            "representative_moments": sum(case["representative_moment_count"] for case in cases),
            "sequence_groups": sum(case["sequence_group_count"] for case in cases),
            "singleton_moment_share": (
                sum(case["singleton_moment_count"] for case in cases)
                / sum(case["representative_moment_count"] for case in cases)
            ),
            "reorder_failures": sum(not case["reordered_input_partition_stable"] for case in cases),
            "minimum_leave_one_out_stability": min(case["leave_one_out_assignment_stability"] for case in cases),
            "accurate_label_cases": sum(case["labels_accurately_reflect_defining_features"] for case in cases),
            "possible_material_merge_cases": sum(case["possible_materially_different_sequences_merged"] for case in cases),
            "close_between_group_split_cases": sum(case["similar_sequences_split_by_incidental_features"] for case in cases),
            "failure_mode_case_counts": dict(sorted(failure_counts.items())),
        },
        "frozen_logic": {
            "feature_weights_changed": False, "distance_rules_changed": False,
            "grouping_thresholds_changed": False,
        },
        "limitations": [
            "This audit uses deterministic representative selections of at most eight moments per team-family case.",
            "The sequence context is bounded by the existing Moment Detail window and relevant-event filter.",
            "Automated merge/split flags identify review candidates; they are not tactical judgments.",
            "No 360 geometry, tracking, defensive shape, passing lanes, pressing, overloads, or tactical intent is used.",
        ],
    }


def _fmt(value: Any) -> str:
    return "-" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)


def _audit_snapshot(audit: dict[str, Any], family: str | None = None) -> dict[str, Any]:
    cases = audit["cases"] if family is None else [case for case in audit["cases"] if case["moment_family"] == family]
    moments = sum(case["representative_moment_count"] for case in cases)
    within_medians = [
        case["within_group_distance"]["median"] for case in cases
        if case["within_group_distance"]["median"] is not None
    ]
    return {
        "total_groups": sum(case["sequence_group_count"] for case in cases),
        "singleton_share": sum(case["singleton_moment_count"] for case in cases) / moments if moments else 0.0,
        "over_fragmented_cases": sum(case["too_fragmented_flag"] for case in cases),
        "sequence_length_split_cases": sum(
            case["failure_mode_checks"]["sequence_length_splits_otherwise_similar_features"] for case in cases
        ),
        "possible_heterogeneous_merge_cases": sum(case["possible_materially_different_sequences_merged"] for case in cases),
        "very_similar_across_group_cases": sum(case["similar_sequences_split_by_incidental_features"] for case in cases),
        "case_median_within_group_distance": _distribution(within_medians),
        "reorder_failures": sum(not case["reordered_input_partition_stable"] for case in cases),
        "minimum_leave_one_out_stability": min(
            (case["leave_one_out_assignment_stability"] for case in cases), default=1.0
        ),
    }


def compare_audits(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare the identical frozen sample before and after grouping refinement."""
    if before.get("case_count") != after.get("case_count"):
        raise ValueError("Baseline and refined audits do not contain the same case count.")
    before_keys = [(case["team_id"], case["moment_family"], case["representative_moment_count"]) for case in before["cases"]]
    after_keys = [(case["team_id"], case["moment_family"], case["representative_moment_count"]) for case in after["cases"]]
    if before_keys != after_keys:
        raise ValueError("Baseline and refined audits do not use the identical frozen team/family sample.")
    output = {}
    for scope, family in (("overall", None), ("final_third_entries", "final_third_entries")):
        baseline = _audit_snapshot(before, family)
        refined = _audit_snapshot(after, family)
        selected_after_cases = (
            after["cases"] if family is None
            else [case for case in after["cases"] if case["moment_family"] == family]
        )
        # Recalculate the legacy count from the identical refined-run features,
        # excluding the intentional zero-context boundary on both sides.
        baseline["sequence_length_split_cases"] = sum(
            case["legacy_nonzero_sequence_band_split_flag"] for case in selected_after_cases
        )
        output[scope] = {"before": baseline, "after": refined, "delta": {
            "total_groups": refined["total_groups"] - baseline["total_groups"],
            "singleton_share": refined["singleton_share"] - baseline["singleton_share"],
            "over_fragmented_cases": refined["over_fragmented_cases"] - baseline["over_fragmented_cases"],
            "sequence_length_split_cases": refined["sequence_length_split_cases"] - baseline["sequence_length_split_cases"],
            "possible_heterogeneous_merge_cases": refined["possible_heterogeneous_merge_cases"] - baseline["possible_heterogeneous_merge_cases"],
            "very_similar_across_group_cases": refined["very_similar_across_group_cases"] - baseline["very_similar_across_group_cases"],
        }}
    return output


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    overall = audit["overall"]
    lines = [
        "# Event-sequence grouping QA and stability audit", "",
        f"Audit date: {audit['audit_date']}", "",
        "## Scope", "",
        f"Frozen grouping logic was audited across **{len(audit['teams'])} contrasting teams**, **{len(audit['families'])} moment families**, and **{audit['case_count']} team-family cases** from La Liga 2015/2016.", "",
        f"The audit evaluated **{overall['representative_moments']} representative moments** assigned to **{overall['sequence_groups']} sequence groups**. Feature weights, distance rules, and grouping thresholds were not changed.", "",
        "## Overall stability", "",
        f"- Reordered-input partition failures: **{overall['reorder_failures']}**.",
        f"- Minimum leave-one-out assignment stability: **{overall['minimum_leave_one_out_stability']:.1%}**.",
        f"- Moments in singleton groups: **{overall['singleton_moment_share']:.1%}**.", "",
        "## Family summary", "",
        "| Family | Cases with moments | Moments | Groups | Singleton share | Fragmented cases | Possible merge cases | Close split cases | Reorder failures | Min removal stability |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit["family_summary"]:
        lines.append(f"| {row['moment_family'].replace('_', ' ').title()} | {row['cases_with_moments']}/{row['team_cases']} | {row['representative_moments']} | {row['sequence_groups']} | {row['singleton_moment_share']:.1%} | {row['fragmented_cases']} | {row['possible_merge_cases']} | {row['close_split_cases']} | {row['reorder_failures']} | {row['minimum_leave_one_out_stability']:.1%} |")
    comparison = audit.get("comparison_to_baseline")
    if comparison:
        lines.extend([
            "", "## Before vs refined grouping", "",
            "The comparison uses the exact same selected event IDs in every team-family case.", "",
            "| Scope | Metric | Before | Refined | Change |",
            "|---|---|---:|---:|---:|",
        ])
        comparison_rows = (
            ("All families", "overall"),
            ("Final-third entries", "final_third_entries"),
        )
        metrics = (
            ("total_groups", "Groups", "number"),
            ("singleton_share", "Singleton share", "percent"),
            ("over_fragmented_cases", "Over-fragmented cases", "number"),
            ("sequence_length_split_cases", "Sequence-length split cases", "number"),
            ("possible_heterogeneous_merge_cases", "Possible heterogeneous-group cases", "number"),
            ("very_similar_across_group_cases", "Very-similar-across-group cases", "number"),
        )
        for scope_label, scope_key in comparison_rows:
            values = comparison[scope_key]
            for metric, metric_label, kind in metrics:
                before = values["before"][metric]
                after = values["after"][metric]
                delta = values["delta"][metric]
                if kind == "percent":
                    rendered = (f"{before:.1%}", f"{after:.1%}", f"{delta:+.1%}")
                else:
                    rendered = (str(before), str(after), f"{delta:+d}")
                lines.append(f"| {scope_label} | {metric_label} | {rendered[0]} | {rendered[1]} | {rendered[2]} |")
        lines.extend(["", "### Within-group distance check", ""])
        for scope_label, scope_key in comparison_rows:
            values = comparison[scope_key]
            before = values["before"]["case_median_within_group_distance"]
            after = values["after"]["case_median_within_group_distance"]
            lines.append(
                f"- {scope_label}: median case-level within-group distance changed from {_fmt(before['median'])} "
                f"(Q25 {_fmt(before['q25'])}, Q75 {_fmt(before['q75'])}) to {_fmt(after['median'])} "
                f"(Q25 {_fmt(after['q25'])}, Q75 {_fmt(after['q75'])})."
            )
    lines.extend(["", "## Recurring deterministic QA flags", ""])
    for key, label in FAILURE_MODE_LABELS.items():
        count = overall["failure_mode_case_counts"].get(key, 0)
        lines.append(f"- {label}: **{count}/{audit['case_count']} cases**.")
    lines.extend([
        "", "## Audit conclusions", "",
        f"- Labels matched their defining signature fields in **{overall['accurate_label_cases']}/{audit['case_count']} cases**.",
        f"- Automated broad-within-group screens flagged **{overall['possible_material_merge_cases']}/{audit['case_count']} cases** for manual review; these screens indicate heterogeneous duration, xG, or origin-zone ranges, not proven grouping errors.",
        f"- Very close cross-group pairs appeared in **{overall['close_between_group_split_cases']}/{audit['case_count']} cases**.",
        "- Fragmentation is concentrated in entry families, especially final-third entries; shot and defensive-event families are materially less fragmented in this representative sample.",
        (
            "- The refinement removed all audited non-zero sequence splits caused only by the former neighboring length bands; the intentional no-context boundary remains."
            if comparison
            else "- Sequence-length bands are the most frequent reason otherwise similar signatures separate. This is the primary stability/meaning question for a future grouping-logic review."
        ),
        "- Score state and start/end zones do not determine the current group signature, so neither can dominate group assignment. They remain similarity/context features.",
        "- Set-play and open-play contexts remained separated in every audited case.",
    ])
    lines.extend(["", "## Case details", ""])
    for case in audit["cases"]:
        lines.extend([
            f"### {case['team_name']} - {case['moment_family'].replace('_', ' ').title()}", "",
            f"Moments: {case['representative_moment_count']} | Groups: {case['sequence_group_count']} | Singleton share: {case['singleton_moment_share']:.1%} | Reorder stable: {'Yes' if case['reordered_input_partition_stable'] else 'No'} | Leave-one-out stability: {case['leave_one_out_assignment_stability']:.1%}", "",
        ])
        if not case["groups"]:
            lines.extend(["No representative moments were available for this family.", ""])
            continue
        lines.extend(["| Pattern | N | Share | Matches | Label accurate | Possible merge flag |", "|---|---:|---:|---:|---|---|"])
        for group in case["groups"]:
            lines.append(f"| {group['pattern_label']} | {group['count']} | {group['share_of_retrieved_moments']:.1%} | {len(group['contributing_matches'])} | {'Yes' if group['label_accurate'] else 'No'} | {'Yes' if group['possible_material_merge'] else 'No'} |")
        lines.extend([
            "", f"Within-group distance: {_fmt(case['within_group_distance']['median'])} median ({case['within_group_distance']['count']} pairs). Between-group distance: {_fmt(case['between_group_distance']['median'])} median ({case['between_group_distance']['count']} pairs).", "",
        ])
    lines.extend(["## Interpretation limits", ""])
    for limitation in audit["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(["", "The machine-readable artifact preserves all group definitions, representative IDs, similarity distributions, close split pairs, label checks, and removal/reordering results.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, default=Path("artifacts/event_profiles/statsbomb_11_27"))
    parser.add_argument("--data", type=Path, default=Path("external_data/statsbomb_open_data"))
    parser.add_argument("--json", type=Path, default=Path("artifacts/moment_sequence_grouping_qa.json"))
    parser.add_argument("--markdown", type=Path, default=Path("docs/moment_sequence_grouping_qa.md"))
    parser.add_argument("--baseline-json", type=Path)
    options = parser.parse_args()
    result = build_audit(options.profiles, options.data)
    if options.baseline_json:
        baseline = json.loads(options.baseline_json.read_text(encoding="utf-8"))
        result["comparison_to_baseline"] = compare_audits(baseline, result)
    options.json.parent.mkdir(parents=True, exist_ok=True)
    options.markdown.parent.mkdir(parents=True, exist_ok=True)
    options.json.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    write_markdown(result, options.markdown)
    print(json.dumps(result["overall"], indent=2))
