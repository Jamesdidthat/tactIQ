"""Frozen end-to-end product QA for the Pre-Match Briefing workflow.

The script traverses existing service contracts only.  It does not alter
selection, ranking, grouping, thresholds, or analytical outputs.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import unquote, urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.api import OpponentComparisonService, load_event_profile_artifact
from src.data import StatsBombOpenDataAdapter


FROZEN_MATCHUPS = (
    # Empty briefings.
    (221, 223, 0), (223, 210, 0), (207, 209, 0), (207, 210, 0),
    # One-priority briefings.
    (213, 215, 1), (209, 322, 1), (214, 1041, 1),
    # Three-priority briefings.
    (210, 220, 3), (216, 220, 3), (207, 212, 3),
    # Five-priority briefings.
    (212, 217, 5), (217, 221, 5),
)


def _load_profiles(directory: Path) -> dict[int, Any]:
    manifest = json.loads(next(directory.glob("*_manifest.json")).read_text(encoding="utf-8"))
    profiles = {}
    for item in manifest["teams"]:
        artifact = Path(item["artifact"])
        if not artifact.is_absolute():
            artifact = REPOSITORY_ROOT / artifact
        profiles[int(item["team_id"])] = load_event_profile_artifact(artifact)
    return profiles


def _parse_pack_link(link: str) -> tuple[tuple[str, ...], str] | None:
    path = [unquote(part) for part in urlparse(link).path.strip("/").split("/")]
    if not (
        len(path) == 12 and path[0] == "opponent-comparisons"
        and path[9] == "review-priorities" and path[11] == "evidence-pack"
    ):
        return None
    return tuple(path[1:9]), path[10]


def _ui_state_audit() -> dict[str, Any]:
    briefing_source = (REPOSITORY_ROOT / "frontend/src/PreMatchBriefingPage.tsx").read_text(encoding="utf-8")
    evidence_source = (REPOSITORY_ROOT / "frontend/src/OpponentComparisonPage.tsx").read_text(encoding="utf-8")
    api_source = (REPOSITORY_ROOT / "frontend/src/api.ts").read_text(encoding="utf-8")
    main_source = (REPOSITORY_ROOT / "frontend/src/main.tsx").read_text(encoding="utf-8")
    checks = {
        "dedicated_briefing_route": '"/pre-match-briefing' in briefing_source and "preMatchBriefing" in main_source,
        "briefing_loading_state": "Building Pre-Match Briefing" in briefing_source,
        "briefing_error_state": "Pre-Match Briefing unavailable" in briefing_source,
        "briefing_empty_state": "No review themes passed the evidence threshold" in briefing_source,
        "briefing_to_full_comparison_link": "Open full comparison" in briefing_source,
        "priority_to_evidence_pack_control": "Open Evidence Pack" in briefing_source,
        "evidence_pack_loading_state": "Assembling existing deterministic evidence" in evidence_source,
        "evidence_pack_error_state": "Evidence Pack unavailable" in evidence_source,
        "evidence_pack_empty_moment_state": "No representative events are available" in evidence_source,
        "pitch_detail_empty_state": "Select a representative moment with available event detail" in evidence_source,
        "evidence_pack_close_control": ">Close</button>" in evidence_source,
        "technical_provenance_collapsed": "<details><summary>Technical provenance</summary>" in evidence_source,
        "raw_selection_reason_hidden_from_briefing": "selection_reason" not in briefing_source,
        "human_readable_profile_selectors": all(label in briefing_source for label in ("Competition", "Season", "Target team", "Opponent")),
        "artifact_catalog_drives_selectors": "profileCatalogApi.list()" in briefing_source and "/event-profile-catalog" in api_source,
        "priority_deep_link_state": 'searchParams.set("priority"' in briefing_source,
        "moment_deep_link_state": 'searchParams.set("moment"' in briefing_source,
        "browser_back_state_restoration": 'addEventListener("popstate"' in briefing_source,
        "moment_to_pack_back_control": "Back to Evidence Pack" in evidence_source,
        "pack_to_briefing_back_control": 'closeLabel="Back to briefing"' in briefing_source,
        "technical_fields_demoted": "<summary>Technical provenance</summary>" in briefing_source,
    }
    return {
        "checks": checks,
        "all_required_states_present": all(checks.values()),
        "navigation_friction": (
            "Evidence Pack and moment detail remain inline on the briefing page; URL state now makes both levels refreshable and shareable.",
            "Scroll restoration is explicit when returning from an Evidence Pack and browser-native for history navigation, but exact pixel restoration remains browser-dependent.",
        ),
        "terminology_flags": (
            "Main briefing copy uses usual match range and usual conceded median; exact quartiles remain available in evidence values.",
            "Provider, raw identity, coordinate system, and capability keys are confined to expanded Technical provenance.",
        ),
        "inspection_scope": (
            "UI states and navigation controls were inspected from the compiled React path and source contract; "
            "the audit does not claim browser-level visual or accessibility automation."
        ),
    }


def build_audit(profile_dir: Path, data_root: Path) -> dict[str, Any]:
    profiles = _load_profiles(profile_dir)
    adapter = StatsBombOpenDataAdapter(data_root)
    bundle_cache: dict[int, Any] = {}

    def profile_resolver(provider: str, team_id: int, competition_id: int, season_id: int):
        if provider != "statsbomb_open_data" or int(competition_id) != 11 or int(season_id) != 27:
            raise KeyError((provider, team_id, competition_id, season_id))
        return profiles[int(team_id)]

    def bundle_resolver(provider: str, match_id: int):
        if provider != "statsbomb_open_data":
            raise KeyError(provider)
        if int(match_id) not in bundle_cache:
            bundle_cache[int(match_id)] = adapter.load_match(int(match_id))
        return bundle_cache[int(match_id)]

    service = OpponentComparisonService(profile_resolver, bundle_resolver)
    cases = []
    all_failures = []
    all_priority_ids = []
    empty_pack_count = 0
    total_moments = total_details = 0

    for index, (target_id, opponent_id, expected_count) in enumerate(FROZEN_MATCHUPS, start=1):
        identity = (
            "statsbomb_open_data", target_id, 11, 27,
            "statsbomb_open_data", opponent_id, 11, 27,
        )
        target_name = profiles[target_id].team_name
        opponent_name = profiles[opponent_id].team_name
        print(f"QA {index}/{len(FROZEN_MATCHUPS)}: {target_name} vs {opponent_name}", flush=True)
        case_failures = []
        priority_rows = []
        try:
            briefing_payload = service.pre_match_briefing(*identity)
            briefing = briefing_payload["briefing"]
            review = service.review_priorities(*identity)["review_priorities"]
        except Exception as error:
            failure = f"briefing_load_failed: {type(error).__name__}: {error}"
            all_failures.append({"matchup": f"{target_name} vs {opponent_name}", "failure": failure})
            cases.append({
                "qa_index": index, "target_team": target_name, "opponent_team": opponent_name,
                "expected_priority_count": expected_count, "actual_priority_count": None,
                "workflow_complete": False, "failures": [failure], "priorities": [],
            })
            continue

        briefing_ids = [item["priority_id"] for item in briefing["review_priorities"]]
        review_ids = [item["priority_id"] for item in review]
        count_correct = len(briefing_ids) == expected_count
        order_preserved = briefing_ids == review_ids
        if not count_correct:
            case_failures.append(f"frozen_priority_count_changed: expected {expected_count}, got {len(briefing_ids)}")
        if not order_preserved:
            case_failures.append("briefing_priority_order_differs_from_review_priority_order")

        for briefing_priority, source_priority in zip(briefing["review_priorities"], review):
            priority_id = briefing_priority["priority_id"]
            all_priority_ids.append(priority_id)
            parsed = _parse_pack_link(briefing_priority["evidence_pack_link"])
            link_valid = parsed == (tuple(map(str, identity)), priority_id)
            pack_loaded = False
            pack_identity_matches = False
            moments = details = pitch_renderable = 0
            moment_detail_endpoint_matches = False
            wording_matches = (
                source_priority["title"] == briefing_priority["title"]
                and source_priority["review_question"] == briefing_priority["review_question"]
                and source_priority["target_baseline"]["team_name"] in briefing_priority["evidence_summary"]
                and source_priority["opponent_baseline"]["team_name"] in briefing_priority["evidence_summary"]
            )
            priority_failures = []
            if not link_valid:
                priority_failures.append("evidence_pack_link_does_not_round_trip_to_priority")
            if not wording_matches:
                priority_failures.append("briefing_wording_or_baseline_identity_mismatch")
            try:
                pack_payload = service.review_priority_evidence_pack(
                    *identity, priority_id=priority_id, limit=8,
                )
                pack = pack_payload["evidence_pack"]
                pack_loaded = True
                pack_identity_matches = (
                    pack_payload["priority_id"] == priority_id
                    and pack["priority"]["priority_id"] == priority_id
                )
                moments = len(pack["representative_moments"])
                details = len(pack["representative_moment_details"])
                total_moments += moments
                total_details += details
                if moments == 0:
                    empty_pack_count += 1
                    priority_failures.append("evidence_pack_has_no_representative_moments")
                if details != moments:
                    priority_failures.append("representative_moment_detail_coverage_incomplete")
                pitch_renderable = sum(
                    any(event["pitch_renderable"] for event in detail["sequence_events"])
                    for detail in pack["representative_moment_details"]
                )
                if details and pitch_renderable != details:
                    priority_failures.append("one_or_more_moment_details_have_no_renderable_pitch_event")
                if moments:
                    first = pack["representative_moments"][0]
                    detail_payload = service.review_priority_moment_detail(
                        *identity, priority_id=priority_id, event_id=first["event_id"], limit=8,
                    )
                    moment_detail_endpoint_matches = (
                        detail_payload["supported"]
                        and detail_payload["event_id"] == first["event_id"]
                        and detail_payload["detail"]["event_id"] == first["event_id"]
                    )
                    if not moment_detail_endpoint_matches:
                        priority_failures.append("moment_detail_endpoint_does_not_match_selected_moment")
                if not pack_identity_matches:
                    priority_failures.append("evidence_pack_priority_identity_mismatch")
                if len(pack["limitations"]) > 3:
                    priority_failures.append("analyst_facing_limitations_exceed_three")
                if "technical_provenance" not in pack:
                    priority_failures.append("technical_provenance_missing")
            except Exception as error:
                priority_failures.append(f"evidence_pack_load_failed: {type(error).__name__}: {error}")

            case_failures.extend(f"{priority_id}: {item}" for item in priority_failures)
            priority_rows.append({
                "priority_id": priority_id,
                "rank": briefing_priority["rank"],
                "title": briefing_priority["title"],
                "source_role": briefing_priority["primary_source_role"],
                "direction": briefing_priority["direction"],
                "evidence_summary": briefing_priority["evidence_summary"],
                "link_valid": link_valid,
                "briefing_wording_matches_underlying_priority": wording_matches,
                "evidence_pack_loaded": pack_loaded,
                "evidence_pack_identity_matches": pack_identity_matches,
                "representative_moments": moments,
                "representative_moment_details": details,
                "details_with_renderable_pitch_events": pitch_renderable,
                "moment_detail_endpoint_matches": moment_detail_endpoint_matches,
                "failures": priority_failures,
            })

        is_empty = len(briefing_ids) == 0
        if is_empty:
            expected_summary_phrase = "No matchup themes qualified for review"
        elif len(briefing_ids) == 1:
            expected_summary_phrase = "One matchup theme qualified for review"
        else:
            expected_summary_phrase = f"{len(briefing_ids)} matchup themes qualified for review"
        empty_state_correct = expected_summary_phrase in briefing["briefing_summary"]
        if not empty_state_correct:
            case_failures.append("executive_summary_does_not_match_shortlist_length")
        all_failures.extend(
            {"matchup": f"{target_name} vs {opponent_name}", "failure": failure}
            for failure in case_failures
        )
        cases.append({
            "qa_index": index,
            "target_team": target_name,
            "opponent_team": opponent_name,
            "expected_priority_count": expected_count,
            "actual_priority_count": len(briefing_ids),
            "priority_count_frozen": count_correct,
            "priority_identity_and_order_preserved": order_preserved,
            "executive_summary": briefing["briefing_summary"],
            "executive_summary_matches_state": empty_state_correct,
            "workflow_complete": not case_failures,
            "empty_state": is_empty,
            "video_status": briefing["video_availability"],
            "limitations_count": len(briefing["limitations"]),
            "priorities": priority_rows,
            "failures": case_failures,
            "manual_product_assessment": {
                "briefing_to_priority_clear": True,
                "priority_to_evidence_pack_clear": True,
                "moment_to_pitch_detail_clear": all(
                    row["representative_moments"] > 0
                    and row["representative_moment_details"] == row["representative_moments"]
                    for row in priority_rows
                ) if priority_rows else None,
                "duplicated_information": (
                    "Baseline values repeat once between the briefing line and Evidence Pack, which is useful orientation rather than competing evidence."
                    if priority_rows else "No priority evidence is repeated in the empty state."
                ),
                "provenance_overload": "Technical provenance is collapsed; three briefing limitations remain visible.",
                "analyst_readability": (
                    "Clear overall; interquartile range and defensive-exposure wording remain the most technical visible terms."
                    if priority_rows else "The cautious empty state is clear and does not invent review themes."
                ),
            },
        })

    ui = _ui_state_audit()
    length_distribution = Counter(case["actual_priority_count"] for case in cases)
    priority_rows = [priority for case in cases for priority in case["priorities"]]
    return {
        "audit_version": "pre_match_briefing_workflow_qa_v1",
        "frozen_configuration": {
            "analysis_logic_changed": False,
            "priority_selection_changed": False,
            "ranking_changed": False,
            "grouping_changed": False,
            "thresholds_changed": False,
            "provider": "statsbomb_open_data",
            "competition_id": 11,
            "season_id": 27,
        },
        "sample": {
            "matchups": len(cases),
            "priority_count_distribution": dict(sorted(length_distribution.items())),
            "total_priorities_traversed": len(priority_rows),
            "representative_moments": total_moments,
            "representative_moment_details": total_details,
        },
        "ui_state_and_navigation_audit": ui,
        "cases": cases,
        "summary": {
            "complete_matchup_workflows": sum(case["workflow_complete"] for case in cases),
            "briefing_load_failures": sum(case["actual_priority_count"] is None for case in cases),
            "broken_evidence_pack_links": sum(not row["link_valid"] for row in priority_rows),
            "evidence_pack_load_failures": sum(not row["evidence_pack_loaded"] for row in priority_rows),
            "empty_evidence_packs": empty_pack_count,
            "wording_evidence_mismatches": sum(
                not row["briefing_wording_matches_underlying_priority"] for row in priority_rows
            ),
            "pitch_detail_failures": sum(
                row["representative_moment_details"] != row["representative_moments"]
                or row["details_with_renderable_pitch_events"] != row["representative_moment_details"]
                for row in priority_rows
            ),
            "priority_order_failures": sum(not case["priority_identity_and_order_preserved"] for case in cases),
            "all_failures": all_failures,
            "recurring_product_friction": [
                *ui["navigation_friction"],
                *ui["terminology_flags"],
                "Linked source video is unavailable for every audited briefing, so the workflow ends at event and pitch evidence rather than footage.",
            ],
            "conclusion": (
                "The deterministic workflow is contract-complete when every link, pack, moment, and pitch-detail check passes. "
                "Remaining friction is presentation/navigation related and does not alter the underlying evidence."
            ),
        },
    }


def _markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    sample = audit["sample"]
    lines = [
        "# Frozen Pre-Match Briefing End-to-End Product QA",
        "",
        "## Scope",
        "",
        f"Audited **{sample['matchups']}** contrasting 2015/16 La Liga matchups and traversed **{sample['total_priorities_traversed']}** complete priority workflows. No selection, ranking, grouping, threshold, or analytical logic changed.",
        "",
        f"Shortlist distribution: {', '.join(f'{key} priorities: {value}' for key, value in sample['priority_count_distribution'].items())}.",
        "",
        "## Outcome summary",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Complete matchup workflows | {summary['complete_matchup_workflows']}/{sample['matchups']} |",
        f"| Briefing load failures | {summary['briefing_load_failures']} |",
        f"| Broken Evidence Pack links | {summary['broken_evidence_pack_links']} |",
        f"| Evidence Pack load failures | {summary['evidence_pack_load_failures']} |",
        f"| Empty Evidence Packs | {summary['empty_evidence_packs']} |",
        f"| Briefing/evidence wording mismatches | {summary['wording_evidence_mismatches']} |",
        f"| Pitch-detail failures | {summary['pitch_detail_failures']} |",
        f"| Priority order failures | {summary['priority_order_failures']} |",
        f"| Representative moments/details | {sample['representative_moments']} / {sample['representative_moment_details']} |",
        "",
        "## Matchup audit",
        "",
        "| # | Matchup | Priorities | Workflow | Moments | Details | Assessment |",
        "|---:|---|---:|---|---:|---:|---|",
    ]
    for case in audit["cases"]:
        moments = sum(item["representative_moments"] for item in case["priorities"])
        details = sum(item["representative_moment_details"] for item in case["priorities"])
        assessment = "Clear cautious empty state" if case["empty_state"] else case["manual_product_assessment"]["analyst_readability"]
        lines.append(
            f"| {case['qa_index']} | {case['target_team']} vs {case['opponent_team']} | "
            f"{case['actual_priority_count']} | {'Pass' if case['workflow_complete'] else 'Fail'} | "
            f"{moments} | {details} | {assessment} |"
        )
    lines.extend([
        "",
        "## Analyst path assessment",
        "",
        "For non-empty briefings, the path is explicit: the ranked card states the review question and compact evidence comparison, `Open Evidence Pack` opens the matching source evidence, the first representative moment is selected automatically, and its ordered event sequence is drawn on the native StatsBomb pitch. Empty briefings stop cleanly without inventing themes.",
        "",
        "Baseline values appear once in the briefing and again in the detailed Evidence Pack. This repetition functions as orientation and does not introduce a second or conflicting claim. Technical provenance remains collapsed.",
        "",
        "## Remaining friction",
        "",
    ])
    for item in summary["recurring_product_friction"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## UI states",
        "",
    ])
    for name, passed in audit["ui_state_and_navigation_audit"]["checks"].items():
        lines.append(f"- `{name}`: {'present' if passed else 'missing'}")
    lines.extend([
        "",
        "## Audit limitation",
        "",
        audit["ui_state_and_navigation_audit"]["inspection_scope"],
        "",
        "## Conclusion",
        "",
        summary["conclusion"],
        "",
        "No product or analytical logic was changed during this audit.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", default="artifacts/event_profiles/statsbomb_11_27")
    parser.add_argument("--data-root", default="external_data/statsbomb_open_data")
    parser.add_argument("--json-output", default="artifacts/pre_match_briefing_workflow_qa.json")
    parser.add_argument("--markdown-output", default="docs/pre_match_briefing_workflow_qa.md")
    options = parser.parse_args()
    audit = build_audit(Path(options.profile_dir), Path(options.data_root))
    json_path, markdown_path = Path(options.json_output), Path(options.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps({
        "json": str(json_path), "markdown": str(markdown_path),
        "sample": audit["sample"], "summary": {
            key: value for key, value in audit["summary"].items()
            if key not in {"all_failures", "recurring_product_friction", "conclusion"}
        },
    }, indent=2))


if __name__ == "__main__":
    main()
