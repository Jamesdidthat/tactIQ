"""Synthetic tests for phase-level Team Shape summaries."""

import unittest

import pandas as pd

from src.analysis import summarize_phase_shape


def make_joined_shape() -> pd.DataFrame:
    rows = []
    for frame, width, length, interval_start, interval_end in (
        (10, 20.0, 30.0, 10, 12),
        (11, 30.0, 40.0, 10, 12),
        (12, 40.0, 50.0, 12, 13),
    ):
        rows.append({
            "frame": frame, "timestamp": f"00:00:0{frame}.00", "elapsed_seconds": float(frame),
            "period": 1, "team_id": 1, "team_acronym": "HOME", "outfield_width": width,
            "outfield_length": length, "possession_status": "in_possession",
            "tactical_phase": "build_up", "possession_team_id": 1,
            "phase_frame_start": interval_start, "phase_frame_end": interval_end,
        })
    rows.append({
        "frame": 13, "timestamp": "00:00:13.00", "elapsed_seconds": 13.0, "period": 1,
        "team_id": 1, "team_acronym": "HOME", "outfield_width": 99.0, "outfield_length": 99.0,
        "possession_status": pd.NA, "tactical_phase": pd.NA, "possession_team_id": pd.NA,
        "phase_frame_start": pd.NA, "phase_frame_end": pd.NA,
    })
    return pd.DataFrame(rows).set_index(
        ["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"]
    )


class PhaseShapeSummaryTests(unittest.TestCase):
    def test_summary_excludes_unlabelled_rows_and_calculates_distribution(self) -> None:
        result = summarize_phase_shape(make_joined_shape())
        row = result.iloc[0]
        self.assertEqual(len(result), 1)
        self.assertEqual(row["frame_count"], 3)
        self.assertEqual(row["represented_seconds"], 0.3)
        self.assertEqual(row["phase_interval_count"], 2)
        self.assertEqual(row["median_outfield_width"], 30.0)
        self.assertEqual(row["q25_outfield_width"], 25.0)
        self.assertEqual(row["q75_outfield_length"], 45.0)
        self.assertEqual(row["possession_status"], "in_possession")


if __name__ == "__main__":
    unittest.main()
