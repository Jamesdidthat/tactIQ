"""Synthetic tests for frame-level team shape calculations."""

import unittest

import pandas as pd

from src.metrics import calculate_team_shape


def make_players() -> pd.DataFrame:
    """Create two teams with deliberately simple native-coordinate positions."""
    common = {"timestamp": "00:00:00.00", "elapsed_seconds": 0.0, "period": 1}
    return pd.DataFrame(
        [
            # Team MEL: goalkeeper plus two outfield players.
            {**common, "frame": 100, "team_id": 1, "team_acronym": "MEL", "player_id": 1,
             "position": "Goalkeeper", "x": -10.0, "y": 0.0},
            {**common, "frame": 100, "team_id": 1, "team_acronym": "MEL", "player_id": 2,
             "position": "Center Back", "x": 0.0, "y": -5.0},
            {**common, "frame": 100, "team_id": 1, "team_acronym": "MEL", "player_id": 3,
             "position": "Right Winger", "x": 10.0, "y": 5.0},
            # Team AUC: no goalkeeper row; all players are outfield.
            {**common, "frame": 100, "team_id": 2, "team_acronym": "AUC", "player_id": 4,
             "position": "Center Forward", "x": 1.0, "y": 2.0},
            {**common, "frame": 100, "team_id": 2, "team_acronym": "AUC", "player_id": 5,
             "position": "Midfield", "x": 5.0, "y": 8.0},
        ]
    )


class CalculateTeamShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shape = calculate_team_shape(make_players())

    def test_full_team_metrics_use_x_for_length_and_y_for_width(self) -> None:
        mel = self.shape.loc[(100, "00:00:00.00", 0.0, 1, 1, "MEL")]
        self.assertEqual(mel["full_team_width"], 10.0)
        self.assertEqual(mel["full_team_length"], 20.0)
        self.assertAlmostEqual(mel["full_team_centroid_x"], 0.0)
        self.assertAlmostEqual(mel["full_team_centroid_y"], 0.0)
        self.assertEqual(mel["player_count"], 3)

    def test_outfield_metrics_exclude_goalkeeper_by_position(self) -> None:
        mel = self.shape.loc[(100, "00:00:00.00", 0.0, 1, 1, "MEL")]
        self.assertEqual(mel["outfield_width"], 10.0)
        self.assertEqual(mel["outfield_length"], 10.0)
        self.assertAlmostEqual(mel["outfield_centroid_x"], 5.0)
        self.assertAlmostEqual(mel["outfield_centroid_y"], 0.0)

    def test_team_without_goalkeeper_uses_all_players_as_outfield(self) -> None:
        auc = self.shape.loc[(100, "00:00:00.00", 0.0, 1, 2, "AUC")]
        self.assertEqual(auc["outfield_width"], auc["full_team_width"])
        self.assertEqual(auc["outfield_length"], auc["full_team_length"])


if __name__ == "__main__":
    unittest.main()
