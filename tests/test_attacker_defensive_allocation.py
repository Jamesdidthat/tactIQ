import unittest

import pandas as pd

from src.metrics.attacker_defensive_allocation import calculate_attacker_defensive_allocation


class AttackerDefensiveAllocationTests(unittest.TestCase):
    def test_uses_nearest_ball_attacker_as_explicit_proxy(self):
        info = {"home_team": {"id": 1}, "away_team": {"id": 2}, "home_team_side": ["left_to_right"]}
        columns = ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym", "player_id", "position", "x", "y"]
        players = pd.DataFrame([
            (1, "00:00:00", 0., 1, 1, "H", 1, "Center Back", 0., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 2, "Center Back", 10., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 3, "Midfielder", 15., 0.),
            (1, "00:00:00", 0., 1, 1, "H", 4, "Forward", 30., 0.),
            (1, "00:00:00", 0., 1, 2, "A", 5, "Forward", 4., 4.),
            (1, "00:00:00", 0., 1, 2, "A", 6, "Forward", 12., 4.),
        ], columns=columns)
        balls = pd.DataFrame([(1, 1, 3., 4.)], columns=["frame", "period", "ball_x", "ball_y"])
        result = calculate_attacker_defensive_allocation(players, balls, info)
        home = result["frame_metrics"].loc[lambda x: x.team_id.eq(1)].iloc[0]
        self.assertEqual(home.defenders_nearest_to_ball_carrier_count, 1)
        self.assertEqual(home.defenders_nearest_to_off_ball_attacker_count, 3)
        self.assertFalse(home.carrier_defender_overload_2plus)
        attackers = result["attacker_context"].loc[lambda x: x.team_id.eq(1)]
        self.assertEqual(int(attackers.is_ball_carrier_proxy.sum()), 1)
        self.assertEqual(int(attackers.is_off_ball.sum()), 1)


if __name__ == "__main__":
    unittest.main()
