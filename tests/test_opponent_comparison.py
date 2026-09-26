"""Correctness and product-contract tests for pre-match opponent comparisons."""

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.analysis import aggregate_event_team_match_metrics, compare_event_team_profiles
from src.api.opponent_comparison_service import OpponentComparisonService
from src.api.event_profile_service import load_event_profile_artifact


def make_profile(team_id: int, name: str, *, opponent: bool = False, provider: str = "statsbomb_open_data"):
    rows = []
    for index in range(20):
        variation = (index % 5 - 2) / 2
        shots = (17 if opponent else 14) + variation
        xg_per_shot = .12 if opponent else .13
        rows.append({
            "provider": provider, "match_id": team_id * 1000 + index, "team_id": team_id,
            "match_minutes": 90.0, "coordinate_system": "statsbomb_120x80",
            "possession_share_estimate": (.44 if opponent else .61) + variation * .008,
            "passes_attempted_per90": (410 if opponent else 610) + variation * 12,
            "pass_completion_rate": (.79 if opponent else .89) + variation * .006,
            "progressive_passes_per90": (49 if opponent else 36) + variation,
            "passes_into_final_third_per90": (48 if opponent else 34) + variation,
            "passes_into_penalty_area_per90": (19 if opponent else 10) + variation * .5,
            "shots": shots, "shots_per90": shots,
            "shots_on_target_per90": (6 if opponent else 5) + variation * .3,
            "xg": shots * xg_per_shot, "xg_per90": shots * xg_per_shot,
            "average_shot_distance": (19 if opponent else 17) + variation * .4,
            "pressures_per90": 105 + variation * 8 + (1 if opponent else 0),
            "tackles_per90": 18 + variation,
            "interceptions_per90": 9 + variation * .5,
            "recoveries_per90": 47 + variation * 2,
            "high_regains_per90": (12 + variation) if index < 9 else np.nan,
            "turnovers_leading_to_shot_per90": (3.0 if opponent else 1.0) + variation * .15,
            "counter_attack_shots_per90": (2.0 if opponent else .4) + variation * .1,
        })
    return aggregate_event_team_match_metrics(
        pd.DataFrame(rows), team_id=team_id, team_name=name,
        competition_id=11, season_id=27,
    )


class OpponentComparisonTests(unittest.TestCase):
    def test_comparison_uses_match_distributions_and_explicit_sign(self):
        result = compare_event_team_profiles(make_profile(1, "Target"), make_profile(2, "Opponent", opponent=True))
        penalty = result.metric_comparisons.set_index("metric").loc["passes_into_penalty_area_per90"]
        self.assertAlmostEqual(penalty.signed_difference, penalty.opponent_median - penalty.target_median)
        self.assertAlmostEqual(penalty.absolute_difference, abs(penalty.signed_difference))
        self.assertAlmostEqual(penalty.relative_difference, penalty.signed_difference / penalty.target_median)
        self.assertGreater(penalty.standardized_by_target_variability, 1.0)
        self.assertGreater(penalty.standardized_by_opponent_variability, 1.0)
        self.assertFalse(penalty.distributions_materially_overlap)
        self.assertEqual(penalty.difference_sign_convention, "opponent_minus_target")

    def test_quality_filter_and_clear_contrast_findings_fail_closed(self):
        result = compare_event_team_profiles(make_profile(1, "Target"), make_profile(2, "Opponent", opponent=True))
        excluded = result.excluded_metrics.set_index("metric")
        self.assertIn("high_regains_per90", excluded.index)
        self.assertIn("fewer than 10", excluded.loc["high_regains_per90", "reason"])
        self.assertTrue(all(not finding.distributions_materially_overlap for finding in result.findings))
        self.assertEqual(len({finding.finding_family for finding in result.findings}), len(result.findings))
        self.assertEqual([finding.rank for finding in result.findings], list(range(1, len(result.findings) + 1)))
        penalty = next(finding for finding in result.findings if finding.metric == "passes_into_penalty_area_per90")
        self.assertIn("typically enters the penalty area more frequently", penalty.title)
        self.assertNotIn("should", penalty.description.lower())
        self.assertNotIn("recommend", penalty.description.lower())

    def test_provider_and_identity_compatibility_are_enforced(self):
        target = make_profile(1, "Target")
        with self.assertRaisesRegex(ValueError, "different team-season"):
            compare_event_team_profiles(target, target)
        with self.assertRaisesRegex(ValueError, "Provider contexts differ"):
            compare_event_team_profiles(target, make_profile(2, "Opponent", opponent=True, provider="other_provider"))

    def test_product_service_is_json_safe_cached_and_split_by_resource(self):
        profiles = {"1": make_profile(1, "Target"), "2": make_profile(2, "Opponent", opponent=True)}
        calls = []

        def resolver(provider, team_id, competition_id, season_id):
            calls.append((provider, str(team_id), str(competition_id), str(season_id)))
            return profiles[str(team_id)]

        service = OpponentComparisonService(resolver)
        identity = ("statsbomb_open_data", 1, 11, 27, "statsbomb_open_data", 2, 11, 27)
        summary = service.summary(*identity)
        metrics = service.metrics(*identity)
        findings = service.findings(*identity)
        self.assertTrue(summary["compatibility"]["comparable"])
        self.assertEqual(summary["compared_metric_count"], len(metrics["metric_comparisons"]))
        self.assertEqual(summary["finding_count"], len(findings["ranked_comparison_findings"]))
        self.assertEqual(len(calls), 2)
        json.dumps({"summary": summary, "metrics": metrics, "findings": findings}, allow_nan=False)

    def test_real_barcelona_real_madrid_profiles_are_fully_comparable(self):
        artifacts = Path(__file__).resolve().parents[1] / "artifacts"
        target = load_event_profile_artifact(artifacts / "statsbomb_barcelona_2015_2016_event_profile_v1.json")
        opponent = load_event_profile_artifact(artifacts / "statsbomb_real_madrid_2015_2016_event_profile_v1.json")
        result = compare_event_team_profiles(target, opponent)
        self.assertEqual(result.target["analysed_match_count"], 38)
        self.assertEqual(result.opponent["analysed_match_count"], 38)
        self.assertEqual(len(result.metric_comparisons), 19)
        self.assertTrue(result.excluded_metrics.empty)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].metric, "interceptions_per90")


if __name__ == "__main__":
    unittest.main()
