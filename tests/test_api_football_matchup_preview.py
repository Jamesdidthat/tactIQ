"""Football-first recent-manager matchup preview tests."""

from __future__ import annotations

import json
import unittest

from src.api.live_football_service import LiveFootballService


def fixture(fixture_id, date, home_id, home_name, away_id, away_name, home_goals, away_goals, home_possession, away_possession):
    return {
        "fixture": {"id": fixture_id, "date": f"{date}T15:00:00+00:00", "timezone": "UTC", "venue": {}, "status": {"long": "Match Finished", "short": "FT", "elapsed": 90}},
        "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026, "round": "Regular Season - 5"},
        "teams": {"home": {"id": home_id, "name": home_name, "logo": f"/{home_id}.png", "winner": home_goals > away_goals}, "away": {"id": away_id, "name": away_name, "logo": f"/{away_id}.png", "winner": away_goals > home_goals}},
        "goals": {"home": home_goals, "away": away_goals}, "score": {},
        "statistics": [
            {"team": {"id": home_id, "name": home_name}, "statistics": [{"type": "Ball Possession", "value": f"{home_possession}%"}, {"type": "Total Shots", "value": 15}, {"type": "Shots on Goal", "value": 6}, {"type": "Passes %", "value": "87%"}]},
            {"team": {"id": away_id, "name": away_name}, "statistics": [{"type": "Ball Possession", "value": f"{away_possession}%"}, {"type": "Total Shots", "value": 8}, {"type": "Shots on Goal", "value": 3}, {"type": "Passes %", "value": "79%"}]},
        ],
        "lineups": [
            {"team": {"id": home_id}, "formation": "4-2-3-1"},
            {"team": {"id": away_id}, "formation": "4-3-3"},
        ],
    }


class FakeClient:
    def __init__(self):
        self.target = fixture(999, "2026-10-01", 33, "Manchester United", 47, "Tottenham", 0, 0, 50, 50)
        self.rows = [
            fixture(1, "2026-09-20", 33, "Manchester United", 60, "Opponent A", 2, 0, 60, 40),
            fixture(2, "2026-09-13", 61, "Opponent B", 33, "Manchester United", 1, 1, 42, 58),
            fixture(3, "2026-09-19", 47, "Tottenham", 62, "Opponent C", 1, 0, 46, 54),
            fixture(4, "2026-09-12", 63, "Opponent D", 47, "Tottenham", 2, 1, 55, 45),
            fixture(5, "2026-08-01", 33, "Manchester United", 64, "Old opponent", 3, 0, 65, 35),
        ]

    def fixture_data(self, fixture_id): return self.target
    def coaches(self, team_id): return [{"id": team_id * 10, "name": f"Manager {team_id}", "photo": None, "team": {"id": team_id}, "career": [{"team": {"id": team_id}, "start": "2026-09-01", "end": None}]}]
    def recent_fixture_data(self, *, team_id, league_id, season, last): return [row for row in self.rows if team_id in {(row["teams"]["home"] or {})["id"], (row["teams"]["away"] or {})["id"]}]
    def fixture_details(self, fixture_ids): return [row for row in self.rows if row["fixture"]["id"] in fixture_ids]


class MatchupPreviewTests(unittest.TestCase):
    def test_preview_uses_current_manager_tenure_and_completed_match_unit(self):
        preview = LiveFootballService(FakeClient()).matchup_preview(999)
        self.assertEqual(preview["sample_definition"]["unit_of_evidence"], "completed_match")
        united = next(team for team in preview["teams"] if team["team"]["team_id"] == 33)
        self.assertEqual(united["matches_in_sample"], 2)
        self.assertNotIn(5, [match["fixture_id"] for match in united["recent_matches"]])
        self.assertEqual(united["manager"]["name"], "Manager 33")
        self.assertTrue(united["manager"]["verified"])

    def test_preview_calculates_basic_stats_and_plain_football_read(self):
        preview = LiveFootballService(FakeClient()).matchup_preview(999)
        united, spurs = preview["teams"]
        self.assertEqual(united["averages"]["possession"], 59.0)
        self.assertEqual(united["averages"]["shots"], 11.5)
        self.assertIn("controlling the ball", united["football_read"]["control"])
        self.assertGreaterEqual(len(preview["matchup_read"]), 2)
        self.assertNotIn("should", json.dumps(preview["matchup_read"]).lower())
        self.assertNotIn("will win", json.dumps(preview).lower())

    def test_preview_is_json_safe_and_explicit_about_tracking_limit(self):
        preview = LiveFootballService(FakeClient()).matchup_preview(999)
        json.dumps(preview, allow_nan=False)
        self.assertTrue(any("off-ball positioning" in item for item in preview["limitations"]))


if __name__ == "__main__":
    unittest.main()
