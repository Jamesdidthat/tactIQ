"""Deterministic event-sequence feature, grouping, and distance tests."""

import unittest
from types import SimpleNamespace

from src.analysis import (
    RepresentativeMoment, build_moment_sequence_grouping,
    derive_moment_sequence_features, sequence_feature_distance,
)


def moment(event_id="focal", *, family="penalty_area_entries", score="drawing", verified=True, values=None, match_id=10):
    return RepresentativeMoment(
        match_id=match_id, team_id=1, team_name="A", opponent_id=2, opponent_name="B",
        match_date="2016-01-01", minute=1, second=10, period=1, event_id=event_id,
        event_type="Pass", metric="metric", family=family, description="Example.",
        relevant_values=values or {"play_pattern": "Regular Play", "shot_type": None, "shot_outcome": None},
        score_state=score, score_state_verified=verified, score_state_team_id=1,
        score_state_team_name="A", source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable", reason_selected="example", evidence_side="team_history",
    )


def event(event_id, index, relation, event_type, elapsed, *, start=None, end=None, play="Regular Play", xg=None, outcome=None):
    return SimpleNamespace(
        event_id=event_id, event_index=index, relation_to_focal=relation,
        event_type=event_type, elapsed_seconds=elapsed, start_coordinates=start,
        end_coordinates=end, play_pattern=play, xg=xg, outcome=outcome,
    )


def detail(event_id="focal", *, focal_type="Pass", start=(79.0, 10.0), end=(103.0, 18.0), previous=("Pass", "Carry"), play="Regular Play", xg=None, outcome=None):
    prior = tuple(event(f"p{index}", index, "previous", kind, 65.0 + index, start=(40.0, 40.0), end=(50.0, 40.0)) for index, kind in enumerate(previous, 1))
    focal = event(event_id, len(prior) + 1, "focal", focal_type, 70.0, start=start, end=end, play=play, xg=xg, outcome=outcome)
    return SimpleNamespace(event_id=event_id, focal_event=focal, sequence_events=(*prior, focal), context_mode="same_possession")


class MomentSequenceSimilarityTests(unittest.TestCase):
    def test_features_use_explicit_zone_boundaries_and_pre_focal_events(self):
        features = derive_moment_sequence_features("priority", moment(), detail())
        self.assertEqual(features.entry_type, "pass")
        self.assertEqual(features.start_zone, "middle_third")
        self.assertEqual(features.end_zone, "penalty_area")
        self.assertEqual(features.corridor, "central")
        self.assertEqual(features.sequence_length_events, 3)
        self.assertEqual(features.sequence_duration_seconds, 4.0)
        self.assertEqual((features.preceding_pass_count, features.preceding_carry_count), (1, 1))
        self.assertEqual(features.sequence_band, "short_sequence")
        self.assertIn("Central pass entry after a short possession sequence", features.sequence_pattern_label)

    def test_set_play_counter_shot_and_score_provenance_are_explicit(self):
        shot = moment("shot", family="shots", values={"play_pattern": "From Corner", "shot_type": "Open Play", "shot_outcome": "Saved"})
        shot_features = derive_moment_sequence_features(
            "priority", shot, detail("shot", focal_type="Shot", start=(105, 65), end=(120, 40), previous=("Pass", "Pass", "Carry"), play="From Corner", xg=.25, outcome="Saved"),
        )
        self.assertEqual(shot_features.play_context, "set_play")
        self.assertFalse(shot_features.explicit_counter)
        self.assertEqual((shot_features.shot_outcome, shot_features.shot_xg), ("Saved", .25))
        self.assertEqual(shot_features.score_state, "drawing")
        self.assertIn("Set-play wide shot", shot_features.sequence_pattern_label)

        counter = moment("counter", family="shots", verified=False, score="leading", values={"play_pattern": "From Counter"})
        counter_features = derive_moment_sequence_features("priority", counter, detail("counter", focal_type="Shot", play="From Counter"))
        self.assertTrue(counter_features.explicit_counter)
        self.assertIsNone(counter_features.score_state)

    def test_grouping_is_stable_and_reports_retrieved_denominator(self):
        moments = (
            moment("a", match_id=10), moment("b", match_id=11),
            moment("c", family="shots", match_id=12),
        )
        details = {
            "a": detail("a"), "b": detail("b"),
            "c": detail("c", focal_type="Shot", previous=(), start=(105, 40), end=(120, 40)),
        }
        first = build_moment_sequence_grouping("priority", moments, details)
        second = build_moment_sequence_grouping("priority", moments, details)
        self.assertEqual(first, second)
        repeated = next(pattern for pattern in first.patterns if pattern.count == 2)
        self.assertAlmostEqual(repeated.share_of_retrieved_moments, 2 / 3)
        self.assertEqual(repeated.contributing_matches, (10, 11))
        self.assertEqual(repeated.representative_event_ids, ("a", "b"))
        self.assertEqual(len(first.similarities), 3)

    def test_transparent_distance_orders_identical_features_before_different_features(self):
        base = derive_moment_sequence_features("priority", moment("a"), detail("a"))
        same = derive_moment_sequence_features("priority", moment("b"), detail("b"))
        different = derive_moment_sequence_features(
            "priority", moment("c", family="shots", values={"play_pattern": "From Counter"}),
            detail("c", focal_type="Shot", start=(105, 70), end=(120, 40), previous=(), play="From Counter", xg=.4),
        )
        identical_distance = sequence_feature_distance(base, same)
        different_distance = sequence_feature_distance(base, different)
        self.assertEqual(identical_distance.distance, 0.0)
        self.assertGreater(different_distance.distance, identical_distance.distance)
        self.assertIn("entry_type", different_distance.differing_categorical_features)
        self.assertIn("play_context", different_distance.differing_categorical_features)

    def test_missing_detail_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Sequence details are missing"):
            build_moment_sequence_grouping("priority", (moment(),), {})

    def test_distinct_defensive_group_signatures_have_distinct_visible_labels(self):
        moments = (
            moment("regular", family="interceptions", values={"play_pattern": "Regular Play"}),
            moment("corner", family="interceptions", values={"play_pattern": "From Corner"}),
        )
        details = {
            "regular": detail("regular", focal_type="Interception", previous=(), play="Regular Play"),
            "corner": detail("corner", focal_type="Interception", previous=(), play="From Corner"),
        }
        result = build_moment_sequence_grouping("priority", moments, details)
        labels = [pattern.pattern_label for pattern in result.patterns]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertTrue(any(label.startswith("Set-play interception") for label in labels))

    def test_neighboring_sequence_counts_merge_with_subgroup_provenance(self):
        moments = (moment("two"), moment("three"))
        details = {
            "two": detail("two", previous=("Pass", "Carry")),
            "three": detail("three", previous=("Pass", "Carry", "Pass")),
        }
        result = build_moment_sequence_grouping("priority", moments, details)
        self.assertEqual(len(result.patterns), 1)
        pattern = result.patterns[0]
        self.assertEqual(pattern.count, 2)
        self.assertEqual(len(pattern.original_subgroup_ids), 2)
        self.assertTrue(pattern.defining_features["merge_applied"])
        self.assertEqual(pattern.defining_features["sequence_length_class"], "mixed_nonzero_sequence")
        self.assertIn("after a possession sequence", pattern.pattern_label)

    def test_material_sequence_gap_and_zero_context_remain_separate(self):
        moments = (moment("none"), moment("one"), moment("six"))
        details = {
            "none": detail("none", previous=()),
            "one": detail("one", previous=("Pass",)),
            "six": detail("six", previous=("Pass",) * 6),
        }
        result = build_moment_sequence_grouping("priority", moments, details)
        self.assertEqual(len(result.patterns), 3)

    def test_merge_never_crosses_play_context_action_corridor_or_zone(self):
        moments = (
            moment("regular"),
            moment("set", values={"play_pattern": "From Corner"}),
            moment("carry"),
            moment("wide"),
            moment("different_zone"),
        )
        details = {
            "regular": detail("regular", previous=("Pass", "Carry")),
            "set": detail("set", previous=("Pass", "Carry", "Pass"), play="From Corner"),
            "carry": detail("carry", focal_type="Carry", previous=("Pass", "Carry", "Pass")),
            "wide": detail("wide", end=(103.0, 10.0), previous=("Pass", "Carry", "Pass")),
            "different_zone": detail("different_zone", start=(30.0, 10.0), previous=("Pass", "Carry", "Pass")),
        }
        result = build_moment_sequence_grouping("priority", moments, details)
        self.assertEqual(len(result.patterns), 5)
        self.assertTrue(all(len(pattern.original_subgroup_ids) == 1 for pattern in result.patterns))

    def test_merge_partition_is_input_order_invariant(self):
        moments = (moment("one"), moment("two"), moment("three"), moment("seven"))
        details = {
            item.event_id: detail(item.event_id, previous=("Pass",) * count)
            for item, count in zip(moments, (1, 2, 3, 7))
        }
        forward = build_moment_sequence_grouping("priority", moments, details)
        reverse = build_moment_sequence_grouping("priority", tuple(reversed(moments)), details)
        forward_partition = {feature.event_id: feature.sequence_pattern_id for feature in forward.features}
        reverse_partition = {feature.event_id: feature.sequence_pattern_id for feature in reverse.features}
        self.assertEqual(forward_partition, reverse_partition)

    def test_defensive_events_preserve_coarse_territorial_boundary(self):
        moments = (
            moment("own_half", family="interceptions"),
            moment("attacking_half", family="interceptions"),
        )
        details = {
            "own_half": detail(
                "own_half", focal_type="Interception", start=(55.0, 40.0),
                end=None, previous=("Pass", "Carry"),
            ),
            "attacking_half": detail(
                "attacking_half", focal_type="Interception", start=(90.0, 40.0),
                end=None, previous=("Pass", "Carry", "Pass"),
            ),
        }
        result = build_moment_sequence_grouping("priority", moments, details)
        self.assertEqual(len(result.patterns), 2)


if __name__ == "__main__":
    unittest.main()
