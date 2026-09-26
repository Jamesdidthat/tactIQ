"""Tests for ball-relative low-block outcome comparisons."""

import unittest

import pandas as pd

from src.analysis import compare_low_block_ball_relative_by_shot_outcome


BALL_METRICS = [
    "median_defence_line_to_ball_distance",
    "median_midfield_line_to_ball_distance",
    "median_attack_line_to_ball_distance",
    "median_deepest_defender_to_ball_distance",
    "median_highest_attacker_to_ball_distance",
]


class LowBlockBallRelativeTests(unittest.TestCase):
    def test_reports_ball_coverage_and_centres_by_team(self) -> None:
        rows = []
        for team_id, offset in [(1, 0.0), (2, 10.0)]:
            for is_shot, value in [(False, 8.0), (False, 10.0), (True, 12.0), (True, 14.0)]:
                row = {
                    "defending_phase_type": "low_block",
                    "defending_team_id": team_id,
                    "defending_team_acronym": f"T{team_id}",
                    "team_possession_lead_to_shot": is_shot,
                    "matched_frame_count": 10,
                    "complete_line_frame_count": 10,
                    "ball_available_frame_count": 8,
                    "defending_half_ball_frame_count": 8,
                    "ball_depth_zone": "middle_defending_half",
                }
                row.update({metric: value + offset for metric in BALL_METRICS})
                rows.append(row)
        missing_ball = rows[0].copy()
        missing_ball["ball_available_frame_count"] = 0
        missing_ball["ball_depth_zone"] = None
        missing_ball.update({metric: float("nan") for metric in BALL_METRICS})
        rows.append(missing_ball)

        result = compare_low_block_ball_relative_by_shot_outcome(
            pd.DataFrame(rows), min_intervals_per_team_outcome=2
        )
        quality = result["quality"].iloc[0]
        self.assertEqual(quality["matched_frame_count"], 90)
        self.assertEqual(quality["ball_available_frame_count"], 64)
        self.assertEqual(quality["missing_ball_frame_count"], 26)
        pooled = result["pooled"].query(
            "metric == 'defence_line_to_ball_distance'"
        ).set_index("team_possession_lead_to_shot")
        self.assertEqual(pooled.loc[False, "interval_count"], 4)
        self.assertEqual(pooled.loc[True, "median_deviation_metres"], 2.0)
        difference = result["pooled_median_differences"].query(
            "metric == 'defence_line_to_ball_distance'"
        ).iloc[0]
        self.assertEqual(difference["median_difference_shot_minus_non_shot_metres"], 4.0)


if __name__ == "__main__":
    unittest.main()
