"""Alignment, visibility, affiliation, and fallback tests for 360 context."""

import unittest

import pandas as pd

from src.analysis import RepresentativeMoment, build_moment_360_context, build_representative_moment_detail
from src.data import CanonicalMatchBundle, ProviderCapabilities


def make_moment(event_id="focal", start=(100.0, 40.0)) -> RepresentativeMoment:
    return RepresentativeMoment(
        match_id=10, team_id=1, team_name="A", opponent_id=2, opponent_name="B",
        match_date="2016-01-01", minute=1, second=0, period=1, event_id=event_id,
        event_type="Shot", metric="shots_per90", family="shots", description="Shot.",
        relevant_values={"start_coordinates": start, "end_coordinates": [120.0, 40.0], "xg": .1},
        score_state="drawing", score_state_verified=True, score_state_team_id=1,
        score_state_team_name="A", source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable_in_statsbomb_open_data",
        reason_selected="typical_match_example", evidence_side="attacking_production",
    )


def make_bundle(snapshot_rows=None, *, has_360=True) -> CanonicalMatchBundle:
    event = {
        "match_id": 10, "event_id": "focal", "event_index": 1, "period": 1,
        "timestamp": "00:01:00.000", "minute": 1, "second": 0, "elapsed_seconds": 60.0,
        "team_id": 1, "player_id": 11, "event_type": "Shot", "is_shot": True,
        "possession_id": 2, "possession_team_id": 1, "location_x": 100.0, "location_y": 40.0,
        "end_location_x": 120.0, "end_location_y": 40.0, "pass_outcome": None,
        "outcome": None, "shot_outcome": "Saved", "shot_type": "Open Play", "shot_xg": .1,
        "play_pattern": "Regular Play", "coordinate_system": "statsbomb_120x80", "attributes": {},
    }
    columns = [
        "match_id", "event_id", "snapshot_player_index", "teammate", "actor", "keeper",
        "location_x", "location_y", "visible_area", "coordinate_system",
    ]
    snapshots = None if not has_360 else pd.DataFrame(snapshot_rows or [], columns=columns)
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
        capabilities=ProviderCapabilities(False, False, False, False, True, False, has_360_snapshots=has_360),
        events=pd.DataFrame([event]), event_snapshots=snapshots,
    )


def snapshot(index, teammate, actor, x, y, *, visible_area=None, coordinate_system="statsbomb_120x80"):
    return {
        "match_id": 10, "event_id": "focal", "snapshot_player_index": index,
        "teammate": teammate, "actor": actor, "keeper": False,
        "location_x": x, "location_y": y,
        "visible_area": visible_area or [90, 20, 120, 20, 120, 60, 90, 60],
        "coordinate_system": coordinate_system,
    }


class Moment360ContextTests(unittest.TestCase):
    def test_exact_event_alignment_and_direct_snapshot_metrics(self):
        bundle = make_bundle([
            snapshot(0, True, True, 100, 40), snapshot(1, True, False, 103, 40),
            snapshot(2, False, False, 104, 40), snapshot(3, False, False, 110, 50),
        ])
        context = build_moment_360_context(make_moment(), bundle)
        self.assertTrue(context.available)
        self.assertEqual(context.spatial_context_mode, "event_plus_360_snapshot")
        self.assertEqual((context.visible_teammate_count, context.visible_opponent_count), (2, 2))
        self.assertAlmostEqual(context.nearest_opponent_distance, 4.0)
        self.assertAlmostEqual(context.nearest_teammate_distance, 3.0)
        self.assertEqual(context.opponents_within_radius, {"5.0": 1, "10.0": 1, "15.0": 2})
        self.assertEqual(context.teammates_within_radius["5.0"], 1)
        self.assertEqual(context.visible_player_width_range, 10.0)
        self.assertEqual(context.visible_player_depth_range, 10.0)
        self.assertTrue(context.event_location_inside_visible_player_hull)
        self.assertTrue(context.event_location_inside_provider_visible_area)
        self.assertEqual(context.attacking_direction_provenance["sign"], 1)

    def test_missing_matching_freeze_frame_preserves_event_only_behavior(self):
        row = snapshot(0, True, True, 100, 40)
        row["event_id"] = "another-event"
        context = build_moment_360_context(make_moment(), make_bundle([row]))
        self.assertFalse(context.available)
        self.assertEqual(context.spatial_context_mode, "event_only")
        self.assertEqual(context.snapshot_players, ())
        self.assertIsNone(context.nearest_opponent_distance)

    def test_partial_visibility_and_unknown_affiliation_remain_explicit(self):
        context = build_moment_360_context(make_moment(), make_bundle([
            snapshot(0, True, True, 100, 40), snapshot(1, None, False, 101, 41),
        ]))
        self.assertEqual(context.visible_unknown_affiliation_count, 1)
        self.assertIsNone(context.nearest_teammate_distance)
        self.assertIsNone(context.event_location_inside_visible_player_hull)
        self.assertTrue(any("partial event-linked" in item.lower() for item in context.visibility_limitations))
        self.assertTrue(any("lacked teammate/opponent" in item for item in context.visibility_limitations))

    def test_configurable_radius_boundaries_are_inclusive(self):
        context = build_moment_360_context(make_moment(), make_bundle([
            snapshot(0, True, True, 100, 40), snapshot(1, False, False, 105, 40),
        ]), radii=(5, 7))
        self.assertEqual(context.opponents_within_radius, {"5.0": 1, "7.0": 1})

    def test_player_team_assignment_uses_only_provider_teammate_flag(self):
        context = build_moment_360_context(make_moment(), make_bundle([
            snapshot(0, True, True, 100, 40), snapshot(1, False, False, 101, 40),
        ]))
        self.assertEqual([player.affiliation for player in context.snapshot_players], ["teammate", "opponent"])

    def test_coordinate_system_and_event_coordinate_disagreement_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "coordinate systems disagree"):
            build_moment_360_context(make_moment(), make_bundle([
                snapshot(0, True, True, 100, 40, coordinate_system="other"),
            ]))
        with self.assertRaisesRegex(ValueError, "focal-event coordinates disagree"):
            build_moment_360_context(make_moment(start=(99.0, 40.0)), make_bundle([
                snapshot(0, True, True, 100, 40),
            ]))
        with self.assertRaisesRegex(ValueError, "120x80 pitch bounds"):
            build_moment_360_context(make_moment(), make_bundle([
                snapshot(0, True, True, 121, 40),
            ]))

    def test_no_360_capability_and_detail_integration_fall_back_to_event_only(self):
        bundle = make_bundle(has_360=False)
        context = build_moment_360_context(make_moment(), bundle)
        self.assertFalse(context.available)
        detail = build_representative_moment_detail(make_moment(), bundle)
        self.assertEqual(detail.moment_360_context.spatial_context_mode, "event_only")
        self.assertEqual(detail.sequence_events[0].event_id, "focal")


if __name__ == "__main__":
    unittest.main()
