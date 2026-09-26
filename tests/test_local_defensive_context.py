import unittest

import numpy as np
import pandas as pd

from src.metrics.local_defensive_context import calculate_local_defensive_context


class LocalDefensiveContextTests(unittest.TestCase):
    def setUp(self):
        self.info = {"home_team": {"id": 1}, "away_team": {"id": 2}, "home_team_side": ["left_to_right"]}
        cols = ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "player_id", "position", "position_group", "x", "y"]
        self.players = pd.DataFrame([
            (1, "00:00:00", 0., 1, 1, "H", 1, "Center Back", "Central Defender", 0., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 2, "Center Back", "Central Defender", 10., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 3, "Midfielder", "Midfield", 15., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 4, "Forward", "Center Forward", 30., 0.),
            (1, "00:00:00", 0., 1, 2, "A", 5, "Forward", "Center Forward", 4., 4.),
            (1, "00:00:00", 0., 1, 2, "A", 6, "Forward", "Center Forward", 12., 4.),
        ], columns=cols)
        self.balls = pd.DataFrame([(1, "00:00:00", 0., 1, 3., 4.)], columns=["frame", "timestamp", "elapsed_seconds", "period", "ball_x", "ball_y"])
        self.lines = pd.DataFrame([(1, "00:00:00", 0., 1, 1, "H", 5., 15.)], columns=["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "defence_tactical_median_x", "midfield_tactical_median_x"]).set_index(["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"])

    def test_local_geometry_and_line_context(self):
        result = calculate_local_defensive_context(self.players, self.balls, self.lines, self.info)
        home = result.loc[result.team_id.eq(1)].iloc[0]
        self.assertAlmostEqual(home.nearest_defender_distance, 5.)
        self.assertAlmostEqual(home.second_nearest_defender_distance, np.sqrt(65))
        self.assertAlmostEqual(home.third_nearest_defender_distance, np.sqrt(160))
        self.assertEqual(home.defenders_within_5m, 1)
        self.assertEqual(home.defenders_within_10m, 2)
        self.assertEqual(home.defenders_within_15m, 3)
        self.assertEqual(home.defending_outfield_goal_side_count, 1)
        self.assertEqual(home.defenders_within_local_radius, 2)
        self.assertEqual(home.attackers_within_local_radius, 2)
        self.assertEqual(home.local_numerical_balance, 0)
        self.assertEqual(home.attackers_goal_side_of_ball_count, 0)
        self.assertEqual(home.attackers_ahead_of_nearest_defender_count, 0)
        self.assertEqual(home.attackers_without_defender_within_3m, 2)
        self.assertEqual(home.attackers_without_defender_within_5m, 1)
        self.assertEqual(home.attackers_without_defender_within_8m, 0)
        self.assertAlmostEqual(home.attacker_nearest_defender_distance_median, (np.sqrt(32) + np.sqrt(20)) / 2)
        self.assertAlmostEqual(home.attacker_nearest_defender_distance_max, np.sqrt(32))
        self.assertEqual(home.attackers_between_defence_and_midfield_count, 1)
        self.assertEqual(home.attackers_in_defending_penalty_area_corridor, 0)
        self.assertEqual(home.attackers_in_central_danger_zone, 0)
        self.assertAlmostEqual(home.defender_ball_concentration_10m, 0.5)
        self.assertAlmostEqual(home.defence_line_to_ball_distance, 2.)
        self.assertFalse(home.ball_between_defence_and_midfield)
        self.assertAlmostEqual(home.nearest_defender_line_separation, 10.)

    def test_missing_ball_stays_missing(self):
        balls = self.balls.copy(); balls.loc[0, "ball_x"] = np.nan
        result = calculate_local_defensive_context(self.players, balls, self.lines, self.info)
        home = result.loc[result.team_id.eq(1)].iloc[0]
        self.assertTrue(pd.isna(home.nearest_defender_distance))
        self.assertTrue(pd.isna(home.local_numerical_balance))


if __name__ == "__main__":
    unittest.main()
