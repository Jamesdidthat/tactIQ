import unittest

import pandas as pd

from src.analysis.cross_match_outcomes import (
    compare_phase_relative_defensive_shape_by_shot_outcome,
)


class PhaseRelativeOutcomeComparisonTests(unittest.TestCase):
    def test_centres_each_team_phase_before_outcome_summary(self):
        rows = []
        for team_id, acronym, offset in [(1, "ONE", 0.0), (2, "TWO", 10.0)]:
            for is_shot, width, length in [
                (False, offset + 8.0, offset + 18.0),
                (False, offset + 10.0, offset + 20.0),
                (True, offset + 12.0, offset + 24.0),
                (True, offset + 14.0, offset + 26.0),
            ]:
                rows.append({
                    "match_id": team_id,
                    "defending_team_id": team_id,
                    "defending_team_acronym": acronym,
                    "defending_phase_type": "medium_block",
                    "team_possession_lead_to_shot": is_shot,
                    "median_outfield_width": width,
                    "median_outfield_length": length,
                })
        intervals = pd.DataFrame(rows)

        result = compare_phase_relative_defensive_shape_by_shot_outcome(
            intervals,
            pooled_min_intervals_per_outcome=2,
            team_phase_min_intervals_per_outcome=2,
        )

        pooled = result["pooled_by_phase"].set_index("team_possession_lead_to_shot")
        self.assertEqual(pooled.loc[False, "interval_count"], 4)
        self.assertEqual(pooled.loc[True, "interval_count"], 4)
        self.assertEqual(pooled.loc[False, "median_outfield_width"], -2.0)
        self.assertEqual(pooled.loc[True, "median_outfield_width"], 2.0)
        difference = result["pooled_phase_median_differences"].iloc[0]
        self.assertEqual(difference["median_width_difference_shot_minus_non_shot"], 4.0)
        self.assertEqual(difference["median_length_difference_shot_minus_non_shot"], 6.0)


if __name__ == "__main__":
    unittest.main()
