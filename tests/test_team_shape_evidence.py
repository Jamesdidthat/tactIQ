"""Product evidence tests for team-shape high-tail episodes."""

import unittest

import pandas as pd

from src.analysis.tactical_findings import generate_team_shape_extreme_findings
from src.analysis.team_shape_evidence import (
    group_high_tail_episodes,
    select_typical_and_extreme_moments,
)


def shape_rows() -> pd.DataFrame:
    rows = []
    for frame in range(1, 101):
        value = 30.0 + (frame % 3 - 1) / 10
        if frame in {80, 81, 82}:
            value = {80: 50.0, 81: 60.0, 82: 55.0}[frame]
        elif frame in {95, 96}:
            value = {95: 52.0, 96: 58.0}[frame]
        interval_start = ((frame - 1) // 10) * 10 + 1
        rows.append({
            "frame": frame,
            "period": 1,
            "timestamp": f"00:00:{frame / 10:05.2f}",
            "elapsed_seconds": frame / 10,
            "team_id": 7,
            "team_acronym": "TST",
            "outfield_length": value,
            "outfield_width": 20.0,
            "tactical_phase": "build_up" if frame < 80 else "create",
            "possession_status": "in_possession",
            "phase_frame_start": interval_start,
            "phase_frame_end": interval_start + 10,
        })
    return pd.DataFrame(rows)


class TeamShapeEvidenceTests(unittest.TestCase):
    def test_contiguous_high_tail_frames_are_grouped_as_episodes(self) -> None:
        rows = pd.DataFrame({
            "frame": [10, 11, 12, 20, 21, 1],
            "period": [1, 1, 1, 1, 1, 2],
            "outfield_length": [51, 54, 52, 55, 53, 56],
        })
        grouped = group_high_tail_episodes(rows, "outfield_length", high_tail_threshold=50)
        episodes = grouped.groupby("extreme_episode_id").first()
        self.assertEqual(len(episodes), 3)
        self.assertEqual(episodes.episode_frame_count.tolist(), [3, 2, 1])
        self.assertEqual(episodes.episode_frame_start.tolist(), [10, 20, 1])
        self.assertEqual(episodes.episode_frame_end_inclusive.tolist(), [12, 21, 1])

    def test_selection_is_stable_distinct_and_traceable(self) -> None:
        rows = shape_rows()
        original = rows.copy(deep=True)
        evidence = select_typical_and_extreme_moments(rows, "outfield_length")
        shuffled = select_typical_and_extreme_moments(rows.sample(frac=1, random_state=4), "outfield_length")
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence, shuffled)
        typical, extreme = evidence["references"]
        self.assertEqual([typical["label"], extreme["label"]], ["Typical example", "Extended example"])
        self.assertEqual(extreme["frame"], 81)
        self.assertGreaterEqual(extreme["metric_value_metres"], evidence["q95_metres"])
        self.assertEqual((extreme["episode_frame_start"], extreme["episode_frame_end_inclusive"]), (80, 82))
        self.assertEqual(extreme["episode_frame_count"], 3)
        self.assertNotEqual(typical["phase_frame_start"], extreme["phase_frame_start"])
        self.assertEqual(extreme["tactical_phase"], "create")
        self.assertEqual(evidence["evidence_context_separation"], "different_tactical_phase")
        pd.testing.assert_frame_equal(rows, original)

    def test_generator_uses_product_copy_and_typical_extreme_metrics(self) -> None:
        findings = generate_team_shape_extreme_findings(
            shape_rows(), match_id="m1", team_names={7: "Test United"}
        )
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.title, "Test United outfield length: typical and more extended shapes")
        self.assertNotIn("high-tail", finding.title)
        self.assertIn("absolute_deviation_from_median_metres", finding.evidence_metrics)
        self.assertEqual(finding.evidence_metrics["extreme_period"], 1)
        self.assertEqual(finding.evidence_metrics["extreme_tactical_phase"], "create")
        self.assertEqual(len(finding.supporting_references), 2)

    def test_available_phase_context_is_preferred_for_extreme_evidence(self) -> None:
        rows = shape_rows()
        rows.loc[rows.frame.isin([80, 81, 82]), "outfield_length"] = [50.0, 55.0, 53.0]
        rows.loc[rows.frame.isin([95, 96]), "outfield_length"] = [70.0, 65.0]
        rows.loc[rows.frame.isin([95, 96]), ["tactical_phase", "phase_frame_start", "phase_frame_end"]] = pd.NA
        evidence = select_typical_and_extreme_moments(rows, "outfield_length")
        extreme = evidence["references"][1]
        self.assertEqual(extreme["frame"], 81)
        self.assertEqual(extreme["tactical_phase"], "create")
        self.assertGreaterEqual(extreme["metric_value_metres"], evidence["q95_metres"])

    def test_constant_shape_does_not_invent_an_extreme_episode(self) -> None:
        rows = shape_rows()
        rows["outfield_length"] = 40.0
        self.assertIsNone(select_typical_and_extreme_moments(rows, "outfield_length"))


if __name__ == "__main__":
    unittest.main()
