"""Synthetic tests for phase interval expansion and Team Shape joins."""

import unittest

import pandas as pd

from src.data.phase_context import (
    audit_phase_context_join,
    expand_phase_context,
    join_phase_context_to_team_shape,
)


MATCH = {
    "id": 99,
    "home_team": {"id": 1, "acronym": "HOME"},
    "away_team": {"id": 2, "acronym": "AWAY"},
}


def make_phases() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "match_id": 99, "frame_start": 10, "frame_end": 12, "period": 1,
            "duration": 0.2, "team_in_possession_id": 1,
            "team_in_possession_phase_type": "build_up",
            "team_out_of_possession_phase_type": "medium_block",
            "team_possession_lead_to_shot": False,
            "team_possession_lead_to_goal": False,
        }]
    )


def make_team_shape() -> pd.DataFrame:
    index = pd.MultiIndex.from_tuples(
        [
            (frame, f"00:00:0{frame}.00", float(frame), 1, team_id, acronym)
            for frame in (9, 10, 11, 12)
            for team_id, acronym in ((1, "HOME"), (2, "AWAY"))
        ],
        names=["frame", "timestamp", "elapsed_seconds", "period", "team_id", "team_acronym"],
    )
    return pd.DataFrame({"player_count": 11}, index=index)


class PhaseContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = expand_phase_context(make_phases(), MATCH)

    def test_expansion_uses_inclusive_start_and_exclusive_end(self) -> None:
        self.assertEqual(set(self.context["frame"]), {10, 11})
        self.assertEqual(len(self.context), 4)  # Two frames × two teams.
        self.assertEqual(self.context.duplicated(["frame", "period", "team_id"]).sum(), 0)

    def test_context_assigns_possession_and_defending_labels_to_correct_teams(self) -> None:
        home = self.context.query("frame == 10 and team_id == 1").iloc[0]
        away = self.context.query("frame == 10 and team_id == 2").iloc[0]
        self.assertEqual((home["possession_status"], home["tactical_phase"]), ("in_possession", "build_up"))
        self.assertEqual((away["possession_status"], away["tactical_phase"]), ("out_of_possession", "medium_block"))

    def test_expansion_rejects_duration_inconsistent_with_frame_interval(self) -> None:
        invalid_phases = make_phases()
        invalid_phases.loc[0, "duration"] = 0.3
        with self.assertRaisesRegex(ValueError, "Phase durations"):
            expand_phase_context(invalid_phases, MATCH)

    def test_join_preserves_shape_frames_outside_phase_intervals_as_unlabelled(self) -> None:
        shape = make_team_shape()
        joined = join_phase_context_to_team_shape(shape, self.context, MATCH)
        self.assertTrue(joined.loc[(9, "00:00:09.00", 9.0, 1, 1, "HOME"), "tactical_phase"] != joined.loc[(9, "00:00:09.00", 9.0, 1, 1, "HOME"), "tactical_phase"])
        self.assertEqual(joined.loc[(10, "00:00:010.00", 10.0, 1, 1, "HOME"), "tactical_phase"], "build_up")
        audit = audit_phase_context_join(shape, self.context, MATCH)
        self.assertEqual(audit["unmatched_phase_team_frames"], 0)
        self.assertEqual(audit["unmatched_shape_team_frames"], 4)


if __name__ == "__main__":
    unittest.main()
