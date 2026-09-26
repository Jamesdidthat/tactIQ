"""Deterministic pre-match review shortlist tests."""

import json
from pathlib import Path
import unittest

from src.analysis import (
    analyze_matchup_interactions,
    build_pre_match_review_priorities,
    compare_event_team_profiles,
    generate_event_profile_findings,
    ReviewPriorityEvidenceCompatibility,
    build_metric_review_question,
)
from src.api import artifact_event_profile_resolver, load_event_profile_artifact
from src.api.opponent_comparison_service import OpponentComparisonService


class PreMatchReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1] / "artifacts"
        cls.barcelona = load_event_profile_artifact(root / "statsbomb_barcelona_2015_2016_event_profile_v1.json")
        cls.real_madrid = load_event_profile_artifact(root / "statsbomb_real_madrid_2015_2016_event_profile_v1.json")

    def build(self, **options):
        comparison = compare_event_team_profiles(self.barcelona, self.real_madrid)
        interactions = analyze_matchup_interactions(self.barcelona, self.real_madrid)
        target = generate_event_profile_findings(self.barcelona).recurring_tendencies
        opponent = generate_event_profile_findings(self.real_madrid).recurring_tendencies
        return build_pre_match_review_priorities(
            comparison, interactions,
            target_recurring_tendencies=target,
            opponent_recurring_tendencies=opponent,
            **options,
        )

    def test_shortlist_is_capped_ranked_and_deterministic(self):
        first, second = self.build(), self.build()
        self.assertGreaterEqual(len(first.priorities), 3)
        self.assertLessEqual(len(first.priorities), 5)
        self.assertEqual(first.priorities, second.priorities)
        self.assertEqual([item.rank for item in first.priorities], list(range(1, len(first.priorities) + 1)))
        self.assertEqual(len({item.priority_id for item in first.priorities}), len(first.priorities))

    def test_direction_provenance_and_contract_evidence_are_preserved(self):
        result = self.build()
        directions = {item.direction for item in result.priorities}
        self.assertIn("target_attack_vs_opponent_defence", directions)
        self.assertIn("opponent_attack_vs_target_defence", directions)
        for item in result.priorities:
            self.assertTrue(item.primary_evidence)
            self.assertTrue(item.target_baseline)
            self.assertTrue(item.opponent_baseline)
            self.assertTrue(item.source_finding_ids)
            self.assertTrue(item.selection_reason)
            self.assertGreaterEqual(item.priority_score, result.configuration["minimum_priority_score"])
            self.assertEqual(str(item.target_baseline["team_id"]), str(result.target["team_id"]))
            self.assertEqual(str(item.opponent_baseline["team_id"]), str(result.opponent["team_id"]))

    def test_semantic_duplicates_are_suppressed_and_retained_as_support(self):
        directory = Path(__file__).resolve().parents[1] / "artifacts" / "event_profiles" / "statsbomb_11_27"
        sporting = load_event_profile_artifact(directory / "statsbomb_11_27_1041_event_profile_v1.json")
        result = build_pre_match_review_priorities(
            compare_event_team_profiles(sporting, self.barcelona),
            analyze_matchup_interactions(sporting, self.barcelona),
        )
        suppressed = result.candidate_audit.loc[result.candidate_audit.status.isin({
            "suppressed_duplicate", "suppressed_semantic_group", "demoted_to_support",
        })]
        self.assertFalse(suppressed.empty)
        selected_keys = [item.priority_id for item in result.priorities]
        self.assertEqual(len(selected_keys), len(set(selected_keys)))
        self.assertTrue(any(len(item.source_finding_ids) > 1 for item in result.priorities))

    def test_directional_sources_precede_overlapping_general_comparisons(self):
        result = self.build()
        selected_general_topics = {
            item.football_family for item in result.priorities
            if item.primary_source_role == "general_team_comparison"
        }
        qualified_directional_topics = set(result.candidate_audit.loc[
            result.candidate_audit.source_role.eq("directional_matchup_interaction")
            & result.candidate_audit.primary_candidate_eligible,
            "football_family",
        ])
        self.assertTrue(selected_general_topics.isdisjoint(qualified_directional_topics))
        self.assertTrue(all(
            item.primary_source_role in {"directional_matchup_interaction", "general_team_comparison"}
            for item in result.priorities
        ))
        self.assertFalse(any(item.primary_source_role == "supporting_tendency" for item in result.priorities))

    def test_demoted_general_comparisons_are_attached_as_directional_support(self):
        directory = Path(__file__).resolve().parents[1] / "artifacts" / "event_profiles" / "statsbomb_11_27"
        sporting = load_event_profile_artifact(directory / "statsbomb_11_27_1041_event_profile_v1.json")
        barcelona = load_event_profile_artifact(directory / "statsbomb_11_27_217_event_profile_v1.json")
        result = build_pre_match_review_priorities(
            compare_event_team_profiles(sporting, barcelona),
            analyze_matchup_interactions(sporting, barcelona),
        )
        demoted = result.candidate_audit.loc[result.candidate_audit.status.eq("demoted_to_support")]
        self.assertFalse(demoted.empty)
        selected_by_source = {
            item.primary_evidence["finding_id"]: item for item in result.priorities
            if item.primary_source_role == "directional_matchup_interaction"
        }
        for row in demoted.itertuples(index=False):
            if row.supporting_priority_source_id not in selected_by_source:
                continue
            support = selected_by_source[row.supporting_priority_source_id].supporting_evidence
            self.assertTrue(any(
                item.get("finding_id") == row.source_finding_id
                and item.get("source_role") == "general_team_comparison"
                for item in support
            ))

    def test_titles_name_the_measured_concept(self):
        result = self.build()
        broad_only = {"Defensive activity", "Shot quality"}
        self.assertTrue(all(not any(label in item.title for label in broad_only) for item in result.priorities))
        self.assertTrue(any(
            any(label in item.title for label in ("Interceptions per 90", "Shots", "xG", "Penalty-area entries"))
            for item in result.priorities
        ))

    def test_review_question_grammar_handles_singular_and_plural_metrics(self):
        singular = build_metric_review_question("pass_completion_rate", "Barcelona", "Real Madrid")
        plural = build_metric_review_question("passes_into_penalty_area_per90", "Barcelona", "Real Madrid")
        xg = build_metric_review_question("xg_per_shot", "Barcelona", "Las Palmas")
        self.assertEqual(
            singular,
            "Review how Real Madrid's pass completion rate differs from Barcelona's.",
        )
        self.assertEqual(
            plural,
            "Review how Real Madrid's penalty-area entries by pass per 90 differ from Barcelona's.",
        )
        self.assertEqual(xg, "Review how Las Palmas' xG per shot differs from Barcelona's.")
        self.assertNotIn("entries differs", plural)

    def test_diminishing_slot_thresholds_are_configured_and_enforced(self):
        result = self.build()
        self.assertEqual(result.configuration["slot_admission_thresholds"], (.58, .58, .58, .66, .72))
        for item in result.priorities:
            self.assertGreaterEqual(
                item.priority_score,
                result.configuration["slot_admission_thresholds"][item.rank - 1],
            )
        with self.assertRaises(ValueError):
            self.build(slot_admission_thresholds=(.58, .58, .58, .50, .72))

    def test_distinct_validated_directional_outputs_are_not_semantically_collapsed(self):
        directory = Path(__file__).resolve().parents[1] / "artifacts" / "event_profiles" / "statsbomb_11_27"
        atletico = load_event_profile_artifact(directory / "statsbomb_11_27_212_event_profile_v1.json")
        sevilla = load_event_profile_artifact(directory / "statsbomb_11_27_213_event_profile_v1.json")
        result = build_pre_match_review_priorities(
            compare_event_team_profiles(atletico, sevilla),
            analyze_matchup_interactions(atletico, sevilla),
        )
        opponent_attack_outputs = {
            item.football_family for item in result.priorities
            if item.primary_source_role == "directional_matchup_interaction"
            and item.direction == "opponent_attack_vs_target_defence"
        }
        self.assertIn("chance_creation", opponent_attack_outputs)
        self.assertIn("shot_quality", opponent_attack_outputs)

    def test_semantic_suppression_is_auditable(self):
        result = self.build()
        semantic = result.candidate_audit.loc[
            result.candidate_audit.status.eq("suppressed_semantic_group")
        ]
        if not semantic.empty:
            self.assertTrue(semantic.supporting_priority_source_id.notna().all())
        self.assertTrue(result.configuration["semantic_group_suppression_enabled"])
        self.assertIn("attacking_output", set(result.configuration["semantic_preparation_groups"].values()))

    def test_weak_evidence_can_return_fewer_than_three(self):
        result = self.build(minimum_priority_score=1.01)
        self.assertLess(len(result.priorities), 3)

    def test_cross_metric_context_is_penalized_and_language_is_non_prescriptive(self):
        result = self.build()
        combined = " ".join(f"{item.title} {item.review_question}" for item in result.priorities).lower()
        for forbidden in ("defend deeper", "press higher", "mark ", "attack the left", "weakness", "will win"):
            self.assertNotIn(forbidden, combined)
        audit = result.candidate_audit.loc[
            result.candidate_audit.source_finding_id.str.contains("high_regain_turnover_exposure", regex=False)
        ]
        self.assertTrue((audit.priority_score < 0.70).all())

    def test_compatibility_contract_rejects_unvalidated_relationships(self):
        accepted = ReviewPriorityEvidenceCompatibility(
            "direct_attack_vs_defence_counterpart", True, "Exact mirrored definition.",
        )
        self.assertTrue(accepted.primary_candidate_eligible)
        with self.assertRaises(ValueError):
            ReviewPriorityEvidenceCompatibility("validated_relationship", True, "Claimed but unreferenced.")
        with self.assertRaises(ValueError):
            ReviewPriorityEvidenceCompatibility("unsupported_cross_metric", True, "Not eligible.")

    def test_high_regain_turnover_remains_visible_but_cannot_be_primary(self):
        comparison = compare_event_team_profiles(self.barcelona, self.real_madrid)
        interactions = analyze_matchup_interactions(self.barcelona, self.real_madrid)
        unsupported = interactions.interactions.loc[
            interactions.interactions.interaction_family.eq("high_regain_turnover_exposure")
        ]
        self.assertEqual(set(unsupported.review_priority_compatibility), {"unsupported_cross_metric"})
        result = build_pre_match_review_priorities(comparison, interactions)
        self.assertFalse(any(
            item.primary_evidence.get("compatibility", {}).get("category") == "unsupported_cross_metric"
            for item in result.priorities
        ))
        audit = result.candidate_audit.loc[
            result.candidate_audit.compatibility_category.eq("unsupported_cross_metric")
        ]
        self.assertFalse(audit.empty)
        self.assertTrue(audit.status.eq("unsupported_cross_metric").all())

    def test_previous_close_and_low_finding_failures_now_return_empty_shortlists(self):
        directory = Path(__file__).resolve().parents[1] / "artifacts" / "event_profiles" / "statsbomb_11_27"
        pairings = ((221, 223), (223, 210), (207, 209), (207, 210))
        for target_id, opponent_id in pairings:
            target = load_event_profile_artifact(directory / f"statsbomb_11_27_{target_id}_event_profile_v1.json")
            opponent = load_event_profile_artifact(directory / f"statsbomb_11_27_{opponent_id}_event_profile_v1.json")
            result = build_pre_match_review_priorities(
                compare_event_team_profiles(target, opponent),
                analyze_matchup_interactions(target, opponent),
                target_recurring_tendencies=generate_event_profile_findings(target).recurring_tendencies,
                opponent_recurring_tendencies=generate_event_profile_findings(opponent).recurring_tendencies,
            )
            self.assertEqual(result.priorities, [], f"{target.team_name} vs {opponent.team_name}")

    def test_api_response_is_json_safe(self):
        service = OpponentComparisonService(artifact_event_profile_resolver(Path(__file__).resolve().parents[1] / "artifacts"))
        identity = ("statsbomb_open_data", 217, 11, 27, "statsbomb_open_data", 220, 11, 27)
        payload = service.review_priorities(*identity)
        self.assertEqual(payload["schema_version"], "v1")
        self.assertTrue(payload["review_priorities"])
        json.dumps(payload, allow_nan=False)

    def test_moment_endpoint_fails_closed_without_event_bundle_resolver(self):
        service = OpponentComparisonService(artifact_event_profile_resolver(Path(__file__).resolve().parents[1] / "artifacts"))
        identity = ("statsbomb_open_data", 217, 11, 27, "statsbomb_open_data", 220, 11, 27)
        priority_id = service.review_priorities(*identity)["review_priorities"][0]["priority_id"]
        payload = service.review_priority_moments(*identity, priority_id=priority_id)
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["representative_moments"], [])
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
