"""API-Football live-provider contract, security and HTTP route tests."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from urllib.request import urlopen

import httpx

from src.api.http_server import LocalAnalysisHandler
from src.api.live_football_service import LiveFootballService
from src.data.api_football_live import (
    ApiFootballClient,
    ApiFootballConfigurationError,
    ApiFootballSettings,
)


FIXTURE = {
    "fixture": {
        "id": 123,
        "date": "2026-09-22T18:00:00+01:00",
        "timezone": "Africa/Lagos",
        "referee": "Referee",
        "venue": {"id": 9, "name": "Football Ground", "city": "Lagos"},
        "status": {"long": "Second Half", "short": "2H", "elapsed": 67, "extra": None},
    },
    "league": {"id": 1, "name": "Test League", "country": "Test", "logo": "https://img/league.png", "season": 2026, "round": "Round 4"},
    "teams": {
        "home": {"id": 10, "name": "Home FC", "logo": "https://img/home.png", "winner": True},
        "away": {"id": 20, "name": "Away FC", "logo": "https://img/away.png", "winner": False},
    },
    "goals": {"home": 2, "away": 1},
    "score": {"halftime": {"home": 1, "away": 1}, "fulltime": {"home": None, "away": None}, "extratime": {"home": None, "away": None}, "penalty": {"home": None, "away": None}},
}


def response(values):
    return httpx.Response(200, json={"get": "fixtures", "parameters": {}, "errors": {}, "results": len(values), "paging": {"current": 1, "total": 1}, "response": values})


class ApiFootballClientTests(unittest.TestCase):
    def test_missing_key_fails_before_network_access(self):
        client = ApiFootballClient(ApiFootballSettings(api_key=None))
        with self.assertRaisesRegex(ApiFootballConfigurationError, "TACTIQ_API_FOOTBALL_KEY"):
            client.fixtures(live="all")

    def test_fixture_list_maps_branding_score_and_live_state(self):
        seen = []

        def handler(request: httpx.Request):
            seen.append(request)
            return response([FIXTURE])

        client = ApiFootballClient(
            ApiFootballSettings(api_key="test-secret"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        fixtures = client.fixtures(live="all")
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["home_team"]["name"], "Home FC")
        self.assertEqual(fixtures[0]["home_team"]["logo_url"], "https://img/home.png")
        self.assertTrue(fixtures[0]["status"]["is_live"])
        self.assertEqual(seen[0].headers["x-apisports-key"], "test-secret")
        self.assertNotIn("test-secret", json.dumps(fixtures))

    def test_list_cache_prevents_duplicate_upstream_calls(self):
        count = 0

        def handler(request: httpx.Request):
            nonlocal count
            count += 1
            return response([FIXTURE])

        client = ApiFootballClient(
            ApiFootballSettings(api_key="secret", fixture_list_ttl_seconds=180),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        client.fixtures(live="all")
        client.fixtures(live="all")
        self.assertEqual(count, 1)

    def test_snapshot_exposes_granular_capabilities_without_tracking(self):
        def handler(request: httpx.Request):
            path = request.url.path
            if path.endswith("/fixtures"):
                return response([FIXTURE])
            if path.endswith("/fixtures/events"):
                return response([{"time": {"elapsed": 11}, "team": FIXTURE["teams"]["home"], "player": {"id": 5, "name": "Player"}, "assist": {}, "type": "Goal", "detail": "Normal Goal"}])
            if path.endswith("/fixtures/statistics"):
                return response([{"team": FIXTURE["teams"]["home"], "statistics": [{"type": "Shots on Goal", "value": 4}]}])
            if path.endswith("/fixtures/lineups"):
                return response([{"team": FIXTURE["teams"]["home"], "formation": "4-3-3", "startXI": [{"player": {"id": 5, "name": "Player", "number": 9, "pos": "F"}}], "substitutes": []}])
            if path.endswith("/fixtures/players"):
                return response([])
            raise AssertionError(path)

        client = ApiFootballClient(
            ApiFootballSettings(api_key="secret"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        snapshot = client.fixture_snapshot(123)
        self.assertTrue(snapshot["capabilities"]["has_coarse_incident_timeline"])
        self.assertTrue(snapshot["capabilities"]["has_team_match_statistics"])
        self.assertTrue(snapshot["capabilities"]["has_lineups"])
        self.assertFalse(snapshot["capabilities"]["has_player_match_statistics"])
        self.assertFalse(snapshot["capabilities"]["has_continuous_tracking"])
        self.assertIn("does not support tracking-derived shape", snapshot["analysis_scope"])
        json.dumps(snapshot, allow_nan=False)

    def test_embedded_fixture_details_avoid_four_extra_quota_calls(self):
        enriched = {**FIXTURE, "events": [], "statistics": [], "lineups": [], "players": []}
        calls = []

        def handler(request: httpx.Request):
            calls.append(request.url.path)
            return response([enriched])

        client = ApiFootballClient(
            ApiFootballSettings(api_key="secret"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        client.fixture_snapshot(123)
        self.assertEqual(calls, ["/fixtures"])


class LiveFootballHttpTests(unittest.TestCase):
    def test_status_and_fixture_routes_use_product_contract(self):
        class StubService:
            def status(self):
                return {"schema_version": "v1", "provider": "api_football", "configured": True}

            def fixtures(self, **kwargs):
                return {"schema_version": "v1", "provider": "api_football", "query": kwargs, "fixture_count": 1, "fixtures": []}

            def fixture(self, fixture_id):
                return {"schema_version": "tactiq.live-match.v1", "provider": "api_football", "fixture_id": fixture_id}

            def matchup_preview(self, fixture_id):
                return {"schema_version": "tactiq.api-football-matchup-preview.v1", "provider": "api_football", "fixture_id": fixture_id}

        class Handler(LocalAnalysisHandler):
            live_football_service = StubService()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(f"{base}/live-football/status", timeout=5) as result:
                self.assertTrue(json.load(result)["configured"])
            with urlopen(f"{base}/live-football/fixtures?live=all&league=39&season=2026", timeout=5) as result:
                payload = json.load(result)
            self.assertEqual(payload["query"]["live"], "all")
            self.assertEqual(payload["query"]["league"], 39)
            with urlopen(f"{base}/live-football/fixtures/123", timeout=5) as result:
                self.assertEqual(json.load(result)["fixture_id"], 123)
            with urlopen(f"{base}/live-football/fixtures/123/matchup-preview", timeout=5) as result:
                self.assertEqual(json.load(result)["schema_version"], "tactiq.api-football-matchup-preview.v1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
