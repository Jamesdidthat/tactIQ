"""Synthetic tests for attack-normalised tactical line structure."""

import unittest

import pandas as pd

from src.metrics import calculate_defensive_line_structure


def make_players(period: int, team_id: int, native_x: tuple[float, float, float]) -> pd.DataFrame:
    common = {
        "frame": 10,
        "timestamp": "00:00:00.00",
        "elapsed_seconds": 0.0,
        "period": period,
        "team_id": team_id,
        "team_acronym": "HOME" if team_id == 1 else "AWAY",
    }
    return pd.DataFrame([
        {**common, "player_id": 1, "position_group": "Central Defender", "x": native_x[0], "y": 0.0},
        {**common, "player_id": 2, "position_group": "Midfield", "x": native_x[1], "y": 0.0},
        {**common, "player_id": 3, "position_group": "Center Forward", "x": native_x[2], "y": 0.0},
        {**common, "player_id": 4, "position_group": "Other", "x": -40.0, "y": 0.0},
    ])


MATCH_INFO = {
    "home_team": {"id": 1},
    "away_team": {"id": 2},
    "home_team_side": ["left_to_right", "right_to_left"],
}


class DefensiveLineStructureTests(unittest.TestCase):
    def test_home_left_to_right_keeps_native_x_as_tactical_x(self) -> None:
        result = calculate_defensive_line_structure(
            make_players(1, 1, (-20.0, 0.0, 20.0)), MATCH_INFO
        ).iloc[0]
        self.assertEqual(result["defence_native_median_x"], -20.0)
        self.assertEqual(result["attack_tactical_median_x"], 20.0)
        self.assertEqual(result["defence_to_midfield_gap"], 20.0)
        self.assertEqual(result["midfield_to_attack_gap"], 20.0)
        self.assertEqual(result["total_outfield_length"], 40.0)
        self.assertTrue(result["line_structure_complete"])

    def test_line_ranges_dispersion_and_extrema_use_normalised_x(self) -> None:
        players = make_players(1, 1, (-20.0, 0.0, 20.0))
        extras = players.iloc[[0, 1, 2]].copy()
        extras["player_id"] = [5, 6, 7]
        extras["x"] = [-10.0, 5.0, 25.0]
        players = pd.concat([players, extras], ignore_index=True)
        result = calculate_defensive_line_structure(players, MATCH_INFO).iloc[0]
        self.assertEqual(result["defence_tactical_min_x"], -20.0)
        self.assertEqual(result["defence_tactical_max_x"], -10.0)
        self.assertEqual(result["defence_tactical_vertical_range"], 10.0)
        self.assertEqual(result["defence_tactical_median_absolute_deviation"], 5.0)
        self.assertEqual(result["deepest_defender_x"], -20.0)
        self.assertEqual(result["highest_attacker_x"], 25.0)
        self.assertEqual(result["total_outfield_vertical_range"], 45.0)

    def test_away_and_second_half_direction_are_normalised(self) -> None:
        away = calculate_defensive_line_structure(
            make_players(1, 2, (20.0, 0.0, -20.0)), MATCH_INFO
        ).iloc[0]
        home_second_half = calculate_defensive_line_structure(
            make_players(2, 1, (20.0, 0.0, -20.0)), MATCH_INFO
        ).iloc[0]
        for result in (away, home_second_half):
            self.assertEqual(result["defence_tactical_median_x"], -20.0)
            self.assertEqual(result["attack_tactical_median_x"], 20.0)
            self.assertEqual(result["defence_to_midfield_gap"], 20.0)

    def test_missing_line_is_marked_and_does_not_create_gaps(self) -> None:
        players = make_players(1, 1, (-20.0, 0.0, 20.0)).query("position_group != 'Midfield'")
        result = calculate_defensive_line_structure(players, MATCH_INFO).iloc[0]
        self.assertFalse(result["midfield_line_available"])
        self.assertTrue(pd.isna(result["midfield_tactical_median_x"]))
        self.assertTrue(pd.isna(result["defence_to_midfield_gap"]))
        self.assertFalse(result["line_structure_complete"])

    def test_team_frame_with_no_mapped_outfield_role_is_preserved(self) -> None:
        players = make_players(1, 1, (-20.0, 0.0, 20.0)).iloc[[3]].copy()
        result = calculate_defensive_line_structure(players, MATCH_INFO).iloc[0]
        self.assertEqual(result["outfield_player_count"], 0)
        self.assertFalse(result["defence_line_available"])
        self.assertFalse(result["line_structure_complete"])


if __name__ == "__main__":
    unittest.main()
