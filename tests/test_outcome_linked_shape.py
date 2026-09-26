"""Synthetic tests for interval-level outcome-linked shape summaries."""

import unittest

import pandas as pd

from src.analysis import summarize_defensive_shape_by_outcome


def make_joined_rows() -> pd.DataFrame:
    rows = []
    # Two intervals: one shot-leading (frames 10-12), one non-shot (12-13).
    for frame, start, end, shot, width, length in (
        (10, 10, 12, True, 20.0, 30.0),
        (11, 10, 12, True, 40.0, 50.0),
        (12, 12, 13, False, 60.0, 70.0),
    ):
        rows.append({
            "frame": frame, "timestamp": f"00:00:0{frame}.00", "elapsed_seconds": float(frame),
            "period": 1, "team_id": 1, "team_acronym": "DEF", "outfield_width": width,
            "outfield_length": length, "possession_team_id": 2,
            "possession_status": "out_of_possession", "tactical_phase": "medium_block",
            "phase_frame_start": start, "phase_frame_end": end,
            "team_possession_lead_to_shot": shot,
        })
    return pd.DataFrame(rows).set_index(
        ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
    )


class OutcomeLinkedShapeTests(unittest.TestCase):
    def test_uses_one_median_observation_per_source_interval(self) -> None:
        phases = pd.DataFrame([
            {"team_in_possession_id": 2, "frame_start": 10, "frame_end": 12, "team_possession_lead_to_shot": True},
            {"team_in_possession_id": 2, "frame_start": 12, "frame_end": 13, "team_possession_lead_to_shot": False},
        ])
        result = summarize_defensive_shape_by_outcome(
            make_joined_rows(), phases, possession_team_id=2, defending_team_id=1,
            min_intervals_per_outcome=1,
        )
        intervals = result["intervals"]
        shot_interval = intervals.loc[intervals["team_possession_lead_to_shot"]].iloc[0]
        self.assertEqual(len(intervals), 2)
        self.assertEqual(shot_interval["interval_median_outfield_width"], 30.0)
        self.assertEqual(shot_interval["represented_seconds"], 0.2)
        self.assertEqual(result["coverage"].iloc[0]["source_shot_leading_intervals"], 1)
        self.assertEqual(len(result["by_defending_phase"]), 2)


if __name__ == "__main__":
    unittest.main()
