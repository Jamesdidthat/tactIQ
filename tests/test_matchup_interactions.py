"""Directional interaction geometry over compact event Team Profiles."""

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.analysis import aggregate_event_team_match_metrics, analyze_matchup_interactions
from src.api.event_profile_service import load_event_profile_artifact
from src.api.opponent_comparison_service import OpponentComparisonService


def profile(team_id: int, name: str, *, attack_level: float, exposure_level: float, incomplete=False):
    rows = []
    for index in range(20):
        variation = (index % 5 - 2) * .25
        shots = attack_level + variation
        rows.append({
            "provider": "statsbomb_open_data", "match_id": team_id * 100 + index,
            "team_id": team_id, "match_minutes": 90.0, "coordinate_system": "statsbomb_120x80",
            "passes_into_penalty_area_per90": attack_level + variation,
            "shots": shots, "shots_per90": shots, "xg": shots * .12, "xg_per90": shots * .12,
            "high_regains_per90": attack_level * .8 + variation,
            "counter_attack_shots_per90": attack_level * .1 + variation * .1,
            "set_play_shots_per90": attack_level * .3 + variation,
            "passes_into_penalty_area_conceded_per90": exposure_level + variation,
            "shots_conceded_per90": exposure_level + variation,
            "xg_conceded_per90": exposure_level * .08 + variation * .05,
            "xg_per_shot_conceded": .08 + variation * .003,
            "turnovers_leading_to_shot_per90": exposure_level * .1 + variation * .05,
            "counter_attack_shots_conceded_per90": exposure_level * .04 + variation * .03,
            "set_play_shots_conceded_per90": exposure_level * .2 + variation,
        })
    if incomplete:
        for row in rows[9:]:
            row["shots_conceded_per90"] = np.nan
    return aggregate_event_team_match_metrics(
        pd.DataFrame(rows), team_id=team_id, team_name=name,
        competition_id=11, season_id=27,
    )


class MatchupInteractionTests(unittest.TestCase):
    def test_both_directions_are_distinct_and_fully_auditable(self):
        result = analyze_matchup_interactions(
            profile(1, "Alpha", attack_level=18, exposure_level=7),
            profile(2, "Beta", attack_level=13, exposure_level=9),
        )
        self.assertEqual(len(result.interactions), 14)
        self.assertEqual(result.interactions.direction_id.nunique(), 2)
        self.assertFalse(result.interactions.duplicated(["direction_id", "interaction_family"]).any())
        row = result.interactions.loc[
            result.interactions.direction_id.eq("1_attack_vs_2_defence")
            & result.interactions.interaction_family.eq("penalty_area_access")
        ].iloc[0]
        self.assertAlmostEqual(row.signed_mismatch, row.attacking_median - row.defending_exposure_median)
        self.assertFalse(row.distributions_materially_overlap)
        self.assertGreater(row.combined_standardized_mismatch, 1)
        self.assertGreaterEqual(row.interaction_strength_score, 0)
        self.assertLessEqual(row.interaction_strength_score, 1)

    def test_findings_require_clear_mismatch_and_do_not_recommend(self):
        result = analyze_matchup_interactions(
            profile(1, "Alpha", attack_level=18, exposure_level=7),
            profile(2, "Beta", attack_level=13, exposure_level=9),
        )
        self.assertTrue(result.findings)
        for direction, findings in pd.Series(result.findings).groupby(lambda index: result.findings[index].direction_id):
            ranks = [item.rank_within_direction for item in findings]
            self.assertEqual(ranks, list(range(1, len(ranks) + 1)), direction)
        combined = " ".join(f"{item.title} {item.description}" for item in result.findings).lower()
        self.assertNotIn("should", combined)
        self.assertNotIn("weakness", combined)
        self.assertNotIn("will win", combined)

    def test_low_coverage_exposure_is_excluded_in_only_affected_direction(self):
        result = analyze_matchup_interactions(
            profile(1, "Alpha", attack_level=18, exposure_level=7),
            profile(2, "Beta", attack_level=13, exposure_level=9, incomplete=True),
        )
        excluded = result.excluded_interactions
        affected = excluded.loc[
            excluded.direction_id.eq("1_attack_vs_2_defence")
            & excluded.interaction_family.eq("shot_volume")
        ]
        self.assertEqual(len(affected), 1)
        self.assertIn("fewer than 10", affected.reason.iloc[0])
        reverse = result.interactions.loc[
            result.interactions.direction_id.eq("2_attack_vs_1_defence")
            & result.interactions.interaction_family.eq("shot_volume")
        ]
        self.assertEqual(len(reverse), 1)

    def test_real_profiles_supply_all_interaction_families(self):
        artifacts = Path(__file__).resolve().parents[1] / "artifacts"
        barcelona = load_event_profile_artifact(artifacts / "statsbomb_barcelona_2015_2016_event_profile_v1.json")
        real_madrid = load_event_profile_artifact(artifacts / "statsbomb_real_madrid_2015_2016_event_profile_v1.json")
        result = analyze_matchup_interactions(barcelona, real_madrid)
        self.assertEqual(len(result.interactions), 14)
        self.assertTrue(result.excluded_interactions.empty)
        self.assertEqual(len(result.findings), 7)
        self.assertEqual({item.direction_id for item in result.findings}, {"217_attack_vs_220_defence", "220_attack_vs_217_defence"})
        unsupported = result.interactions.loc[
            result.interactions.interaction_family.eq("high_regain_turnover_exposure")
        ]
        self.assertEqual(set(unsupported.review_priority_compatibility), {"unsupported_cross_metric"})
        self.assertTrue(unsupported.combined_standardized_mismatch.isna().all())
        self.assertTrue(unsupported.interaction_strength_score.isna().all())

    def test_api_resources_are_json_safe(self):
        profiles = {
            "1": profile(1, "Alpha", attack_level=18, exposure_level=7),
            "2": profile(2, "Beta", attack_level=13, exposure_level=9),
        }
        service = OpponentComparisonService(lambda provider, team, competition, season: profiles[str(team)])
        identity = ("statsbomb_open_data", 1, 11, 27, "statsbomb_open_data", 2, 11, 27)
        payload = {
            "interactions": service.interactions(*identity),
            "findings": service.interaction_findings(*identity),
        }
        self.assertEqual(len(payload["interactions"]["directional_interactions"]), 14)
        self.assertTrue(payload["findings"]["ranked_interaction_findings"])
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
