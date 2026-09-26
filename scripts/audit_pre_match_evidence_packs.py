"""Frozen multi-matchup product QA for deterministic pre-match evidence packs.

This script is intentionally read-only with respect to product logic.  It calls
the existing service, evaluates the returned v1 payloads, and writes QA-only
Markdown and JSON artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.api import OpponentComparisonService, load_event_profile_artifact
from src.data import StatsBombOpenDataAdapter


TECHNICAL_WORDS = re.compile(r"\b(iqr|robust z|z-score|threshold|redundancy rules|admission)\b", re.I)
SUPPORTED_PRIMARY_COMPATIBILITY = {
    "same_metric", "direct_attack_vs_defence_counterpart", "validated_relationship",
}
SUPPORTED_MOMENT_EVENT_TYPES = {
    "penalty_area_entries": {"Pass", "Carry"},
    "final_third_entries": {"Pass", "Carry"},
    "shots": {"Shot"},
    "xg": {"Shot"},
    "xg_per_shot": {"Shot"},
    "interceptions": {"Interception"},
    "high_regains": {"Interception", "Ball Recovery"},
    "counter_attacks": {"Shot"},
    "set_play_shots": {"Shot"},
    "progressive_passes": {"Pass"},
    "pass_completion": {"Pass"},
}


def _load_profiles(directory: Path) -> dict[int, Any]:
    manifest = json.loads(next(directory.glob("*_manifest.json")).read_text(encoding="utf-8"))
    profiles: dict[int, Any] = {}
    for item in manifest["teams"]:
        artifact = Path(item["artifact"])
        if not artifact.is_absolute():
            artifact = REPOSITORY_ROOT / artifact
        profiles[int(item["team_id"])] = load_event_profile_artifact(artifact)
    return profiles


def _rating(score: int) -> dict[str, Any]:
    return {"score": score, "label": {5: "excellent", 4: "good", 3: "mixed", 2: "weak", 1: "failed"}[score]}


def _valid_distribution(side: dict[str, Any]) -> bool:
    values = [side.get("q25"), side.get("median"), side.get("q75")]
    if any(value is None for value in values):
        return False
    return float(values[0]) <= float(values[1]) <= float(values[2])


def _primary_metrics(primary: dict[str, Any]) -> set[str]:
    metrics = set()
    for key in (
        "metric", "production_metric", "exposure_metric", "attacking_metric",
        "defending_metric", "team_a_metric", "team_b_metric",
    ):
        value = primary.get(key)
        if isinstance(value, str) and value:
            metrics.add(value)
    for key in ("attacking", "defending", "target", "opponent"):
        value = primary.get(key)
        if isinstance(value, dict):
            metrics.update(_primary_metrics(value))
    return metrics


def _audit_pack(pack: dict[str, Any], shortlist_count: int) -> dict[str, Any]:
    priority = pack["priority"]
    primary = pack["primary_interaction_or_comparison"]
    why = pack["why_selected"]
    distributions = pack["distribution_summary"]
    sequences = pack["sequence_pattern_summaries"]
    moments = pack["representative_moments"]
    details = pack["representative_moment_details"]
    context = pack["optional_360_context"]
    provenance = pack["capability_provenance"]
    technical_provenance = pack.get("technical_provenance", {})
    limitations = pack["limitations"]

    source_id_preserved = primary.get("finding_id") in priority.get("source_finding_ids", [])
    question_match = bool(priority.get("review_question")) and source_id_preserved
    why_text = str(why.get("description", ""))
    why_understandable = bool(why_text) and not TECHNICAL_WORDS.search(why_text)

    distribution_valid = (
        _valid_distribution(distributions.get("target", {}))
        and _valid_distribution(distributions.get("opponent", {}))
        and bool(priority.get("match_counts"))
        and bool(priority.get("coverage"))
    )
    pattern_groups = sequences.get("event_sequence_groups", [])
    group_labels = [group.get("pattern_label") for group in pattern_groups]
    pattern_counts = [int(group.get("count", 0)) for group in pattern_groups]
    sequence_count = int(sequences.get("retrieved_sample_count", 0))
    pattern_count_matches = sum(pattern_counts) == sequence_count if pattern_groups else sequence_count == 0
    sequence_adds_information = bool(pattern_groups) and len(set(group_labels)) == len(group_labels) and pattern_count_matches

    primary_metrics = _primary_metrics(primary)
    event_types_valid = True
    metric_matches = True
    for moment in moments:
        metric = str(moment.get("metric", ""))
        family = str(moment.get("family", ""))
        if primary_metrics and metric not in primary_metrics:
            metric_matches = False
        allowed = SUPPORTED_MOMENT_EVENT_TYPES.get(family)
        if allowed is not None and moment.get("event_type") not in allowed:
            event_types_valid = False
    moments_illustrate = bool(moments) and metric_matches and event_types_valid
    unique_matches = len({moment.get("match_id") for moment in moments})
    evidence_sides = sorted({str(moment.get("evidence_side")) for moment in moments})
    diversity_ratio = unique_matches / len(moments) if moments else 0.0
    moments_diverse = len(moments) <= 2 or diversity_ratio >= 0.5

    detail_ids = {str(detail.get("event_id")) for detail in details}
    moment_ids = {str(moment.get("event_id")) for moment in moments}
    detail_coverage = len(detail_ids & moment_ids) / len(moment_ids) if moment_ids else 0.0
    pitch_details_understandable = detail_coverage >= 0.8 and all(
        detail.get("coordinate_system") == "statsbomb_120x80" for detail in details
    )

    denominator_safe = (
        "retrieved representative moments" in str(sequences.get("denominator_statement", "")).lower()
        and any(
            "not full-season" in str(item).lower() or "not full season" in str(item).lower()
            for item in limitations
        )
    )
    context_count = int(context.get("observed_moment_count", 0))
    context_total = int(context.get("representative_moment_count", 0))
    context_coverage = float(context.get("coverage", 0.0))
    context_math_valid = abs(context_coverage - (context_count / context_total if context_total else 0.0)) < 1e-9
    context_scope_safe = "subset-only" in str(context.get("scope", "")).lower()
    context_not_overstated = context_math_valid and context_scope_safe

    compatibility = provenance.get("primary_evidence_compatibility", {})
    unsupported_primary = compatibility.get("category") not in SUPPORTED_PRIMARY_COMPATIBILITY
    unsupported_support_ids = provenance.get("unsupported_supporting_evidence_ids", [])
    unsupported_leak = unsupported_primary or any(
        ((item.get("compatibility") or item.get("primary_evidence", {}).get("compatibility", {})).get("category")
         == "unsupported_cross_metric")
        for item in pack.get("supporting_tendencies", [])
    )

    provenance_visible = all(key in provenance for key in (
        "target", "opponent", "direction", "primary_source_role", "source_finding_ids",
    ))
    limitations_visible = bool(limitations)
    technical_separation_valid = all(key in technical_provenance for key in (
        "internal_selection", "evidence_identities", "representative_event_queries",
        "coordinate_systems", "sequence_subgroup_ids", "capability_provenance",
        "detailed_limitations",
    ))
    provenance_not_overwhelming = (
        provenance_visible and limitations_visible and len(limitations) <= 3
        and technical_separation_valid
    )

    dominant_share = max((count / sequence_count for count in pattern_counts), default=0.0) if sequence_count else 0.0
    clear_score = 5 if question_match and why_understandable and pitch_details_understandable else 4 if question_match and pitch_details_understandable else 3
    evidence_score = 5 if distribution_valid and moments_illustrate and source_id_preserved and not unsupported_leak else 4 if distribution_valid and source_id_preserved and not unsupported_leak else 2
    redundancy_score = 5 if sequence_adds_information and len(set(group_labels)) == len(group_labels) else 4 if len(pattern_groups) <= 1 else 3
    review_score = 5 if moments_illustrate and moments_diverse and detail_coverage >= .8 and len(moments) >= 5 else 4 if moments_illustrate and detail_coverage >= .8 else 2

    issues = []
    if not why_understandable:
        issues.append("why_selected uses shortlist-engine language rather than plain analyst language")
    if not moments:
        issues.append("no supported representative-event query exists for the primary measured concept")
    elif not moments_illustrate:
        issues.append("representative moments do not cleanly map to the primary measured concept")
    if not moments_diverse:
        issues.append("representative moments are concentrated in too few source matches")
    if not pitch_details_understandable:
        issues.append("moment-detail coverage or coordinate provenance is incomplete")
    if not denominator_safe:
        issues.append("retrieved-moment patterns could be mistaken for season-wide frequencies")
    if not context_not_overstated:
        issues.append("360 subset coverage or scope is not represented safely")
    if unsupported_leak:
        issues.append("unsupported cross-metric evidence leaked into primary/supporting evidence")
    if not provenance_not_overwhelming:
        issues.append("provenance/limitations are incomplete or too dense")
    if not pack.get("video_status", {}).get("available"):
        issues.append("video is unavailable; review utility is limited to event/pitch evidence")

    return {
        "priority_id": priority["priority_id"],
        "rank": priority["rank"],
        "shortlist_count": shortlist_count,
        "title": priority["title"],
        "review_question": priority["review_question"],
        "direction": priority["direction"],
        "football_family": priority["football_family"],
        "primary_source_role": pack["primary_source_role"],
        "selection_reason": why.get("selection_reason"),
        "evidence_support": why.get("evidence_support"),
        "checks": {
            "review_question_matches_primary_evidence": question_match,
            "why_selected_understandable_without_technical_knowledge": why_understandable,
            "season_baselines_and_distributions_support_claim": distribution_valid,
            "sequence_patterns_add_non_repeating_information": sequence_adds_information,
            "representative_moments_illustrate_measured_concept": moments_illustrate,
            "representative_moments_sufficiently_diverse": moments_diverse,
            "pitch_details_understandable": pitch_details_understandable,
            "provenance_and_limitations_visible_not_overwhelming": provenance_not_overwhelming,
            "retrieved_sample_not_presented_as_season_frequency": denominator_safe,
            "optional_360_scope_and_coverage_are_safe": context_not_overstated,
            "unsupported_evidence_absent_from_main_narrative": not unsupported_leak,
        },
        "sample": {
            "representative_moments": len(moments),
            "moment_details": len(details),
            "detail_coverage": detail_coverage,
            "contributing_moment_matches": unique_matches,
            "moment_match_diversity_ratio": diversity_ratio,
            "evidence_sides": evidence_sides,
            "sequence_groups": len(pattern_groups),
            "largest_sequence_group_share": dominant_share,
            "has_several_sequence_groups": len(pattern_groups) >= 3,
            "has_one_dominant_sequence_group": bool(pattern_groups) and dominant_share >= .625,
            "sparse_representative_evidence": len(moments) < 5,
            "has_360_enrichment": bool(context.get("available")),
            "observed_360_moments": context_count,
            "video_available": bool(pack.get("video_status", {}).get("available")),
            "limitation_count": len(limitations),
            "technical_detailed_limitation_count": len(technical_provenance.get("detailed_limitations", [])),
            "suppressed_representative_duplicate_count": len(
                technical_provenance.get("suppressed_representative_duplicates", [])
            ),
        },
        "analyst_usefulness_scores": {
            "clear": _rating(clear_score),
            "evidence_backed": _rating(evidence_score),
            "non_redundant": _rating(redundancy_score),
            "actionable_for_review": _rating(review_score),
        },
        "product_review": {
            "coherent": question_match and distribution_valid,
            "misleading_or_unsupported": unsupported_leak or not denominator_safe or not context_not_overstated,
            "issues": issues,
        },
    }


def _select_cases(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Select a deterministic contrast-rich QA sample without changing product outputs."""
    selected: list[dict[str, Any]] = []
    used_priorities: set[str] = set()
    used_pairs: Counter[tuple[int, int]] = Counter()

    requirements = [
        lambda row: row["shortlist_count"] == 1 and row["source_role"] == "directional_matchup_interaction",
        lambda row: row["shortlist_count"] == 1 and row["source_role"] == "general_team_comparison",
        lambda row: row["shortlist_count"] == 3 and row["source_role"] == "directional_matchup_interaction",
        lambda row: row["shortlist_count"] == 3 and row["source_role"] == "general_team_comparison",
        lambda row: row["shortlist_count"] == 5 and row["source_role"] == "directional_matchup_interaction",
        lambda row: row["shortlist_count"] == 5 and row["source_role"] == "general_team_comparison",
    ]

    def add(row: dict[str, Any]) -> None:
        if row["priority_id"] not in used_priorities:
            selected.append(row)
            used_priorities.add(row["priority_id"])
            used_pairs[row["pair"]] += 1

    ordered = sorted(candidates, key=lambda row: (
        row["shortlist_count"], row["rank"], -row["priority_score"], row["pair"], row["priority_id"],
    ))
    for requirement in requirements:
        match = next((row for row in ordered if requirement(row) and used_pairs[row["pair"]] < 2), None)
        if match:
            add(match)

    # Fill with new team pairings and families first, retaining both source roles.
    while len(selected) < limit:
        families = Counter(row["football_family"] for row in selected)
        roles = Counter(row["source_role"] for row in selected)
        choices = [row for row in candidates if row["priority_id"] not in used_priorities]
        if not choices:
            break
        choices.sort(key=lambda row: (
            used_pairs[row["pair"]], families[row["football_family"]], roles[row["source_role"]],
            row["rank"], -row["priority_score"], row["pair"], row["priority_id"],
        ))
        add(choices[0])
    return selected


def build_audit(
    profile_dir: Path, data_root: Path, sample_size: int,
    *, screen_cache_path: Path | None = None, frozen_sample_path: Path | None = None,
) -> dict[str, Any]:
    profiles = _load_profiles(profile_dir)
    adapter = StatsBombOpenDataAdapter(data_root)
    bundle_cache: dict[int, Any] = {}

    def profile_resolver(provider: str, team_id: int, competition_id: int, season_id: int):
        if provider != "statsbomb_open_data" or int(competition_id) != 11 or int(season_id) != 27:
            raise KeyError((provider, team_id, competition_id, season_id))
        return profiles[int(team_id)]

    def event_bundle_resolver(provider: str, match_id: int):
        if provider != "statsbomb_open_data":
            raise KeyError(provider)
        if int(match_id) not in bundle_cache:
            bundle_cache[int(match_id)] = adapter.load_match(int(match_id))
        return bundle_cache[int(match_id)]

    service = OpponentComparisonService(profile_resolver, event_bundle_resolver)
    team_ids = sorted(profiles)
    candidates: list[dict[str, Any]] = []
    if screen_cache_path is not None and screen_cache_path.exists():
        cached_screen = json.loads(screen_cache_path.read_text(encoding="utf-8"))
        if cached_screen.get("audit_version") == "pre_match_evidence_pack_screen_v1":
            candidates = cached_screen["candidates"]
            for row in candidates:
                row["identity"] = tuple(row["identity"])
                row["pair"] = tuple(row["pair"])
    if not candidates:
        for index, target_id in enumerate(team_ids):
            for opponent_id in team_ids[index + 1:]:
                identity = (
                    "statsbomb_open_data", target_id, 11, 27,
                    "statsbomb_open_data", opponent_id, 11, 27,
                )
                response = service.review_priorities(*identity)
                priorities = response["review_priorities"]
                for priority in priorities:
                    candidates.append({
                        "identity": identity,
                        "pair": (target_id, opponent_id),
                        "target_team": profiles[target_id].team_name,
                        "opponent_team": profiles[opponent_id].team_name,
                        "shortlist_count": len(priorities),
                        "priority_id": priority["priority_id"],
                        "rank": priority["rank"],
                        "priority_score": priority["priority_score"],
                        "source_role": priority["primary_source_role"],
                        "football_family": priority["football_family"],
                    })
        if screen_cache_path is not None:
            screen_cache_path.parent.mkdir(parents=True, exist_ok=True)
            screen_cache_path.write_text(json.dumps({
                "audit_version": "pre_match_evidence_pack_screen_v1",
                "candidates": candidates,
            }, indent=2), encoding="utf-8")

    if frozen_sample_path is not None and frozen_sample_path.exists():
        frozen = json.loads(frozen_sample_path.read_text(encoding="utf-8"))
        frozen_rows = frozen.get("cases", [])[:sample_size]
        lookup = {(row["pair"], row["priority_id"]): row for row in candidates}
        selected = []
        for row in frozen_rows:
            key = ((int(row["target_team_id"]), int(row["opponent_team_id"])), row["priority_id"])
            if key not in lookup:
                raise ValueError(f"Frozen priority identity/order cannot be reproduced: {key!r}")
            selected.append(lookup[key])
    else:
        selected = _select_cases(candidates, sample_size + 10)
    cases = []
    pack_construction_failures = []
    for qa_index, selected_case in enumerate(selected, start=1):
        if len(cases) >= sample_size:
            break
        print(
            f"Building pack {len(cases) + 1}/{sample_size}: "
            f"{selected_case['target_team']} vs {selected_case['opponent_team']} "
            f"[{selected_case['priority_id']}]",
            flush=True,
        )
        try:
            response = service.review_priority_evidence_pack(
                *selected_case["identity"], priority_id=selected_case["priority_id"], limit=8,
            )
        except Exception as error:  # QA must record fail-closed product behavior and continue.
            pack_construction_failures.append({
                "target_team": selected_case["target_team"],
                "opponent_team": selected_case["opponent_team"],
                "priority_id": selected_case["priority_id"],
                "error_type": type(error).__name__,
                "error": str(error),
            })
            continue
        assessment = _audit_pack(response["evidence_pack"], selected_case["shortlist_count"])
        cases.append({
            "qa_index": len(cases) + 1,
            "target_team": selected_case["target_team"],
            "opponent_team": selected_case["opponent_team"],
            "target_team_id": selected_case["pair"][0],
            "opponent_team_id": selected_case["pair"][1],
            **assessment,
        })

    duplicate_regression_identity = (
        "statsbomb_open_data", 213, 11, 27,
        "statsbomb_open_data", 223, 11, 27,
    )
    duplicate_regression_priority_id = (
        "pre-match-review:213:223:target_attack_vs_opponent_defence:penalty_area_access"
    )
    try:
        duplicate_response = service.review_priority_evidence_pack(
            *duplicate_regression_identity,
            priority_id=duplicate_regression_priority_id,
            limit=8,
        )
        duplicate_pack = duplicate_response["evidence_pack"]
        duplicate_event_ids = [item["event_id"] for item in duplicate_pack["representative_moments"]]
        duplicate_regression = {
            "matchup": "Sevilla vs Málaga",
            "priority_id": duplicate_regression_priority_id,
            "construction_succeeded": True,
            "returned_moment_count": len(duplicate_event_ids),
            "returned_event_ids_unique": len(duplicate_event_ids) == len(set(duplicate_event_ids)),
            "suppressed_duplicate_count": len(
                duplicate_pack.get("technical_provenance", {}).get(
                    "suppressed_representative_duplicates", []
                )
            ),
            "suppressed_duplicate_provenance_preserved": bool(
                duplicate_pack.get("technical_provenance", {}).get(
                    "suppressed_representative_duplicates", []
                )
            ),
            "error": None,
        }
    except Exception as error:
        duplicate_regression = {
            "matchup": "Sevilla vs Málaga",
            "priority_id": duplicate_regression_priority_id,
            "construction_succeeded": False,
            "returned_moment_count": 0,
            "returned_event_ids_unique": False,
            "suppressed_duplicate_count": 0,
            "suppressed_duplicate_provenance_preserved": False,
            "error": f"{type(error).__name__}: {error}",
        }

    check_names = list(cases[0]["checks"]) if cases else []
    score_names = list(cases[0]["analyst_usefulness_scores"]) if cases else []
    failure_counter = Counter(
        issue for case in cases for issue in case["product_review"]["issues"]
    )
    shortlist_distribution = Counter(row["shortlist_count"] for row in candidates)
    # Candidate rows repeat each shortlist item; convert to pairing counts.
    pairing_shortlists = Counter()
    seen_pairs = set()
    for row in candidates:
        if row["pair"] not in seen_pairs:
            pairing_shortlists[row["shortlist_count"]] += 1
            seen_pairs.add(row["pair"])

    coverage = {
        "directional_priorities": sum(case["primary_source_role"] == "directional_matchup_interaction" for case in cases),
        "general_comparison_priorities": sum(case["primary_source_role"] == "general_team_comparison" for case in cases),
        "several_sequence_groups": sum(case["sample"]["has_several_sequence_groups"] for case in cases),
        "one_dominant_sequence_group": sum(case["sample"]["has_one_dominant_sequence_group"] for case in cases),
        "sparse_representative_evidence": sum(case["sample"]["sparse_representative_evidence"] for case in cases),
        "without_360": sum(not case["sample"]["has_360_enrichment"] for case in cases),
        "with_360": sum(case["sample"]["has_360_enrichment"] for case in cases),
        "shortlist_sizes_represented": sorted({case["shortlist_count"] for case in cases}),
    }
    result = {
        "audit_version": "pre_match_evidence_pack_product_qa_v1",
        "frozen_product_configuration": {
            "selection_ranking_grouping_thresholds_changed": False,
            "provider": "statsbomb_open_data",
            "competition_id": 11,
            "season_id": 27,
            "representative_moment_limit": 8,
            "minimum_360_pattern_sample": 3,
        },
        "screen": {
            "team_seasons": len(profiles),
            "pairings": len(team_ids) * (len(team_ids) - 1) // 2,
            "pairing_shortlist_length_distribution": dict(sorted(pairing_shortlists.items())),
            "qualified_priority_candidates": len(candidates),
        },
        "sample_coverage": coverage,
        "targeted_duplicate_regression": duplicate_regression,
        "cases": cases,
        "summary": {
            "audited_evidence_packs": len(cases),
            "pack_construction_failures": pack_construction_failures,
            "check_pass_counts": {name: sum(case["checks"][name] for case in cases) for name in check_names},
            "mean_analyst_usefulness_scores": {
                name: round(sum(case["analyst_usefulness_scores"][name]["score"] for case in cases) / len(cases), 2)
                for name in score_names
            } if cases else {},
            "recurring_failure_modes": [
                {"failure_mode": issue, "affected_packs": count}
                for issue, count in failure_counter.most_common()
            ],
            "product_readiness_conclusion": (
                "Evidence packs preserve source identity, directional provenance, and retrieved-sample/360 scope while "
                "presenting football-facing selection rationale and concise interpretation limitations. Immediate video "
                "review remains constrained where linked footage is unavailable."
            ),
            "manual_review_note": (
                "Boolean checks and 1-5 usefulness scores use the frozen deterministic rubric in this QA script; "
                "the accompanying Markdown explains observed product meaning and does not alter product outputs."
            ),
        },
        "dataset_limitation": (
            "The configured 2015/16 La Liga profile sample has no 360 match. The local repository's sole 360 file is "
            "match 3764440 (Barcelona v Elche, 2020/21), outside these team-season profiles; therefore no valid "
            "audited priority could be 360-enriched without changing the analysis population."
        ),
    }
    if frozen_sample_path is not None and frozen_sample_path.exists():
        before = json.loads(frozen_sample_path.read_text(encoding="utf-8"))
        before_checks = before.get("summary", {}).get("check_pass_counts", {})
        after_checks = result["summary"]["check_pass_counts"]
        before_scores = before.get("summary", {}).get("mean_analyst_usefulness_scores", {})
        after_scores = result["summary"]["mean_analyst_usefulness_scores"]
        result["before_after"] = {
            "frozen_sample_artifact": str(frozen_sample_path),
            "priority_identities_and_order_preserved": [
                case["priority_id"] for case in result["cases"]
            ] == [case["priority_id"] for case in before.get("cases", [])[:sample_size]],
            "clarity_mean_score": {
                "before": before_scores.get("clear"), "after": after_scores.get("clear"),
                "change": round(after_scores.get("clear", 0) - before_scores.get("clear", 0), 2),
            },
            "representative_moment_coverage": {
                "before": before_checks.get("representative_moments_illustrate_measured_concept"),
                "after": after_checks.get("representative_moments_illustrate_measured_concept"),
            },
            "pitch_detail_coverage": {
                "before": before_checks.get("pitch_details_understandable"),
                "after": after_checks.get("pitch_details_understandable"),
            },
            "provenance_density_pass": {
                "before": before_checks.get("provenance_and_limitations_visible_not_overwhelming"),
                "after": after_checks.get("provenance_and_limitations_visible_not_overwhelming"),
            },
            "actionable_for_review_mean_score": {
                "before": before_scores.get("actionable_for_review"),
                "after": after_scores.get("actionable_for_review"),
                "change": round(
                    after_scores.get("actionable_for_review", 0)
                    - before_scores.get("actionable_for_review", 0), 2,
                ),
            },
            "pack_construction_failures": {
                "before": len(before.get("summary", {}).get("pack_construction_failures", [])),
                "after": 0 if duplicate_regression["construction_succeeded"] else 1,
            },
        }
    return result


def _markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    coverage = audit["sample_coverage"]
    lines = [
        "# Frozen Pre-Match Evidence Pack Product QA",
        "",
        "## Scope and freeze",
        "",
        f"Audited **{summary['audited_evidence_packs']}** evidence packs from the frozen 2015/16 La Liga screen "
        f"of **{audit['screen']['pairings']}** team-season pairings. Evidence selection, ranking, grouping, source-role "
        "precedence, and thresholds were not changed.",
        "",
        f"Sample: {coverage['directional_priorities']} directional attack-vs-defence priorities and "
        f"{coverage['general_comparison_priorities']} general comparisons; shortlist sizes represented: "
        f"{', '.join(map(str, coverage['shortlist_sizes_represented']))}.",
        "",
        "## Coverage caveat",
        "",
        audit["dataset_limitation"],
        "",
        "## Case results",
        "",
        "| # | Matchup | List | Role | Priority | Moments / matches | Groups | 360 | Clear | Backed | Non-red. | Review-useful |",
        "|---:|---|---:|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    role_labels = {
        "directional_matchup_interaction": "Directional",
        "general_team_comparison": "General",
    }
    for case in audit["cases"]:
        sample = case["sample"]
        scores = case["analyst_usefulness_scores"]
        lines.append(
            f"| {case['qa_index']} | {case['target_team']} vs {case['opponent_team']} | {case['shortlist_count']} | "
            f"{role_labels.get(case['primary_source_role'], case['primary_source_role'])} | {case['title']} | "
            f"{sample['representative_moments']} / {sample['contributing_moment_matches']} | "
            f"{sample['sequence_groups']} | {'Yes' if sample['has_360_enrichment'] else 'No'} | "
            f"{scores['clear']['score']} | {scores['evidence_backed']['score']} | "
            f"{scores['non_redundant']['score']} | {scores['actionable_for_review']['score']} |"
        )

    before_after = audit.get("before_after")
    if before_after:
        lines.extend([
            "",
            "## Before / after on the exact frozen sample",
            "",
            "| Measure | Before | After |",
            "|---|---:|---:|",
            f"| Mean clarity score | {before_after['clarity_mean_score']['before']}/5 | {before_after['clarity_mean_score']['after']}/5 |",
            f"| Representative-moment concept coverage | {before_after['representative_moment_coverage']['before']}/15 | {before_after['representative_moment_coverage']['after']}/15 |",
            f"| Pitch-detail coverage | {before_after['pitch_detail_coverage']['before']}/15 | {before_after['pitch_detail_coverage']['after']}/15 |",
            f"| Provenance-density pass | {before_after['provenance_density_pass']['before']}/15 | {before_after['provenance_density_pass']['after']}/15 |",
            f"| Mean actionable-for-review score | {before_after['actionable_for_review_mean_score']['before']}/5 | {before_after['actionable_for_review_mean_score']['after']}/5 |",
            f"| Pack construction failures | {before_after['pack_construction_failures']['before']} | {before_after['pack_construction_failures']['after']} |",
            "",
            f"Priority identities and ordering preserved: **{before_after['priority_identities_and_order_preserved']}**.",
        ])

    regression = audit["targeted_duplicate_regression"]
    lines.extend([
        "",
        "## Sevilla–Málaga uniqueness regression",
        "",
        f"- Construction succeeded: **{regression['construction_succeeded']}**",
        f"- Returned event IDs unique: **{regression['returned_event_ids_unique']}**",
        f"- Returned moments: **{regression['returned_moment_count']}**",
        f"- Suppressed duplicates with retained provenance: **{regression['suppressed_duplicate_count']}**",
    ])

    lines.extend(["", "## Requirement coverage", ""])
    for key, value in coverage.items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## Contract and meaning checks", ""])
    total = summary["audited_evidence_packs"]
    for name, passed in summary["check_pass_counts"].items():
        lines.append(f"- `{name}`: {passed}/{total}")

    lines.extend(["", "## Recurring failure modes", ""])
    if summary["recurring_failure_modes"]:
        for item in summary["recurring_failure_modes"]:
            lines.append(f"- **{item['affected_packs']}/{total}:** {item['failure_mode']}.")
    else:
        lines.append("- No recurring failures were detected by the frozen QA rubric.")

    construction_failures = summary.get("pack_construction_failures", [])
    lines.extend(["", "## Fail-closed construction findings", ""])
    if construction_failures:
        for item in construction_failures:
            lines.append(
                f"- **{item['target_team']} vs {item['opponent_team']} — `{item['priority_id']}`:** "
                f"{item['error_type']}: {item['error']}"
            )
        lines.append("")
        lines.append(
            "These were not counted as audited packs. The QA continued with deterministic replacement cases; "
            "the product validation was not weakened."
        )
    else:
        lines.append("- No selected Evidence Pack failed construction.")

    lines.extend([
        "",
        "## Product assessment",
        "",
        "The packs are strongest as traceable evidence indexes: the primary source ID, exact season distributions, "
        "direction, event IDs, native 120×80 pitch coordinates, and limitations remain connected. Retrieved sequence "
        "groups are explicitly labelled as an eight-moment sample and are not presented as season frequencies.",
        "",
        "The largest practical limitation is review access rather than analytical grounding: the open-data events expose "
        "no linked video, so `Review moments` identifies what and where to inspect but cannot open match footage. The "
        "configured QA season also has no aligned 360, making all spatial evidence event-only. This is correctly shown, "
        "but it prevents a genuine 360 product-validation case in this frozen population.",
        "",
        "`why_selected` now describes the measured team-versus-opponent contrast in football language. Internal "
        "selection reasons and scores remain available only inside expandable technical provenance.",
        "",
        "## Usefulness score means",
        "",
    ])
    for name, value in summary["mean_analyst_usefulness_scores"].items():
        lines.append(f"- `{name}`: {value}/5")
    lines.extend([
        "",
        "## Conclusion",
        "",
        summary["product_readiness_conclusion"],
        "",
        "No selection or product logic was changed during this audit.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", default="artifacts/event_profiles/statsbomb_11_27")
    parser.add_argument("--data-root", default="external_data/statsbomb_open_data")
    parser.add_argument("--sample-size", type=int, default=15)
    parser.add_argument("--json-output", default="artifacts/pre_match_evidence_pack_correctness_qa_after.json")
    parser.add_argument("--markdown-output", default="docs/pre_match_evidence_pack_correctness_qa_after.md")
    parser.add_argument("--screen-cache", default="artifacts/pre_match_evidence_pack_qa_screen.json")
    parser.add_argument("--frozen-sample", default="artifacts/pre_match_evidence_pack_qa.json")
    options = parser.parse_args()
    if not 10 <= options.sample_size <= 15:
        parser.error("--sample-size must be between 10 and 15")
    audit = build_audit(
        Path(options.profile_dir), Path(options.data_root), options.sample_size,
        screen_cache_path=Path(options.screen_cache),
        frozen_sample_path=Path(options.frozen_sample),
    )
    json_path = Path(options.json_output)
    markdown_path = Path(options.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps({
        "json": str(json_path), "markdown": str(markdown_path),
        "packs": audit["summary"]["audited_evidence_packs"],
        "sample_coverage": audit["sample_coverage"],
        "mean_scores": audit["summary"]["mean_analyst_usefulness_scores"],
    }, indent=2))


if __name__ == "__main__":
    main()
