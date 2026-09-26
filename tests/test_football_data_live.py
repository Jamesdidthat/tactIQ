"""football-data.org client, preview and route tests."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from urllib.request import urlopen

import httpx

from src.api.football_data_service import FootballDataService
from src.api.http_server import LocalAnalysisHandler
from src.data.football_data_live import (
    FootballDataClient,
    FootballDataConfigurationError,
    FootballDataSettings,
)


COMPETITION = {
    "id": 2021, "code": "PL", "name": "Premier League", "type": "LEAGUE", "emblem": "https://img/pl.png",
    "area": {"name": "England", "code": "ENG", "flag": "https://img/eng.svg"},
    "currentSeason": {"startDate": "2026-08-14", "endDate": "2027-05-23", "currentMatchday": 5},
}
HOME = {"id": 66, "name": "Manchester United FC", "shortName": "Man United", "tla": "MUN", "crest": "https://img/mun.png"}
AWAY = {"id": 73, "name": "Tottenham Hotspur FC", "shortName": "Tottenham", "tla": "TOT", "crest": "https://img/tot.png"}


def match(match_id=100, date="2026-10-01T19:00:00Z", status="TIMED", home=HOME, away=AWAY, home_goals=None, away_goals=None):
    return {
        "id": match_id, "utcDate": date, "status": status, "matchday": 6,
        "competition": COMPETITION, "season": COMPETITION["currentSeason"],
        "homeTeam": home, "awayTeam": away,
        "score": {"winner": None, "fullTime": {"home": home_goals, "away": away_goals}, "halfTime": {"home": None, "away": None}},
        "referees": [],
    }


class FootballDataClientTests(unittest.TestCase):
    def test_missing_key_fails_before_request(self):
        client = FootballDataClient(FootballDataSettings(api_key=None))
        with self.assertRaisesRegex(FootballDataConfigurationError, "TACTIQ_FOOTBALL_DATA_KEY"):
            client.competitions()

    def test_auth_mapping_and_cache(self):
        requests = []

        def handler(request: httpx.Request):
            requests.append(request)
            return httpx.Response(200, json={"competitions": [COMPETITION]})

        client = FootballDataClient(
            FootballDataSettings(api_key="secret"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        first = client.competitions()
        second = client.competitions()
        self.assertEqual(first, second)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].headers["X-Auth-Token"], "secret")
        self.assertEqual(first[0]["code"], "PL")
        self.assertNotIn("secret", json.dumps(first))

    def test_current_fixture_and_team_mapping(self):
        def handler(request: httpx.Request):
            if request.url.path.endswith("/matches"):
                return httpx.Response(200, json={"matches": [match()]})
            if request.url.path.endswith("/teams"):
                return httpx.Response(200, json={"teams": [HOME, AWAY]})
            raise AssertionError(request.url.path)

        client = FootballDataClient(
            FootballDataSettings(api_key="secret"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        fixture = client.competition_matches("PL")[0]
        self.assertEqual(fixture["competition"]["code"], "PL")
        self.assertEqual(fixture["home_team"]["name"], "Manchester United FC")
        self.assertEqual(client.competition_teams("PL")[1]["tla"], "TOT")


class FootballDataServiceTests(unittest.TestCase):
    def test_preview_describes_results_without_inventing_tactics(self):
        class StubClient:
            configured = True
            def match_data(self, match_id): return match(match_id)
            def team_data(self, team_id): return {"coach": {"id": team_id + 1, "name": f"Coach {team_id}", "contract": {"start": "2026-07-01"}}}
            def team_matches(self, team_id, **kwargs):
                other = AWAY if team_id == HOME["id"] else HOME
                team = HOME if team_id == HOME["id"] else AWAY
                return [match(90 + index, f"2026-09-{20-index:02d}T15:00:00Z", "FINISHED", team, other, 2, 1) for index in range(5)]

        preview = FootballDataService(StubClient()).matchup_preview(100)
        self.assertEqual(len(preview["teams"]), 2)
        self.assertEqual(preview["teams"][0]["matches_in_sample"], 5)
        self.assertIsNone(preview["teams"][0]["averages"]["possession"])
        serialized = json.dumps(preview)
        self.assertIn("scorelines alone", serialized.lower())
        self.assertNotIn("pressing intensity", serialized.lower())


class FootballDataHttpTests(unittest.TestCase):
    def test_catalog_fixture_team_and_preview_routes(self):
        class StubService:
            def status(self): return {"schema_version": "v1", "provider": "football_data_org", "configured": True}
            def competitions(self): return {"schema_version": "v1", "competitions": [{"code": "PL"}]}
            def fixtures(self, code, **kwargs): return {"schema_version": "v1", "competition_code": code, "query": kwargs}
            def teams(self, code): return {"schema_version": "v1", "competition_code": code, "teams": []}
            def matchup_preview(self, match_id): return {"schema_version": "tactiq.current-matchup-preview.v1", "match_id": match_id}

        class Handler(LocalAnalysisHandler):
            football_data_service = StubService()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(f"{base}/football-data/competitions", timeout=5) as result:
                self.assertEqual(json.load(result)["competitions"][0]["code"], "PL")
            with urlopen(f"{base}/football-data/competitions/PL/fixtures?status=SCHEDULED", timeout=5) as result:
                self.assertEqual(json.load(result)["query"]["status"], "SCHEDULED")
            with urlopen(f"{base}/football-data/competitions/PL/teams", timeout=5) as result:
                self.assertEqual(json.load(result)["competition_code"], "PL")
            with urlopen(f"{base}/football-data/matches/100/matchup-preview", timeout=5) as result:
                self.assertEqual(json.load(result)["match_id"], 100)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
