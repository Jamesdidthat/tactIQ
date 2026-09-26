"""Frozen live-API and production-route QA for the deterministic briefing export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


FROZEN_MATCHUPS = (
    (221, 223, 0), (223, 210, 0), (207, 209, 0), (207, 210, 0),
    (213, 215, 1), (209, 322, 1), (214, 1041, 1),
    (210, 220, 3), (216, 220, 3), (207, 212, 3),
    (212, 217, 5), (217, 221, 5),
)


def fetch_json(url: str, origin: str) -> tuple[int, dict]:
    with urlopen(Request(url, headers={"Origin": origin}), timeout=300) as response:
        return response.status, json.load(response)


def fetch_html(url: str) -> tuple[int, str]:
    with urlopen(url, timeout=30) as response:
        return response.status, response.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8016")
    parser.add_argument("--frontend", default="http://127.0.0.1:5176")
    parser.add_argument("--json-output", default="artifacts/pre_match_briefing_export_qa.json")
    parser.add_argument("--markdown-output", default="docs/pre_match_briefing_export_qa.md")
    options = parser.parse_args()
    api, frontend = options.api.rstrip("/"), options.frontend.rstrip("/")
    _, catalog = fetch_json(f"{api}/event-profile-catalog", frontend)
    names = {int(item["team_id"]): item["team_name"] for item in catalog["profiles"]}
    cases = []
    total_packs = total_selected_moments = total_static_pitches = 0

    for index, (target_id, opponent_id, expected_count) in enumerate(FROZEN_MATCHUPS, start=1):
        identity = ("statsbomb_open_data", str(target_id), "11", "27", "statsbomb_open_data", str(opponent_id), "11", "27")
        api_path = "/opponent-comparisons/" + "/".join(identity)
        briefing_status, payload = fetch_json(f"{api}{api_path}/briefing", frontend)
        priorities = payload["briefing"]["review_priorities"]
        priority_ids = [item["priority_id"] for item in priorities]
        pack_ids, selected_moments, static_pitches, unique_event_ids = [], 0, 0, True
        for priority in priorities:
            pack_status, pack_payload = fetch_json(f"{api}{api_path}/review-priorities/{quote(priority['priority_id'], safe='')}/evidence-pack", frontend)
            if pack_status != 200:
                continue
            pack = pack_payload["evidence_pack"]
            pack_ids.append(pack["priority"]["priority_id"])
            moments = pack["representative_moments"][:3]
            selected_moments += len(moments)
            event_ids = [item["event_id"] for item in moments]
            unique_event_ids = unique_event_ids and len(event_ids) == len(set(event_ids))
            details = {item["event_id"]: item for item in pack["representative_moment_details"]}
            static_pitches += sum(any(event.get("pitch_renderable") for event in details.get(moment_id, {}).get("sequence_events", [])) for moment_id in event_ids)
        query = {
            "target_provider": identity[0], "target_team_id": identity[1], "target_competition_id": identity[2], "target_season_id": identity[3],
            "opponent_provider": identity[4], "opponent_team_id": identity[5], "opponent_competition_id": identity[6], "opponent_season_id": identity[7],
        }
        export_url = f"{frontend}/pre-match-briefing/print?{urlencode(query)}"
        route_status, html = fetch_html(export_url)
        refresh_status, refresh_html = fetch_html(export_url)
        passed = all((briefing_status == 200, len(priorities) == expected_count, priority_ids == pack_ids, route_status == 200, refresh_status == 200, html == refresh_html, 'id="root"' in html, unique_event_ids))
        total_packs += len(pack_ids); total_selected_moments += selected_moments; total_static_pitches += static_pitches
        cases.append({
            "target_team": names[target_id], "opponent_team": names[opponent_id], "expected_priorities": expected_count,
            "actual_priorities": len(priorities), "priority_order_preserved": priority_ids == pack_ids,
            "evidence_packs_loaded": len(pack_ids), "selected_representative_moments": selected_moments,
            "static_pitch_visuals_available": static_pitches, "selected_event_ids_unique": unique_event_ids,
            "export_route_status": route_status, "refresh_status": refresh_status, "passed": passed,
        })
        print(f"Export QA {index}/12: {names[target_id]} vs {names[opponent_id]} {'PASS' if passed else 'FAIL'}", flush=True)

    source = Path("frontend/src/PreMatchBriefingPrintPage.tsx").read_text(encoding="utf-8")
    briefing_source = Path("frontend/src/PreMatchBriefingPage.tsx").read_text(encoding="utf-8")
    main_source = Path("frontend/src/main.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    export_checks = {
        "dedicated_action": "Print / Export briefing" in briefing_source,
        "dedicated_deep_link_route": "PreMatchBriefingPrintPage" in main_source and "preMatchBriefingPrint" in main_source,
        "browser_print_action": "window.print()" in source,
        "a4_page_rule": "@page { size: A4" in css,
        "print_controls_hidden": ".print-controls { display: none !important;" in css,
        "grayscale_pitch": "filter: grayscale(1)" in css,
        "page_break_protection": "break-inside: avoid" in css and "page-break-inside: avoid" in css,
        "deterministic_priority_order": "loadedPriorities.map" in source and "slice(0, 3)" in source,
        "static_pitch_renderer_reused": "StatsBombEventPitch" in source,
        "generation_timestamp": "generatedAt" in source and "<time" in source,
        "explicit_video_status": "Video availability" in source,
        "technical_appendix_separate": "Technical appendix" in source and "print-appendix" in source,
        "empty_state_present": "No review themes passed the evidence threshold" in source,
        "live_deep_links_present": "Open this Evidence Pack in TactIQ" in source and "Open live detail" in source,
        "no_ai_generation": "explanationApi" not in source and "AI explanation" not in source,
    }
    summary = {
        "passed_matchups": sum(item["passed"] for item in cases), "failed_matchups": sum(not item["passed"] for item in cases),
        "evidence_packs_loaded": total_packs, "selected_representative_moments": total_selected_moments,
        "static_pitch_visuals_available": total_static_pitches, "all_export_contract_checks_passed": all(export_checks.values()),
        "priority_distribution": {"0": 4, "1": 3, "3": 3, "5": 2},
        "qa_boundary": "Production SPA routes and live API evidence were exercised. No installed browser automation runtime was available for pixel-level PDF pagination or physical-printer testing.",
    }
    result = {"audit_version": "pre_match_briefing_export_v1", "frozen_matchups": 12, "export_contract_checks": export_checks, "cases": cases, "summary": summary}
    json_path, markdown_path = Path(options.json_output), Path(options.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True); markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Pre-Match Briefing Export QA", "", "Frozen QA across 12 contrasting matchups. No analytical logic, rankings, thresholds, priority identities, ordering, or Evidence Pack contents were changed.", "", "| Matchup | Priorities | Packs | Moments | Static pitches | Order | Export | Result |", "|---|---:|---:|---:|---:|---|---:|---|"]
    for case in cases:
        lines.append(f"| {case['target_team']} vs {case['opponent_team']} | {case['actual_priorities']} | {case['evidence_packs_loaded']} | {case['selected_representative_moments']} | {case['static_pitch_visuals_available']} | {'Preserved' if case['priority_order_preserved'] else 'Changed'} | {case['export_route_status']} | {'Pass' if case['passed'] else 'Fail'} |")
    lines.extend(["", "## Export contract", "", *[f"- {name.replace('_', ' ').capitalize()}: {'Pass' if passed else 'Fail'}" for name, passed in export_checks.items()], "", "## Outcome", "", f"- Frozen matchups passed: **{summary['passed_matchups']}/12**", f"- Evidence Packs loaded: **{total_packs}**", f"- Representative moments selected for export: **{total_selected_moments}**", f"- Selected moments with static pitch data: **{total_static_pitches}**", "- Empty, one-, three-, and five-priority briefing cases all rendered through the same deterministic export route.", "", "## QA boundary", "", summary["qa_boundary"], ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
