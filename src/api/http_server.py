"""Localhost-only HTTP wrapper for the product-facing MatchAnalysisService."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from src.data import StatsBombOpenDataAdapter, load_skillcorner_match, preflight_skillcorner_phase_periods
from src.data.api_football_live import ApiFootballConfigurationError, ApiFootballRequestError
from src.analysis import TeamProfileArtifactStore, TeamProfileIdentity
from src.ai import MatchStoryExplanationService, TacticalExplanationService, explanation_provider_from_environment

from .match_analysis_service import MatchAnalysisService
from .team_profile_service import TeamProfileService
from .event_profile_service import (
    EventProfileService, artifact_event_profile_resolver,
    event_profile_artifact_catalog,
)
from .opponent_comparison_service import OpponentComparisonService
from .live_football_service import LiveFootballService
from .football_data_service import FootballDataService
from src.data.football_data_live import (
    FootballDataConfigurationError,
    FootballDataRequestError,
)


def skillcorner_resolver(matches_root: Path):
    """Return a lazy resolver for local SkillCorner match directories only."""
    def resolve(match_id: str | int):
        directory = matches_root / str(match_id)
        if not directory.is_dir():
            raise KeyError(f"Local match {match_id!r} was not found.")
        return load_skillcorner_match(directory)
    return resolve


def skillcorner_team_resolver(matches_root: Path):
    def resolve(team_id: str | int):
        requested = int(team_id) if str(team_id).isdigit() else team_id
        directories, excluded, team_name = [], [], None
        for directory in sorted(matches_root.iterdir()):
            metadata = directory / f"{directory.name}_match.json"
            if not directory.is_dir() or not metadata.is_file():
                continue
            info = json.loads(metadata.read_text(encoding="utf-8"))
            teams = (info.get("home_team", {}), info.get("away_team", {}))
            selected = next((team for team in teams if team.get("id") == requested), None)
            if selected:
                team_name = team_name or selected.get("name") or selected.get("acronym")
                issue = preflight_skillcorner_phase_periods(directory)
                if issue:
                    excluded.append({"match_id": int(directory.name), "provider": "skillcorner_open_data", "reason": issue})
                else:
                    directories.append(directory)
        if team_name is None:
            raise KeyError(f"Local team {team_id!r} was not found.")
        identity = TeamProfileIdentity(requested, team_name or str(requested), {"skillcorner_open_data": requested})
        return identity, (load_skillcorner_match(directory) for directory in directories), excluded
    return resolve


class LocalAnalysisHandler(BaseHTTPRequestHandler):
    """Serve only the v1 frontend paths over a loopback-bound server."""

    service: MatchAnalysisService
    team_service: TeamProfileService
    event_profile_service: EventProfileService
    opponent_comparison_service: OpponentComparisonService
    live_football_service: LiveFootballService
    football_data_service: FootballDataService
    event_profile_catalog: dict

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        path = [unquote(part) for part in parsed_url.path.strip("/").split("/")]
        query = parse_qs(parsed_url.query)
        try:
            if path == ["football-data", "status"]:
                self._send_json(HTTPStatus.OK, self.football_data_service.status())
                return
            if path == ["football-data", "competitions"]:
                self._send_json(HTTPStatus.OK, self.football_data_service.competitions())
                return
            if len(path) == 4 and path[:2] == ["football-data", "competitions"] and path[3] == "fixtures":
                self._send_json(HTTPStatus.OK, self.football_data_service.fixtures(
                    path[2],
                    status=query.get("status", [None])[0],
                    date_from=query.get("dateFrom", [None])[0],
                    date_to=query.get("dateTo", [None])[0],
                ))
                return
            if len(path) == 4 and path[:2] == ["football-data", "competitions"] and path[3] == "teams":
                self._send_json(HTTPStatus.OK, self.football_data_service.teams(path[2]))
                return
            if len(path) == 4 and path[:2] == ["football-data", "matches"] and path[3] == "matchup-preview":
                self._send_json(HTTPStatus.OK, self.football_data_service.matchup_preview(int(path[2])))
                return
            if path == ["live-football", "status"]:
                self._send_json(HTTPStatus.OK, self.live_football_service.status())
                return
            if path == ["live-football", "leagues"]:
                self._send_json(HTTPStatus.OK, self.live_football_service.leagues())
                return
            if path == ["live-football", "fixtures"]:
                integer = lambda name: int(query[name][0]) if query.get(name) else None
                self._send_json(HTTPStatus.OK, self.live_football_service.fixtures(
                    live=query.get("live", [None])[0],
                    fixture_date=query.get("date", [None])[0],
                    league=integer("league"),
                    season=integer("season"),
                    next_count=integer("next"),
                ))
                return
            if len(path) == 3 and path[:2] == ["live-football", "fixtures"]:
                self._send_json(HTTPStatus.OK, self.live_football_service.fixture(int(path[2])))
                return
            if len(path) == 4 and path[:2] == ["live-football", "fixtures"] and path[3] == "matchup-preview":
                self._send_json(HTTPStatus.OK, self.live_football_service.matchup_preview(int(path[2])))
                return
            if path == ["event-profile-catalog"]:
                self._send_json(HTTPStatus.OK, self.event_profile_catalog)
                return
            if path == ["team-profile-catalog"]:
                self._send_json(HTTPStatus.OK, self.team_service.catalog())
                return
            # /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority}/evidence-pack
            if len(path) == 12 and path[0] == "opponent-comparisons" and path[9] == "review-priorities" and path[11] == "evidence-pack":
                self._send_json(
                    HTTPStatus.OK,
                    self.opponent_comparison_service.review_priority_evidence_pack(
                        *path[1:9], priority_id=path[10],
                    ),
                )
                return
            # /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority}/moments/{event}
            if len(path) == 13 and path[0] == "opponent-comparisons" and path[9] == "review-priorities" and path[11] == "moments":
                self._send_json(
                    HTTPStatus.OK,
                    self.opponent_comparison_service.review_priority_moment_detail(
                        *path[1:9], priority_id=path[10], event_id=path[12],
                    ),
                )
                return
            # /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority}/moments
            if len(path) == 12 and path[0] == "opponent-comparisons" and path[9] == "review-priorities" and path[11] == "moments":
                self._send_json(
                    HTTPStatus.OK,
                    self.opponent_comparison_service.review_priority_moments(
                        *path[1:9], priority_id=path[10],
                    ),
                )
                return
            # /opponent-comparisons/{target provider/team/competition/season}/{opponent provider/team/competition/season}/{resource}
            if len(path) == 10 and path[0] == "opponent-comparisons":
                resource = path[9]
                endpoint = {
                    "summary": self.opponent_comparison_service.summary,
                    "metrics": self.opponent_comparison_service.metrics,
                    "findings": self.opponent_comparison_service.findings,
                    "interactions": self.opponent_comparison_service.interactions,
                    "interaction-findings": self.opponent_comparison_service.interaction_findings,
                    "review-priorities": self.opponent_comparison_service.review_priorities,
                    "briefing": self.opponent_comparison_service.pre_match_briefing,
                }.get(resource)
                if endpoint is None:
                    raise KeyError("Unknown opponent comparison endpoint.")
                self._send_json(HTTPStatus.OK, endpoint(*path[1:9]))
                return
            # /event-profiles/{provider}/{team}/{competition}/{season}/matches/{match}/story/explanation
            if len(path) == 9 and path[0] == "event-profiles" and path[5] == "matches" and path[7:] == ["story", "explanation"]:
                self._send_json(HTTPStatus.OK, self.event_profile_service.match_story_explanation(path[1], path[2], path[3], path[4], path[6]))
                return
            # /event-profiles/{provider}/{team}/{competition}/{season}/matches/{match}/story
            if len(path) == 8 and path[0] == "event-profiles" and path[5] == "matches" and path[7] == "story":
                self._send_json(HTTPStatus.OK, self.event_profile_service.match_story(path[1], path[2], path[3], path[4], path[6]))
                return
            # /event-profiles/{provider}/{team}/{competition}/{season}/matches/{match}/tactical-analysis
            if len(path) == 8 and path[0] == "event-profiles" and path[5] == "matches" and path[7] == "tactical-analysis":
                self._send_json(HTTPStatus.OK, self.event_profile_service.match_tactical_analysis(path[1], path[2], path[3], path[4], path[6]))
                return
            # /event-profiles/{provider}/{team}/{competition}/{season}/style-concepts/{concept}/moments
            if len(path) == 8 and path[0] == "event-profiles" and path[5] == "style-concepts" and path[7] == "moments":
                self._send_json(HTTPStatus.OK, self.event_profile_service.style_concept_moments(
                    path[1], path[2], path[3], path[4], path[6],
                    limit=int(query.get("limit", ["6"])[0]),
                ))
                return
            # /event-profiles/{provider}/{team}/{competition}/{season}/{endpoint}
            if len(path) == 6 and path[0] == "event-profiles":
                provider, team_id, competition_id, season_id, resource = path[1:]
                endpoint = {
                    "summary": self.event_profile_service.summary,
                    "baselines": self.event_profile_service.baselines,
                    "findings": self.event_profile_service.findings,
                    "tendencies": self.event_profile_service.tendencies,
                    "unusual-matches": self.event_profile_service.unusual_matches,
                    "archetypes": self.event_profile_service.archetypes,
                    "relationships": self.event_profile_service.relationships,
                    "matches": self.event_profile_service.matches,
                    "football-style": self.event_profile_service.football_style,
                }.get(resource)
                if endpoint is None:
                    raise KeyError("Unknown Event Profile endpoint.")
                self._send_json(HTTPStatus.OK, endpoint(provider, team_id, competition_id, season_id))
                return
            if len(path) == 3 and path[0] == "teams":
                endpoint = {"summary": self.team_service.summary, "metrics": self.team_service.metrics, "finding-families": self.team_service.finding_families, "matches": self.team_service.matches, "deviations": self.team_service.deviations, "shape-style": self.team_service.shape_style}.get(path[2])
                if endpoint is None:
                    raise KeyError("Unknown Team Profile endpoint.")
                self._send_json(HTTPStatus.OK, endpoint(path[1]))
                return
            # /matches/{id}/summary | findings | coverage
            if len(path) == 3 and path[0] == "matches":
                match_id, endpoint = path[1:]
                payload = {
                    "summary": self.service.get_match_summary,
                    "findings": self.service.get_ranked_findings,
                    "coverage": self.service.get_analysis_coverage,
                    "tactical-analysis": self.service.get_tactical_analysis,
                }.get(endpoint)
                if payload is None:
                    raise KeyError("Unknown v1 endpoint.")
                self._send_json(HTTPStatus.OK, payload(match_id))
                return
            # /matches/{id}/findings/{findingId}
            if len(path) == 4 and path[0] == "matches" and path[2] == "findings":
                self._send_json(HTTPStatus.OK, self.service.get_finding_detail(path[1], path[3]))
                return
            # /matches/{id}/findings/{findingId}/explanation
            if len(path) == 5 and path[0] == "matches" and path[2] == "findings" and path[4] == "explanation":
                self._send_json(HTTPStatus.OK, self.service.get_finding_explanation(path[1], path[3]))
                return
            # /matches/{id}/findings/{findingId}/moments/{n}/frame
            if len(path) == 7 and path[0] == "matches" and path[2] == "findings" and path[4] == "moments" and path[6] == "frame":
                self._send_json(HTTPStatus.OK, self.service.get_representative_pitch_frame(path[1], path[3], moment_index=int(path[5])))
                return
            # /matches/{id}/frames/{frame}/periods/{period}
            if len(path) == 6 and path[0] == "matches" and path[2] == "frames" and path[4] == "periods":
                self._send_json(HTTPStatus.OK, self.service.get_pitch_frame(path[1], int(path[3]), int(path[5])))
                return
            # /matches/{id}/clips/{centreFrame}/periods/{period}?before=25&after=25&step=1
            if len(path) == 6 and path[0] == "matches" and path[2] == "clips" and path[4] == "periods":
                self._send_json(HTTPStatus.OK, self.service.get_pitch_clip(
                    path[1], int(path[3]), int(path[5]),
                    before_frames=int(query.get("before", ["25"])[0]),
                    after_frames=int(query.get("after", ["25"])[0]),
                    step=int(query.get("step", ["1"])[0]),
                    before_seconds=float(query["before_seconds"][0]) if "before_seconds" in query else None,
                    after_seconds=float(query["after_seconds"][0]) if "after_seconds" in query else None,
                ))
                return
            raise KeyError("Unknown v1 endpoint.")
        except KeyError as error:
            self._send_json(HTTPStatus.NOT_FOUND, {"schema_version": "v1", "error": str(error)})
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"schema_version": "v1", "error": str(error)})
        except (
            ApiFootballConfigurationError,
            ApiFootballRequestError,
            FootballDataConfigurationError,
            FootballDataRequestError,
        ) as error:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"schema_version": "v1", "error": str(error)})
        except Exception:  # Keep local diagnostic detail out of the product contract.
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"schema_version": "v1", "error": "Local analysis request failed."})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        print(f"[tactiq-api] {self.address_string()} {format % args}")


def run_local_server(matches_root: str | Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the wrapper only on loopback for local development."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The local development API may bind only to localhost.")
    explanation_provider = explanation_provider_from_environment()
    LocalAnalysisHandler.team_service = TeamProfileService(
        skillcorner_team_resolver(Path(matches_root)),
        artifact_store=TeamProfileArtifactStore("artifacts/team_profiles"),
        provider="skillcorner_open_data",
    )
    LocalAnalysisHandler.service = MatchAnalysisService(
        skillcorner_resolver(Path(matches_root)),
        explanation_service=TacticalExplanationService(explanation_provider),
        tracking_profile_resolver=LocalAnalysisHandler.team_service.get_result,
    )
    event_profile_root = Path("artifacts")
    event_profile_resolver = artifact_event_profile_resolver(event_profile_root)
    LocalAnalysisHandler.event_profile_catalog = event_profile_artifact_catalog(event_profile_root)
    statsbomb_adapter = StatsBombOpenDataAdapter(
        Path(__file__).resolve().parents[2] / "external_data" / "statsbomb_open_data"
    )
    event_bundle_cache = {}

    def event_bundle_resolver(provider: str, match_id: int):
        if provider != "statsbomb_open_data":
            raise KeyError(f"Representative event moments are not configured for provider {provider!r}.")
        key = (provider, int(match_id))
        if key not in event_bundle_cache:
            event_bundle_cache[key] = statsbomb_adapter.load_match(int(match_id))
        return event_bundle_cache[key]

    LocalAnalysisHandler.event_profile_service = EventProfileService(
        event_profile_resolver,
        story_explanation_service=MatchStoryExplanationService(explanation_provider),
        event_bundle_resolver=event_bundle_resolver,
    )

    LocalAnalysisHandler.opponent_comparison_service = OpponentComparisonService(
        event_profile_resolver, event_bundle_resolver,
    )
    LocalAnalysisHandler.live_football_service = LiveFootballService()
    LocalAnalysisHandler.football_data_service = FootballDataService()
    server = ThreadingHTTPServer((host, port), LocalAnalysisHandler)
    print(f"TactIQ local API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TactIQ's localhost-only v1 analysis API.")
    parser.add_argument("--matches-root", default="opendata/data/matches")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args()
    run_local_server(options.matches_root, options.host, options.port)
