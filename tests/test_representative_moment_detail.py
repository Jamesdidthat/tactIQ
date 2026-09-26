"""Representative moment detail boundary and ordering tests."""

from dataclasses import replace
import unittest

import pandas as pd

from src.analysis import RepresentativeMoment, build_representative_moment_detail
from src.data.canonical import CanonicalMatchBundle, ProviderCapabilities


def bundle(events: list[dict]) -> CanonicalMatchBundle:
    defaults = {
        "match_id": 10, "period": 1, "timestamp": "00:00:00.000", "minute": 0,
        "second": 0, "elapsed_seconds": 0.0, "team_id": 1, "player_id": None,
        "event_type": "Pass", "is_shot": False, "possession_id": 7,
        "possession_team_id": 1, "location_x": None, "location_y": None,
        "end_location_x": None, "end_location_y": None, "pass_outcome": None,
        "outcome": None, "shot_outcome": None, "shot_type": None, "shot_xg": None,
        "play_pattern": "Regular Play", "coordinate_system": "statsbomb_120x80",
        "attributes": {},
    }
    rows = [{**defaults, **event} for event in events]
    return CanonicalMatchBundle(
        provider="statsbomb_open_data", match_info={"id": 10},
        matches=pd.DataFrame([{"match_id": 10, "pitch_length_m": pd.NA, "pitch_width_m": pd.NA}]),
        teams=pd.DataFrame([
            {"match_id": 10, "team_id": 1, "team_code": "A", "team_name": "A"},
            {"match_id": 10, "team_id": 2, "team_code": "B", "team_name": "B"},
        ]),
        roster=pd.DataFrame(columns=["match_id", "player_id", "team_id", "position", "position_group", "is_goalkeeper"]),
        player_positions=pd.DataFrame(columns=["match_id", "frame", "period", "elapsed_seconds", "player_id", "team_id", "x", "y"]),
        ball_positions=pd.DataFrame(columns=["match_id", "frame", "period", "elapsed_seconds", "ball_x", "ball_y"]),
        attacking_directions=pd.DataFrame(columns=["match_id", "period", "team_id", "attacking_x_sign"]),
        capabilities=ProviderCapabilities(False, False, False, False, True, False),
        events=pd.DataFrame(rows),
    )


def moment(event_id: str) -> RepresentativeMoment:
    return RepresentativeMoment(
        match_id=10, team_id=1, team_name="A", opponent_id=2, opponent_name="B",
        match_date="2016-01-01", minute=0, second=4, period=1, event_id=event_id,
        event_type="Pass", metric="passes_into_final_third_per90", family="final_third_entries",
        description="Example.", relevant_values={}, score_state="drawing", score_state_verified=True,
        score_state_team_id=1, score_state_team_name="A",
        source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable_in_statsbomb_open_data",
        reason_selected="typical_match_example", evidence_side="attacking_production",
    )


class RepresentativeMomentDetailTests(unittest.TestCase):
    def test_known_possession_never_crosses_possession_boundary_and_preserves_order(self):
        data = bundle([
            {"event_id": "a", "event_index": 1, "elapsed_seconds": 1.0, "second": 1, "possession_id": 7, "location_x": 20, "location_y": 30, "end_location_x": 30, "end_location_y": 30},
            {"event_id": "other", "event_index": 2, "elapsed_seconds": 2.0, "second": 2, "possession_id": 8},
            {"event_id": "focal", "event_index": 3, "elapsed_seconds": 4.0, "second": 4, "possession_id": 7, "location_x": 40, "location_y": 30, "end_location_x": 50, "end_location_y": 30},
            {"event_id": "next", "event_index": 4, "elapsed_seconds": 5.0, "second": 5, "possession_id": 7, "event_type": "Carry", "location_x": 50, "location_y": 30, "end_location_x": 55, "end_location_y": 32},
            {"event_id": "later", "event_index": 5, "elapsed_seconds": 6.0, "second": 6, "possession_id": 7},
        ])
        detail = build_representative_moment_detail(moment("focal"), data)
        self.assertEqual(detail.context_mode, "same_possession")
        self.assertEqual([event.event_id for event in detail.sequence_events], ["a", "focal", "next"])
        self.assertNotIn("other", {event.event_id for event in detail.sequence_events})

    def test_missing_coordinates_remain_missing_and_unrenderable(self):
        data = bundle([
            {"event_id": "a", "event_index": 1, "elapsed_seconds": 1.0},
            {"event_id": "focal", "event_index": 2, "elapsed_seconds": 2.0},
        ])
        detail = build_representative_moment_detail(moment("focal"), data)
        self.assertIsNone(detail.focal_event.start_coordinates)
        self.assertFalse(detail.focal_event.pitch_renderable)
        self.assertTrue(any("unavailable coordinates" in item for item in detail.limitations))

    def test_missing_possession_uses_bounded_same_period_window(self):
        data = bundle([
            {"event_id": "before", "event_index": 1, "elapsed_seconds": 95.0, "minute": 1, "second": 35, "possession_id": None},
            {"event_id": "focal", "event_index": 2, "elapsed_seconds": 100.0, "minute": 1, "second": 40, "possession_id": None},
            {"event_id": "too-late", "event_index": 3, "elapsed_seconds": 105.0, "minute": 1, "second": 45, "possession_id": None},
            {"event_id": "other-period", "event_index": 4, "elapsed_seconds": 99.0, "period": 2, "possession_id": None},
        ])
        detail = build_representative_moment_detail(moment("focal"), data, after_seconds=3)
        self.assertEqual(detail.context_mode, "bounded_time_window")
        self.assertEqual([event.event_id for event in detail.sequence_events], ["before", "focal"])

    def test_unsupported_focal_type_is_retained_without_visual_inference(self):
        data = bundle([
            {"event_id": "focal", "event_index": 1, "event_type": "Goal Keeper", "location_x": 5, "location_y": 40},
        ])
        source = moment("focal")
        detail = build_representative_moment_detail(source, data)
        self.assertFalse(detail.sequence_supported)
        self.assertEqual(detail.focal_event.event_type, "Goal Keeper")
        self.assertFalse(detail.focal_event.pitch_renderable)

    def test_turnover_to_shot_detail_preserves_cross_possession_bounded_link(self):
        data = bundle([
            {"event_id": "turnover", "event_index": 1, "elapsed_seconds": 100.0, "possession_id": 7, "event_type": "Miscontrol", "location_x": 60, "location_y": 40},
            {"event_id": "counter-pass", "event_index": 2, "elapsed_seconds": 103.0, "possession_id": 8, "possession_team_id": 2, "team_id": 2, "event_type": "Pass", "location_x": 45, "location_y": 40, "end_location_x": 80, "end_location_y": 40},
            {"event_id": "linked-shot", "event_index": 3, "elapsed_seconds": 109.0, "possession_id": 8, "possession_team_id": 2, "team_id": 2, "event_type": "Shot", "location_x": 105, "location_y": 40, "shot_xg": .2},
            {"event_id": "unlinked", "event_index": 4, "elapsed_seconds": 110.0, "possession_id": 8, "possession_team_id": 2},
        ])
        source = replace(
            moment("turnover"), family="turnover_to_shot",
            metric="turnovers_leading_to_shot_per90", event_type="Miscontrol",
            relevant_values={
                "linked_sequence_event_ids": ("turnover", "counter-pass", "linked-shot"),
                "shot_event_id": "linked-shot",
            },
        )
        detail = build_representative_moment_detail(source, data)
        self.assertEqual(detail.context_mode, "turnover_to_shot_window")
        self.assertEqual(
            [event.event_id for event in detail.sequence_events],
            ["turnover", "counter-pass", "linked-shot"],
        )
        self.assertEqual(detail.sequence_events[-1].event_type, "Shot")


if __name__ == "__main__":
    unittest.main()
