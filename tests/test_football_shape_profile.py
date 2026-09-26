"""Football-first shape profiles stay capability-gated and frame-traceable."""

import unittest

from src.analysis import TeamProfileIdentity, build_football_shape_profile, build_team_profile
from src.data import ProviderCapabilities
from tests.test_finding_prioritization import make_result
from tests.test_match_analysis_service import make_bundle


class FootballShapeProfileTests(unittest.TestCase):
    def test_tracking_profile_uses_real_representative_frames(self) -> None:
        bundle = make_bundle("provider_one", "one")
        profile = build_team_profile(
            [bundle], TeamProfileIdentity("club", "Test Club", {"provider_one": "h"}),
            analysis_results={"one": make_result([])},
        )
        shape = build_football_shape_profile(profile)
        self.assertTrue(shape.available)
        self.assertTrue(shape.with_ball)
        observed = set(zip(bundle.player_positions.frame.astype(int), bundle.player_positions.period.astype(int)))
        for concept in (*shape.with_ball, *shape.without_ball):
            for reference in concept.representative_frames:
                self.assertIn((reference.frame, reference.period), observed)
                self.assertGreater(reference.clip_before_seconds + reference.clip_after_seconds, 5)
                self.assertTrue(reference.clip_reason)
            self.assertTrue(all(item.provider == "provider_one" for item in concept.evidence))
        self.assertFalse(shape.transitions)
        self.assertIn("generic transition retreat/advance speed", shape.unsupported_concepts)

    def test_event_only_profile_fails_closed_with_exact_product_message(self) -> None:
        bundle = make_bundle("event_provider", "one")
        bundle.capabilities = ProviderCapabilities(False, False, False, False, False, False)
        bundle.player_positions = bundle.player_positions.iloc[0:0]
        bundle.ball_positions = bundle.ball_positions.iloc[0:0]
        profile = build_team_profile(
            [bundle], TeamProfileIdentity("club", "Test Club", {"event_provider": "h"}),
            analysis_results={"one": make_result([])},
        )
        shape = build_football_shape_profile(profile)
        self.assertFalse(shape.available)
        self.assertEqual(shape.availability_message, "Detailed team shape requires tracking data")
        self.assertFalse(shape.with_ball)
        self.assertFalse(shape.without_ball)


if __name__ == "__main__":
    unittest.main()
