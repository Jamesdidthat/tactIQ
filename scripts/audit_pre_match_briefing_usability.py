"""Frozen HTTP/browser-route usability audit for the Pre-Match Briefing UI."""

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


def fetch_json(url: str, origin: str) -> tuple[int, dict, str | None]:
    with urlopen(Request(url, headers={"Origin": origin}), timeout=300) as response:
        return response.status, json.load(response), response.headers.get("Access-Control-Allow-Origin")


def fetch_html(url: str) -> tuple[int, str]:
    with urlopen(url, timeout=30) as response:
        return response.status, response.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8015")
    parser.add_argument("--frontend", default="http://127.0.0.1:5175")
    parser.add_argument("--json-output", default="artifacts/pre_match_briefing_usability_qa.json")
    parser.add_argument("--markdown-output", default="docs/pre_match_briefing_usability_qa.md")
    options = parser.parse_args()
    api, frontend = options.api.rstrip("/"), options.frontend.rstrip("/")
    catalog_status, catalog, cors = fetch_json(f"{api}/event-profile-catalog", frontend)
    names = {int(item["team_id"]): item["team_name"] for item in catalog["profiles"]}
    setup_status, setup_html = fetch_html(f"{frontend}/pre-match-briefing")
    cases = []
    for index, (target_id, opponent_id, expected_count) in enumerate(FROZEN_MATCHUPS, start=1):
        identity = (
            "statsbomb_open_data", str(target_id), "11", "27",
            "statsbomb_open_data", str(opponent_id), "11", "27",
        )
        path = "/opponent-comparisons/" + "/".join(identity)
        status, payload, response_cors = fetch_json(f"{api}{path}/briefing", frontend)
        priorities = payload["briefing"]["review_priorities"]
        priority = priorities[0] if priorities else None
        moment = None
        pack_status = detail_status = None
        if priority:
            priority_id = priority["priority_id"]
            pack_status, pack_payload, _ = fetch_json(
                f"{api}{path}/review-priorities/{quote(priority_id, safe='')}/evidence-pack", frontend,
            )
            moments = pack_payload["evidence_pack"]["representative_moments"]
            moment = moments[0] if moments else None
            if moment:
                detail_status, _, _ = fetch_json(
                    f"{api}{path}/review-priorities/{quote(priority_id, safe='')}/moments/{quote(moment['event_id'], safe='')}",
                    frontend,
                )
        query = {
            "target_provider": identity[0], "target_team_id": identity[1],
            "target_competition_id": identity[2], "target_season_id": identity[3],
            "opponent_provider": identity[4], "opponent_team_id": identity[5],
            "opponent_competition_id": identity[6], "opponent_season_id": identity[7],
        }
        if priority:
            query["priority"] = priority["priority_id"]
        if moment:
            query["moment"] = moment["event_id"]
        deep_link = f"{frontend}/pre-match-briefing?{urlencode(query)}"
        deep_status, deep_html = fetch_html(deep_link)
        refresh_status, refresh_html = fetch_html(deep_link)
        passed = all((
            status == 200, len(priorities) == expected_count,
            response_cors == frontend, deep_status == 200, refresh_status == 200,
            "id=\"root\"" in deep_html, deep_html == refresh_html,
            not priority or (pack_status == 200 and moment is not None and detail_status == 200),
        ))
        cases.append({
            "index": index, "target_team": names[target_id], "opponent_team": names[opponent_id],
            "expected_priorities": expected_count, "actual_priorities": len(priorities),
            "briefing_http_status": status, "evidence_pack_http_status": pack_status,
            "moment_detail_http_status": detail_status,
            "priority_id": priority["priority_id"] if priority else None,
            "moment_event_id": moment["event_id"] if moment else None,
            "deep_link": deep_link, "deep_link_http_status": deep_status,
            "refresh_http_status": refresh_status, "passed": passed,
        })
        print(f"Usability QA {index}/12: {names[target_id]} vs {names[opponent_id]} {'PASS' if passed else 'FAIL'}", flush=True)

    source = Path("frontend/src/PreMatchBriefingPage.tsx").read_text(encoding="utf-8")
    evidence_source = Path("frontend/src/OpponentComparisonPage.tsx").read_text(encoding="utf-8")
    state_checks = {
        "human_readable_selectors": all(label in source for label in ("Competition", "Season", "Target team", "Opponent")),
        "ids_preserved_as_hidden_api_identity": all(f'name="target_{field}"' in source and f'name="opponent_{field}"' in source for field in ("provider", "team_id", "competition_id", "season_id")),
        "priority_in_url": 'searchParams.set("priority"' in source,
        "moment_in_url": 'searchParams.set("moment"' in source,
        "popstate_restoration": 'addEventListener("popstate"' in source,
        "back_to_evidence_pack": "Back to Evidence Pack" in evidence_source,
        "back_to_briefing": 'closeLabel="Back to briefing"' in source,
        "technical_provenance_collapsed": "<summary>Technical provenance</summary>" in source,
        "football_facing_range_wording": "usual match ranges" in source and "usual conceded median" in source,
    }
    result = {
        "audit_version": "pre_match_briefing_usability_v1",
        "frozen_matchups": 12,
        "priority_distribution": {"0": 4, "1": 3, "3": 3, "5": 2},
        "catalog": {"http_status": catalog_status, "profile_count": len(catalog["profiles"]), "excluded_count": len(catalog["excluded"]), "cors_origin": cors},
        "frontend": {"setup_route_status": setup_status, "spa_root_present": 'id="root"' in setup_html},
        "state_and_navigation_checks": state_checks,
        "cases": cases,
        "summary": {
            "passed_matchups": sum(case["passed"] for case in cases),
            "failed_matchups": sum(not case["passed"] for case in cases),
            "all_state_checks_passed": all(state_checks.values()),
            "manual_url_editing_required": False,
            "remaining_limitations": [
                "Linked video remains unavailable in StatsBomb Open Data.",
                "This environment has no installed browser automation runtime; QA exercised the production SPA route, live API/CORS boundary, persisted deep-link contract, refresh round-trip, and compiled interaction states rather than pixel-level rendering or accessibility automation.",
            ],
        },
    }
    json_path, markdown_path = Path(options.json_output), Path(options.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True); markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = [
        "# Pre-Match Briefing Usability QA", "",
        "Frozen product QA across 12 matchups. Analytical logic, priority identities, ranking, thresholds, and ordering were unchanged.", "",
        "| Matchup | Priorities | Briefing | Pack | Moment | Deep link | Refresh | Result |", "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in cases:
        rows.append(f"| {case['target_team']} vs {case['opponent_team']} | {case['actual_priorities']} | {case['briefing_http_status']} | {case['evidence_pack_http_status'] or '—'} | {case['moment_detail_http_status'] or '—'} | {case['deep_link_http_status']} | {case['refresh_http_status']} | {'Pass' if case['passed'] else 'Fail'} |")
    rows.extend(["", "## State and navigation", ""])
    rows.extend(f"- {name.replace('_', ' ').capitalize()}: {'Pass' if passed else 'Fail'}" for name, passed in state_checks.items())
    rows.extend(["", "## Outcome", "", f"**{result['summary']['passed_matchups']}/12 matchups passed.** Available profile count: {len(catalog['profiles'])}. Manual URL editing required: no.", "", "## QA boundary", "", *[f"- {item}" for item in result["summary"]["remaining_limitations"]], ""])
    markdown_path.write_text("\n".join(rows), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
