"""Subset-denominator and fail-closed tests for pattern/360 summaries."""

import unittest
from types import SimpleNamespace

from src.analysis import RepresentativeMoment, build_moment_patterns, build_pattern_context_summaries


def event_moment(event_id: str, match_id: int) -> RepresentativeMoment:
    return RepresentativeMoment(
        match_id=match_id, team_id=1, team_name="A", opponent_id=2, opponent_name="B",
        match_date="2016-01-01", minute=1, second=0, period=1, event_id=event_id,
        event_type="Pass", metric="passes_into_penalty_area_per90", family="penalty_area_entries",
        description="Entry.", relevant_values={
            "start_coordinates": [90.0, 40.0], "end_coordinates": [105.0, 10.0],
            "play_pattern": "Regular Play",
        }, score_state="drawing", score_state_verified=True, score_state_team_id=1,
        score_state_team_name="A", source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable", reason_selected="example",
        evidence_side="attacking_production",
    )


def context(value: float, *, available=True, mode="event_plus_360_snapshot", nearest=None):
    return SimpleNamespace(
        available=available, spatial_context_mode=mode,
        visible_opponent_count=value,
        nearest_opponent_distance=value if nearest is None else nearest,
        opponents_within_radius={"5.0": int(value), "10.0": int(value + 1), "15.0": int(value + 2)},
        visible_teammates_in_penalty_area=value + 1,
        visible_opponents_in_penalty_area=value,
        visible_player_width_range=value * 2,
        visible_player_depth_range=value * 3,
    )


class PatternContextComparisonTests(unittest.TestCase):
    def setUp(self):
        self.moments = tuple(event_moment(f"e{index}", 10 + index) for index in range(1, 5))
        self.patterns = build_moment_patterns("priority", self.moments)

    def test_event_and_360_denominators_remain_separate(self):
        result = build_pattern_context_summaries(
            self.patterns, self.moments, {"e1": context(1), "e2": context(3)},
            minimum_360_sample=2,
        )[0]
        self.assertEqual(result.full_event_sample_count, 4)
        self.assertEqual(result.snapshot_360_subset_count, 2)
        self.assertEqual(result.snapshot_360_coverage, .5)
        self.assertEqual(result.full_eligible_event_sample_count, 4)

    def test_subset_wording_never_emits_season_wide_spatial_claim(self):
        result = build_pattern_context_summaries(
            self.patterns, self.moments, {"e1": context(1), "e2": context(3)},
            minimum_360_sample=2,
        )[0]
        self.assertTrue(result.scope_statement.startswith("Among 2 360-observed examples"))
        self.assertNotIn("usually", result.scope_statement.lower())
        self.assertTrue(any("must not be extrapolated" in item for item in result.limitations))

    def test_low_coverage_fails_closed_without_spatial_summary(self):
        result = build_pattern_context_summaries(
            self.patterns, self.moments, {"e1": context(1)}, minimum_360_sample=2,
        )[0]
        self.assertFalse(result.spatial_summary_available)
        self.assertEqual(result.metric_summaries, ())
        self.assertIn("no spatial summary is generated", result.scope_statement)

    def test_missing_360_never_changes_event_pattern_count(self):
        without = build_pattern_context_summaries(self.patterns, self.moments, {}, minimum_360_sample=1)[0]
        with_one = build_pattern_context_summaries(
            self.patterns, self.moments, {"e1": context(1)}, minimum_360_sample=1,
        )[0]
        self.assertEqual(without.full_event_sample_count, with_one.full_event_sample_count)
        self.assertEqual(without.event_sample_share, with_one.event_sample_share)

    def test_metric_aggregation_is_deterministic_and_capability_aware(self):
        contexts = {
            "e1": context(1), "e2": context(3), "e3": context(5),
            "e4": context(100, mode="continuous_tracking"),
        }
        first = build_pattern_context_summaries(self.patterns, self.moments, contexts, minimum_360_sample=3)[0]
        second = build_pattern_context_summaries(self.patterns, self.moments, contexts, minimum_360_sample=3)[0]
        self.assertEqual(first, second)
        self.assertEqual(first.snapshot_360_subset_count, 3)
        opponents = next(metric for metric in first.metric_summaries if metric.metric == "visible_opponent_count")
        self.assertEqual((opponents.q25, opponents.median, opponents.q75), (2.0, 3.0, 4.0))
        self.assertEqual(opponents.sample_count, 3)
        self.assertTrue(first.capability_provenance["continuous_tracking_used"] is False)

    def test_metric_missingness_uses_360_subset_as_coverage_denominator(self):
        missing = context(1)
        missing.nearest_opponent_distance = None
        result = build_pattern_context_summaries(
            self.patterns, self.moments, {"e1": missing, "e2": context(3)}, minimum_360_sample=2,
        )[0]
        nearest = next(metric for metric in result.metric_summaries if metric.metric == "nearest_opponent_distance")
        self.assertEqual(nearest.sample_count, 1)
        self.assertEqual(nearest.coverage, .5)


if __name__ == "__main__":
    unittest.main()
