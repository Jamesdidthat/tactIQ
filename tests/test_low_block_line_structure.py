"""Tests for interval-level low-block line-structure comparisons."""

import unittest

import pandas as pd

from src.analysis import compare_low_block_line_structure_by_shot_outcome


METRICS = [
    "median_defence_to_midfield_gap",
    "median_midfield_to_attack_gap",
    "median_defence_tactical_median_x",
    "median_midfield_tactical_median_x",
    "median_attack_tactical_median_x",
    "median_total_outfield_length",
    "median_defence_tactical_vertical_range",
    "median_midfield_tactical_vertical_range",
    "median_attack_tactical_vertical_range",
    "median_defence_tactical_median_absolute_deviation",
    "median_midfield_tactical_median_absolute_deviation",
    "median_attack_tactical_median_absolute_deviation",
    "median_deepest_defender_x",
    "median_highest_attacker_x",
    "median_total_outfield_vertical_range",
]


class LowBlockLineStructureTests(unittest.TestCase):
    def test_excludes_incomplete_intervals_and_centres_by_team(self) -> None:
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
                }
                row.update({metric: value + offset for metric in METRICS})
                rows.append(row)
        incomplete = rows[0].copy()
        incomplete["complete_line_frame_count"] = 9
        rows.append(incomplete)

        result = compare_low_block_line_structure_by_shot_outcome(
            pd.DataFrame(rows), min_intervals_per_team_outcome=2
        )

        quality = result["quality"].iloc[0]
        self.assertEqual(quality["low_block_intervals"], 9)
        self.assertEqual(quality["complete_line_intervals"], 8)
        self.assertEqual(quality["excluded_incomplete_line_mapping"], 1)
        pooled = result["pooled"].query("metric == 'defence_to_midfield_gap'").set_index(
            "team_possession_lead_to_shot"
        )
        self.assertEqual(pooled.loc[False, "median_deviation_metres"], -2.0)
        self.assertEqual(pooled.loc[True, "median_deviation_metres"], 2.0)
        difference = result["pooled_median_differences"].query(
            "metric == 'defence_to_midfield_gap'"
        ).iloc[0]
        self.assertEqual(difference["median_difference_shot_minus_non_shot_metres"], 4.0)


if __name__ == "__main__":
    unittest.main()
