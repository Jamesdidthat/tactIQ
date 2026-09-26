"""Adapter-level canonical-contract checks independent of downloaded files."""

import unittest

import pandas as pd

from src.data.metrica import validate_canonical_metrica_data


def canonical_fixture() -> dict:
    info = {
        "pitch_length": 105.0, "pitch_width": 68.0,
        "home_team": {"id": "home"}, "away_team": {"id": "away"},
        "home_team_side": ["left_to_right", "right_to_left"],
    }
    players = pd.DataFrame([
        {"frame": 1, "period": 1, "elapsed_seconds": 0.04, "player_id": "h1", "team_id": "home", "position": "Goalkeeper", "position_group": "Other", "x": -50.0, "y": 0.0},
        {"frame": 1, "period": 1, "elapsed_seconds": 0.04, "player_id": "a1", "team_id": "away", "position": "Goalkeeper", "position_group": "Other", "x": 50.0, "y": 0.0},
    ])
    balls = pd.DataFrame([{"frame": 1, "period": 1, "elapsed_seconds": 0.04, "ball_x": 0.0, "ball_y": 0.0}])
    return {"match_info": info, "player_positions": players, "ball_positions": balls}


class MetricaCanonicalValidationTests(unittest.TestCase):
    def test_valid_canonical_fixture_passes(self) -> None:
        validate_canonical_metrica_data(canonical_fixture())

    def test_duplicate_player_frame_is_rejected(self) -> None:
        value = canonical_fixture()
        value["player_positions"] = pd.concat([value["player_positions"], value["player_positions"].iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_canonical_metrica_data(value)

    def test_unreasonable_out_of_bounds_position_is_rejected(self) -> None:
        value = canonical_fixture()
        value["player_positions"].loc[0, "x"] = 100.0
        with self.assertRaisesRegex(ValueError, "bounds"):
            validate_canonical_metrica_data(value)

    def test_missing_direction_period_is_rejected(self) -> None:
        value = canonical_fixture()
        value["player_positions"].loc[:, "period"] = 3
        value["ball_positions"].loc[:, "period"] = 3
        with self.assertRaisesRegex(ValueError, "direction"):
            validate_canonical_metrica_data(value)


if __name__ == "__main__":
    unittest.main()
