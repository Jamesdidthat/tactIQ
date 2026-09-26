"""Match-weighted, capability-aware Team Profile tests."""

from dataclasses import replace
import unittest

import pandas as pd

from src.analysis.team_profile import TeamProfileIdentity, build_team_profile, profile_evidence_band
from src.data import ProviderCapabilities
from tests.test_finding_prioritization import make_result
from tests.test_match_analysis_service import make_bundle


def enrich(bundle, shot_for: int, shot_against: int):
    match_id = bundle.matches.match_id.iloc[0]
    events = []
    for index in range(shot_for):
        events.append({"match_id": match_id, "event_id": f"f{index}", "period": 1, "team_id": "h", "event_type": "shot", "is_shot": True})
    for index in range(shot_against):
        events.append({"match_id": match_id, "event_id": f"a{index}", "period": 1, "team_id": "a", "event_type": "shot", "is_shot": True})
    bundle.events = pd.DataFrame(events)
    bundle.tactical_phases = pd.DataFrame([{
        "match_id": match_id, "period": 1, "frame_start": 1, "frame_end_exclusive": 21,
        "possession_team_id": "h", "attacking_phase_type": "build_up",
        "defending_phase_type": "medium_block",
    }])
    bundle.capabilities = ProviderCapabilities(True, True, True, True, True, True)
    return bundle


class TeamProfileTests(unittest.TestCase):
    def test_configurable_profile_evidence_bands(self) -> None:
        self.assertEqual(profile_evidence_band(0), "insufficient")
        self.assertEqual(profile_evidence_band(2), "insufficient")
        self.assertEqual(profile_evidence_band(3), "provisional")
        self.assertEqual(profile_evidence_band(5), "developing")
        self.assertEqual(profile_evidence_band(10), "established")
        self.assertEqual(profile_evidence_band(2, ((2, "thin"), (4, "usable"), (float("inf"), "strong"))), "usable")

    def test_match_values_are_preserved_then_summarised_across_matches(self) -> None:
        first = enrich(make_bundle("provider_one", "one"), 2, 1)
        second = enrich(make_bundle("provider_one", "two"), 4, 3)
        second.player_positions.loc[second.player_positions.player_id.eq("h_a"), "x"] += 10
        identity = TeamProfileIdentity("club", "Test Club", {"provider_one": "h"})
        empty_results = {"one": make_result([]), "two": make_result([])}
        profile = build_team_profile([first, second], identity, analysis_results=empty_results)

        self.assertEqual(len(profile.matches_included), 2)
        overall = profile.aggregate_patterns.loc[
            profile.aggregate_patterns.metric.eq("outfield_length")
            & profile.aggregate_patterns.metric_family.eq("overall_team_shape")
        ].iloc[0]
        self.assertEqual(overall.contributing_matches, 2)
        self.assertEqual(overall.evidence_band, "insufficient")
        self.assertEqual(overall.baseline_label, "two-match provisional baseline")
        match_values = profile.match_level_values.loc[
            profile.match_level_values.metric.eq("outfield_length")
            & profile.match_level_values.metric_family.eq("overall_team_shape"), "value"
        ].sort_values().tolist()
        self.assertEqual(overall.median_across_matches, pd.Series(match_values).median())
        deviations = profile.match_deviations.loc[
            profile.match_deviations.metric.eq("outfield_length")
            & profile.match_deviations.metric_family.eq("overall_team_shape")
        ]
        self.assertEqual(set(deviations.deviation_label), {"more_compact", "more_stretched"})
        self.assertAlmostEqual(deviations.deviation_from_baseline.sum(), 0.)
        self.assertTrue(deviations.contributing_matches.eq(2).all())
        self.assertTrue(deviations.comparison_label.str.contains("two-match provisional baseline").all())

    def test_phase_line_shot_and_capability_outputs_are_gated_and_traceable(self) -> None:
        bundle = enrich(make_bundle("provider_one", "one"), 2, 3)
        profile = build_team_profile(
            [bundle], TeamProfileIdentity("club", "Test Club", {"provider_one": "h"}),
            analysis_results={"one": make_result([])},
        )
        families = set(profile.match_level_values.metric_family)
        self.assertTrue({"overall_team_shape", "phase_team_shape", "defensive_line_structure", "phase_defensive_line_structure", "shot_counts"}.issubset(families))
        shots = profile.match_level_values.set_index("metric").value
        self.assertEqual(shots.shots_for, 2)
        self.assertEqual(shots.shots_conceded, 3)
        phase = profile.match_level_values.loc[profile.match_level_values.metric_family.eq("phase_team_shape")]
        self.assertEqual(set(phase.tactical_phase), {"build_up"})
        self.assertTrue(phase.required_capabilities.str.contains("has_tactical_phases").all())
        represented = profile.match_level_values.loc[profile.match_level_values.metric_family.isin(["overall_team_shape", "phase_team_shape"])]
        self.assertTrue(represented.representative_frame.notna().all())
        self.assertTrue(represented.representative_period.notna().all())
        coverage = profile.capability_coverage.set_index("capability")
        self.assertEqual(coverage.loc["has_events", "coverage"], 1.)

    def test_providers_are_never_pooled_into_one_baseline(self) -> None:
        first = make_bundle("provider_one", "one")
        second = make_bundle("provider_two", "two")
        profile = build_team_profile(
            [first, second],
            TeamProfileIdentity("club", "Test Club", {"provider_one": "h", "provider_two": "h"}),
            analysis_results={"one": make_result([]), "two": make_result([])},
        )
        overall = profile.aggregate_patterns.loc[
            profile.aggregate_patterns.metric.eq("outfield_length")
            & profile.aggregate_patterns.metric_family.eq("overall_team_shape")
        ]
        self.assertEqual(set(overall.provider), {"provider_one", "provider_two"})
        self.assertTrue(overall.contributing_matches.eq(1).all())

    def test_unmapped_or_absent_team_is_reported_not_silently_mixed(self) -> None:
        first = make_bundle("provider_one", "one")
        profile = build_team_profile(
            [first], TeamProfileIdentity("club", "Test Club", {"other_provider": "h"})
        )
        self.assertTrue(profile.matches_included.empty)
        self.assertEqual(len(profile.matches_excluded), 1)
        self.assertIn("no mapping", profile.matches_excluded.reason.iloc[0])


if __name__ == "__main__":
    unittest.main()
