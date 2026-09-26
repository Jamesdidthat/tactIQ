import json
import unittest
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.analysis import (
    aggregate_event_team_match_metrics, build_match_archetypes,
    build_metric_relationship_deviations, assemble_match_story,
    generate_event_profile_findings,
)
from src.analysis.event_team_profile import metric_definitions
from src.api import EventProfileService, load_event_profile_artifact


def make_profile():
    definitions = metric_definitions()
    rows = []
    for index in range(20):
        row = {
            "provider": "statsbomb_open_data", "match_id": 1000 + index,
            "match_date": f"2026-01-{index + 1:02d}", "competition_id": 11,
            "season_id": 27, "team_id": 217, "team_name": "Barcelona",
            "opponent_team_id": index, "opponent_team_name": f"Opponent {index}",
            "home_away": "home" if index % 2 == 0 else "away",
            "home_score": 2, "away_score": 1, "team_score": 2 if index % 2 == 0 else 1,
            "opponent_score": 1 if index % 2 == 0 else 2,
            "leading_seconds": 1800.0, "drawing_seconds": 3000.0, "trailing_seconds": 900.0,
            "leading_share": 1800 / 5700, "drawing_share": 3000 / 5700, "trailing_share": 900 / 5700,
            "score_state_source": "event_goal_timeline_verified",
            "metric_chronology": {
                "possession_share_estimate": {"first_seconds": 0.0, "median_seconds": 600.0, "last_seconds": 5600.0, "event_count": 100},
                "progressive_passes_per90": {"first_seconds": 300.0, "median_seconds": 1500.0, "last_seconds": 5400.0, "event_count": 20},
                "passes_into_penalty_area_per90": {"first_seconds": 600.0, "median_seconds": 2400.0, "last_seconds": 5200.0, "event_count": 10},
                "shots_per90": {"first_seconds": 900.0, "median_seconds": 3200.0, "last_seconds": 5100.0, "event_count": 12},
                "xg_per90": {"first_seconds": 900.0, "median_seconds": 3200.0, "last_seconds": 5100.0, "event_count": 12},
                "xg_per_shot": {"first_seconds": 900.0, "median_seconds": 3200.0, "last_seconds": 5100.0, "event_count": 12},
            },
            "match_minutes": 95.0,
            "coordinate_system": "statsbomb_120x80",
        }
        for definition in definitions.itertuples(index=False):
            row[definition.metric] = 10.0 + (index % 4)
        row["possession_share_estimate"] = .60 + (index % 4) * .01
        row["pass_completion_rate"] = .84 + (index % 4) * .005
        row["progressive_passes_per90"] = 20.0 + index % 4
        row["passes_into_final_third_per90"] = 40.0 + 2 * (index % 4)
        rows.append(row)
    rows[-1]["progressive_passes_per90"] = 50.0
    rows[-1]["passes_into_final_third_per90"] = 100.0
    rows[-1]["xg_per90"] = 50.0
    rows[-2]["possession_share_estimate"] = .80
    rows[-2]["progressive_passes_per90"] = 5.0
    rows[-2]["passes_into_penalty_area_per90"] = 40.0
    rows[-2]["shots_per90"] = 1.0
    return aggregate_event_team_match_metrics(
        pd.DataFrame(rows), team_id=217, team_name="Barcelona",
        competition_id=11, season_id=27,
    )


class EventProfileFindingTests(unittest.TestCase):
    def test_robust_findings_are_grounded_and_duplicates_suppressed(self):
        result = generate_event_profile_findings(make_profile())
        self.assertTrue(result.findings)
        progressive = [item for item in result.findings if item.source_match_id == 1019 and item.finding_family == "progression"]
        self.assertEqual(len(progressive), 1)
        finding = progressive[0]
        self.assertEqual(finding.contributing_match_count, 20)
        self.assertEqual(finding.coverage, 1.0)
        self.assertGreater(finding.observed_value, finding.season_baseline)
        self.assertGreater(finding.absolute_deviation, 0)
        self.assertNotIn("good", finding.title.lower())
        self.assertFalse(result.suppressed_duplicates.empty)
        self.assertEqual(len(result.deviations.match_id.unique()), 20)

    def test_product_service_is_json_safe_and_cached(self):
        calls = 0
        profile = make_profile()

        def resolver(provider, team_id, competition_id, season_id):
            nonlocal calls
            calls += 1
            return profile

        service = EventProfileService(resolver)
        outputs = [
            service.summary("statsbomb_open_data", 217, 11, 27),
            service.baselines("statsbomb_open_data", 217, 11, 27),
            service.findings("statsbomb_open_data", 217, 11, 27),
            service.tendencies("statsbomb_open_data", 217, 11, 27),
            service.unusual_matches("statsbomb_open_data", 217, 11, 27),
            service.archetypes("statsbomb_open_data", 217, 11, 27),
            service.relationships("statsbomb_open_data", 217, 11, 27),
            service.matches("statsbomb_open_data", 217, 11, 27),
            service.match_story("statsbomb_open_data", 217, 11, 27, 1018),
        ]
        for output in outputs:
            json.dumps(output, allow_nan=False)
            self.assertEqual(output["schema_version"], "v1")
        self.assertEqual(calls, 1)
        self.assertEqual(outputs[0]["analysed_match_count"], 20)
        self.assertEqual(outputs[-3]["total_matches"], 20)
        self.assertEqual(len(outputs[-2]["matches"]), 20)
        self.assertEqual(outputs[-2]["matches"][0]["match_id"], 1000)
        self.assertLessEqual(len(outputs[-1]["story_points"]), 4)
        self.assertEqual(outputs[-1]["maximum_story_points"], 4)
        self.assertIn("match_context", outputs[-1])

    def test_archetypes_are_transparent_multi_label_and_match_weighted(self):
        result = build_match_archetypes(make_profile())
        match = [item for item in result.assignments if item.match_id == 1018]
        labels = {item.archetype for item in match}
        self.assertIn("high_possession_low_progression", labels)
        self.assertIn("high_penalty_area_access_low_shot_output", labels)
        self.assertGreaterEqual(len(labels), 2)
        for assignment in match:
            self.assertEqual(len(assignment.contributing_metrics), 2)
            self.assertTrue(all(component["contributing_match_count"] == 20 for component in assignment.contributing_metrics))
            self.assertTrue(all(component["coverage"] == 1.0 for component in assignment.contributing_metrics))
        summary = result.season_summary.set_index("archetype")
        self.assertGreater(summary.loc["high_possession_low_progression", "match_count"], 0)
        self.assertIn(1018, summary.loc["high_possession_low_progression", "representative_match_ids"])

    def test_archetype_fails_closed_when_component_coverage_is_low(self):
        profile = make_profile()
        profile.match_metrics.loc[:4, "progressive_passes_per90"] = pd.NA
        result = build_match_archetypes(profile)
        progression_rules = {"high_possession_low_progression", "high_progression_high_chance_creation"}
        self.assertFalse(any(item.archetype in progression_rules for item in result.assignments))

    def test_robust_relationship_recovers_slope_and_flags_residual(self):
        profile = make_profile()
        x = pd.Series([.50 + index * .01 for index in range(20)])
        noise = pd.Series([-1., 0., 1., 0.] * 5)
        profile.match_metrics["possession_share_estimate"] = x
        profile.match_metrics["progressive_passes_per90"] = 10 + 50 * x + noise
        profile.match_metrics.loc[19, "progressive_passes_per90"] += 15
        result = build_metric_relationship_deviations(profile)
        fit = result.relationship_fits.loc[
            result.relationship_fits.upstream_metric.eq("possession_share_estimate")
            & result.relationship_fits.downstream_metric.eq("progressive_passes_per90")
        ].iloc[0]
        self.assertAlmostEqual(fit.slope, 50.0, delta=3.0)
        finding = next(item for item in result.findings if item.match_id == 1019 and item.downstream_metric == "progressive_passes_per90")
        self.assertGreater(finding.observed_downstream_value, finding.expected_downstream_value)
        self.assertGreater(finding.residual_robust_z, 2.0)
        self.assertEqual(finding.contributing_match_count, 20)

    def test_relationship_fails_closed_below_coverage_threshold(self):
        profile = make_profile()
        profile.match_metrics.loc[:4, "progressive_passes_per90"] = pd.NA
        result = build_metric_relationship_deviations(profile)
        pair = result.relationship_fits.loc[
            result.relationship_fits.upstream_metric.eq("possession_share_estimate")
            & result.relationship_fits.downstream_metric.eq("progressive_passes_per90")
        ]
        self.assertTrue(pair.empty)

    def test_match_story_is_deterministic_diverse_and_grounded(self):
        profile = make_profile()
        first = assemble_match_story(profile, 1018)
        second = assemble_match_story(profile, 1018)
        self.assertEqual([asdict(item) for item in first.story_points], [asdict(item) for item in second.story_points])
        self.assertLessEqual(len(first.story_points), 4)
        self.assertGreaterEqual(len(first.story_points), 1)
        self.assertEqual(len({item.redundancy_group for item in first.story_points}), len(first.story_points))
        topic_order = {"possession_circulation": 0, "progression": 1, "territorial_access": 2, "shot_quantity": 3, "chance_creation": 4, "shot_quality": 4}
        story_order = [topic_order[item.semantic_topic] for item in first.story_points]
        self.assertEqual(story_order, sorted(story_order))
        self.assertEqual(len({item.semantic_topic for item in first.story_points}), len(first.story_points))
        progression = next(item for item in first.story_points if item.semantic_topic == "progression")
        self.assertGreaterEqual(len(progression.merged_candidate_ids), 2)
        for item in first.story_points:
            self.assertEqual(item.source_match_id, 1018)
            self.assertTrue(item.supporting_metrics)
            self.assertEqual(item.contributing_season_match_count, 20)
            self.assertEqual(item.coverage, 1.0)
            self.assertTrue(item.limitations)
            self.assertTrue(item.chronology["available"])
            self.assertIn(item.evidence_basis, {"High", "Moderate", "Limited"})
        self.assertEqual(first.match_context["opponent_team_name"], "Opponent 18")
        self.assertEqual(first.match_context["home_away"], "home")
        self.assertEqual(first.match_context["team_relative_score"], "2–1")

    def test_match_story_does_not_pad_weak_or_absent_evidence(self):
        result = assemble_match_story(make_profile(), 1000)
        self.assertLess(len(result.story_points), 3)
        self.assertEqual(result.story_points, [])
        self.assertEqual(result.status, "no_qualifying_patterns")
        self.assertEqual(result.message, "No unusual season-relative patterns qualified. This does not mean the match lacked important events.")

    def test_equal_stage_topics_use_event_chronology_as_ordering_tiebreak(self):
        profile = make_profile()
        index = profile.match_metrics.index[profile.match_metrics.match_id.eq(1019)][0]
        profile.match_metrics.loc[index, "shots_on_target_per90"] = 50.0
        chronology = dict(profile.match_metrics.at[index, "metric_chronology"])
        chronology["shots_on_target_per90"] = {
            "first_seconds": 100.0, "median_seconds": 1000.0,
            "last_seconds": 2000.0, "event_count": 5,
        }
        profile.match_metrics.at[index, "metric_chronology"] = chronology
        result = assemble_match_story(profile, 1019)
        final_stage = [
            point for point in result.story_points
            if point.semantic_topic in {"shot_quantity", "shot_quality", "chance_creation"}
        ]
        self.assertGreaterEqual(len(final_stage), 2)
        medians = [point.chronology["median_seconds"] for point in final_stage]
        self.assertEqual(medians, sorted(medians))

    def test_default_story_cap_is_four_and_context_is_descriptive(self):
        result = assemble_match_story(make_profile(), 1018)
        self.assertEqual(result.maximum_story_points, 4)
        self.assertLessEqual(len(result.story_points), 4)
        self.assertEqual(result.match_context["score_state_source"], "event_goal_timeline_verified")
        self.assertAlmostEqual(result.match_context["score_state_exposure"]["drawing"]["share"], 3000 / 5700)

    def test_real_match_coherence_and_merged_evidence_provenance_regressions(self):
        artifact = Path(__file__).resolve().parents[1] / "artifacts" / "statsbomb_barcelona_2015_2016_event_profile_v1.json"
        profile = load_event_profile_artifact(artifact)

        disconnected = assemble_match_story(profile, 267327)
        self.assertEqual(disconnected.presentation_mode, "parallel_observations")
        self.assertEqual(len(disconnected.story_points), 2)
        self.assertFalse(disconnected.coherence_linkages)

        mixed_mechanisms = assemble_match_story(profile, 266653)
        self.assertEqual(mixed_mechanisms.presentation_mode, "parallel_observations")
        self.assertEqual(len(mixed_mechanisms.story_points), 3)

        connected = assemble_match_story(profile, 266961)
        self.assertEqual(connected.presentation_mode, "connected_story")
        self.assertEqual(len(connected.story_points), 3)
        self.assertGreaterEqual(len(connected.coherence_linkages), 2)
        relationship = connected.story_points[0]
        self.assertEqual(relationship.story_type, "metric_relationship_residual")
        self.assertEqual(relationship.primary_evidence_basis, "Moderate")
        self.assertEqual(relationship.evidence_basis, "Moderate")
        self.assertEqual(relationship.evidence_level, "moderate")
        self.assertIn("High", {item["evidence_basis"] for item in relationship.supporting_evidence_bases if not item["is_primary"]})

    def test_match_story_rejects_invalid_size_and_unknown_match(self):
        profile = make_profile()
        with self.assertRaises(ValueError):
            assemble_match_story(profile, 1018, maximum_story_points=5)
        with self.assertRaises(KeyError):
            assemble_match_story(profile, 9999)


if __name__ == "__main__":
    unittest.main()
