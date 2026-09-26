import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.data import StatsBombOpenDataAdapter, statsbomb_team_coverage
from src.analysis.event_team_profile import (
    aggregate_event_team_match_metrics, build_event_team_season_profile,
    calculate_event_team_match_metrics,
)


def write_fixture(root: Path) -> None:
    data = root / "data"
    for folder in ("matches/1", "events", "lineups", "three-sixty"):
        (data / folder).mkdir(parents=True, exist_ok=True)
    (data / "competitions.json").write_text(json.dumps([{
        "competition_id": 1, "season_id": 1, "country_name": "Test",
        "competition_name": "Test League", "competition_gender": "female",
        "competition_youth": False, "competition_international": False,
        "season_name": "2026", "match_available": "2026-01-01",
        "match_available_360": "2026-01-01",
    }]), encoding="utf-8")
    (data / "matches/1/1.json").write_text(json.dumps([{
        "match_id": 100, "match_date": "2026-01-01", "kick_off": "12:00:00.000",
        "competition": {"competition_id": 1, "competition_name": "Test League", "country_name": "Test"},
        "season": {"season_id": 1, "season_name": "2026"},
        "home_team": {"home_team_id": 10, "home_team_name": "Alpha"},
        "away_team": {"away_team_id": 20, "away_team_name": "Beta"},
        "home_score": 1, "away_score": 0, "competition_stage": {"name": "League"},
    }]), encoding="utf-8")
    (data / "lineups/100.json").write_text(json.dumps([
        {"team_id": 10, "team_name": "Alpha", "lineup": [{"player_id": 1, "player_name": "A One", "player_nickname": None, "jersey_number": 1, "positions": [{"position": "Goalkeeper"}]}]},
        {"team_id": 20, "team_name": "Beta", "lineup": [{"player_id": 2, "player_name": "B One", "player_nickname": None, "jersey_number": 9, "positions": [{"position": "Center Forward"}]}]},
    ]), encoding="utf-8")
    events = [
        {"id": "event-1", "index": 1, "period": 1, "timestamp": "00:00:01.000", "minute": 0, "second": 1, "type": {"id": 30, "name": "Pass"}, "team": {"id": 10}, "player": {"id": 1}, "possession": 1, "possession_team": {"id": 10}, "play_pattern": {"name": "Regular Play"}, "location": [20, 30], "pass": {"end_location": [80, 40]}},
        {"id": "event-2", "index": 2, "period": 1, "timestamp": "00:00:02.000", "minute": 0, "second": 2, "type": {"id": 16, "name": "Shot"}, "team": {"id": 10}, "player": {"id": 1}, "possession": 1, "possession_team": {"id": 10}, "play_pattern": {"name": "Regular Play"}, "location": [100, 40], "shot": {"end_location": [120, 40], "outcome": {"name": "Goal"}, "statsbomb_xg": 0.25}},
    ]
    (data / "events/100.json").write_text(json.dumps(events), encoding="utf-8")
    (data / "three-sixty/100.json").write_text(json.dumps([{
        "event_uuid": "event-2", "visible_area": [0, 0, 120, 0, 120, 80],
        "freeze_frame": [{"teammate": True, "actor": True, "keeper": False, "location": [100, 40]}],
    }]), encoding="utf-8")


class StatsBombAdapterTests(unittest.TestCase):
    def test_event_bundle_lineups_identity_and_360_are_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            adapter = StatsBombOpenDataAdapter(root)
            bundle = adapter.load_match(100)
            self.assertTrue(bundle.capabilities.has_events)
            self.assertTrue(bundle.capabilities.has_lineups)
            self.assertTrue(bundle.capabilities.has_360_snapshots)
            self.assertFalse(bundle.capabilities.has_continuous_tracking)
            self.assertTrue(bundle.player_positions.empty)
            self.assertTrue(bundle.ball_positions.empty)
            self.assertEqual(bundle.events.is_shot.sum(), 1)
            self.assertEqual(len(bundle.event_snapshots), 1)
            self.assertEqual(adapter.resolve_team("Alpha")["team_id"], 10)
            self.assertEqual(adapter.resolve_team(10)["match_ids"], (100,))
            coverage = adapter.repository_asset_coverage().set_index("asset_type")
            self.assertEqual(coverage.loc["events", "repository_blobs"], 1)
            self.assertEqual(coverage.loc["events", "unindexed_blobs"], 0)

    def test_coverage_thresholds_do_not_overstate_one_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            coverage = statsbomb_team_coverage(StatsBombOpenDataAdapter(root))
            self.assertTrue(coverage.matches_available.eq(1).all())
            self.assertFalse(coverage.at_least_5_matches.any())
            self.assertFalse(coverage.at_least_10_matches.any())
            self.assertFalse(coverage.at_least_20_matches.any())

    def test_match_metrics_and_match_weighted_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            metrics = calculate_event_team_match_metrics(bundle)
            alpha = metrics.loc[metrics.team_id.eq(10)].iloc[0]
            self.assertEqual(alpha.passes_attempted, 1)
            self.assertEqual(alpha.passes_completed, 1)
            self.assertEqual(alpha.progressive_passes, 1)
            self.assertEqual(alpha.passes_into_final_third, 1)
            self.assertEqual(alpha.shots, 1)
            self.assertEqual(alpha.goals, 1)
            self.assertAlmostEqual(alpha.xg, 0.25)
            beta = metrics.loc[metrics.team_id.eq(20)].iloc[0]
            self.assertEqual(alpha.shots_conceded, beta.shots)
            self.assertAlmostEqual(alpha.xg_conceded, beta.xg)
            self.assertEqual(alpha.passes_into_penalty_area_conceded, beta.passes_into_penalty_area)
            self.assertEqual(alpha.counter_attack_shots_conceded, beta.counter_attack_shots)
            self.assertEqual(alpha.opponent_team_name, "Beta")
            self.assertEqual(alpha.home_away, "home")
            self.assertEqual(alpha.team_score, 1)
            self.assertEqual(alpha.opponent_score, 0)
            self.assertEqual(alpha.score_state_source, "event_goal_timeline_verified")
            self.assertAlmostEqual(alpha.drawing_seconds, 2.0)
            self.assertIn("progressive_passes_per90", alpha.metric_chronology)
            self.assertEqual(alpha.metric_chronology["shots"]["first_seconds"], 2.0)
            profile = build_event_team_season_profile(
                [bundle], team_id=10, competition_id=1, season_id=1,
            )
            self.assertEqual(len(profile.match_metrics), 1)
            shots = profile.aggregate_metrics.loc[profile.aggregate_metrics.metric.eq("shots")].iloc[0]
            self.assertEqual(shots.contributing_matches, 1)
            self.assertEqual(shots.median_across_matches, 1)

            compact = metrics.loc[metrics.team_id.eq(10)].copy()
            second = compact.copy()
            second["match_id"] = 101
            compact.loc[:, "shots"] = 1
            second.loc[:, "shots"] = 9
            weighted = aggregate_event_team_match_metrics(
                pd.concat([compact, second], ignore_index=True), team_id=10,
                team_name="Alpha", competition_id=1, season_id=1,
            )
            shots = weighted.aggregate_metrics.loc[weighted.aggregate_metrics.metric.eq("shots")].iloc[0]
            self.assertEqual(shots.median_across_matches, 5)
            self.assertEqual(shots.contributing_matches, 2)


if __name__ == "__main__":
    unittest.main()
