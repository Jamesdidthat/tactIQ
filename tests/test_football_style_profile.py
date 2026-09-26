import json
import unittest

import pandas as pd

from src.analysis import EventTeamSeasonProfile, build_football_style_profile
from src.api import EventProfileService


METRICS = {
    "possession_share_estimate": (.64, "proportion"), "passes_attempted_per90": (650, "per_90"),
    "pass_completion_rate": (.86, "proportion"), "progressive_passes_per90": (38, "per_90"),
    "progressive_carries_per90": (20, "per_90"), "passes_into_final_third_per90": (50, "per_90"),
    "passes_into_penalty_area_per90": (15, "per_90"), "shots_per90": (15, "per_90"),
    "xg_per90": (2.0, "xG_per_90"), "xg_per_shot": (.14, "xG"),
    "average_shot_distance": (17, "native_120x80_units"), "pressures_per90": (122, "per_90"),
    "interceptions_per90": (7, "per_90"), "recoveries_per90": (44, "per_90"),
    "high_regains_per90": (12, "per_90"), "passes_into_penalty_area_conceded_per90": (7, "per_90"),
    "shots_conceded_per90": (9, "per_90"), "xg_conceded_per90": (.8, "xG_per_90"),
    "turnovers_leading_to_shot_per90": (1.1, "per_90"), "counter_attack_shots_per90": (.5, "per_90"),
    "counter_attack_shots_conceded_per90": (.1, "per_90"), "set_play_shots_conceded_per90": (1.5, "per_90"),
}


def make_profile() -> EventTeamSeasonProfile:
    matches = []
    for index in range(20):
        row = {"provider": "statsbomb_open_data", "match_id": index + 1, "match_date": f"2026-01-{index + 1:02d}", "team_id": 1, "team_name": "Example FC",
               "match_minutes": 90.0, "coordinate_system": "statsbomb_120x80",
               "opponent_team_name": f"Opponent {index + 1}", "home_away": "home" if index % 2 else "away"}
        for metric, (median, _) in METRICS.items():
            row[metric] = median * (1 + ((index % 3) - 1) * .04)
        if index >= 15:
            row["progressive_passes_per90"] = 48
        matches.append(row)
    aggregates = [{"metric": metric, "median_across_matches": median, "q25_across_matches": median * .9,
                   "q75_across_matches": median * 1.1, "contributing_matches": 20, "total_matches": 20,
                   "coverage": 1.0, "unit": unit, "definition": f"Stable definition for {metric}.",
                   "coordinate_system": None} for metric, (median, unit) in METRICS.items()]
    definitions = pd.DataFrame(aggregates)[["metric", "unit", "definition"]].copy()
    return EventTeamSeasonProfile(1, "Example FC", 11, 27, pd.DataFrame(matches), pd.DataFrame(aggregates),
                                  definitions, pd.DataFrame(columns=["match_id", "reason"]), "League", "2025/26")


class FootballStyleProfileTests(unittest.TestCase):
    def test_profile_is_football_first_and_evidence_backed(self):
        result = build_football_style_profile(make_profile())
        self.assertEqual(result.schema_version, "tactiq.football-style-profile.v1")
        self.assertIn("take control with the ball", result.playing_identity)
        self.assertTrue(result.in_possession)
        self.assertTrue(result.out_of_possession)
        self.assertTrue(result.transitions)
        self.assertTrue(result.strengths)
        for concept in (*result.in_possession, *result.out_of_possession, *result.transitions):
            self.assertTrue(concept.supporting_evidence)
            self.assertNotIn("z-score", (concept.title + concept.summary).lower())
            self.assertNotIn("iqr", (concept.title + concept.summary).lower())
            self.assertTrue(concept.what_this_looks_like)
            self.assertGreaterEqual(concept.supporting_evidence[0].contributing_matches, 5)

    def test_visible_language_avoids_metric_translation_terms(self):
        result = build_football_style_profile(make_profile())
        concepts = (*result.in_possession, *result.out_of_possession, *result.transitions,
                    *result.strengths, *result.potential_weaknesses, *result.recent_style)
        visible = " ".join([result.playing_identity, *(
            part for concept in concepts for part in (concept.title, concept.summary, concept.what_this_looks_like)
        )]).lower()
        for forbidden in ("event-derived possession", "expected-goal output", "progressive passes", "distribution", "baseline", "per 90", "penalty-area access"):
            self.assertNotIn(forbidden, visible)

    def test_recent_style_is_deterministic_under_input_reordering(self):
        profile = make_profile()
        expected = build_football_style_profile(profile).recent_style
        shuffled = make_profile()
        shuffled.match_metrics = shuffled.match_metrics.sample(frac=1, random_state=4).reset_index(drop=True)
        self.assertEqual(expected, build_football_style_profile(shuffled).recent_style)

    def test_capability_limits_shape_claims(self):
        result = build_football_style_profile(make_profile())
        self.assertFalse(result.capabilities["has_continuous_tracking"])
        text = " ".join(result.limitations).lower()
        self.assertIn("compactness", text)
        self.assertIn("width", text)

    def test_at_a_glance_uses_only_supported_linked_concepts(self):
        result = build_football_style_profile(make_profile())
        concept_ids = {item.concept_id for item in (*result.in_possession, *result.out_of_possession, *result.transitions)}
        dimensions = {item.dimension_id: item for item in result.style_at_a_glance}
        self.assertEqual(set(dimensions), {
            "possession_control", "directness", "forward_progression", "penalty_area_presence",
            "shot_volume", "shot_quality", "high_ball_recovery", "counter_attacking",
        })
        self.assertTrue(all(item.level in {"Low", "Moderate", "High"} for item in dimensions.values()))
        self.assertTrue(all(item.concept_id in concept_ids for item in dimensions.values()))
        self.assertNotIn("width", dimensions)
        self.assertNotIn("defensive_height", dimensions)
        self.assertNotIn("compactness", dimensions)

    def test_at_a_glance_is_stable_under_match_reordering(self):
        expected = build_football_style_profile(make_profile()).style_at_a_glance
        shuffled = make_profile()
        shuffled.match_metrics = shuffled.match_metrics.sample(frac=1, random_state=8).reset_index(drop=True)
        self.assertEqual(expected, build_football_style_profile(shuffled).style_at_a_glance)

    def test_service_response_is_json_safe_and_cached(self):
        calls = 0
        profile = make_profile()
        def resolver(*_args):
            nonlocal calls
            calls += 1
            return profile
        service = EventProfileService(resolver)
        first = service.football_style("statsbomb_open_data", 1, 11, 27)
        second = service.football_style("statsbomb_open_data", 1, 11, 27)
        json.dumps(first, allow_nan=False)
        self.assertEqual(first, second)
        self.assertEqual(calls, 1)

    def test_invalid_recent_window_is_rejected(self):
        with self.assertRaises(ValueError):
            build_football_style_profile(make_profile(), recent_window=0)


if __name__ == "__main__":
    unittest.main()
