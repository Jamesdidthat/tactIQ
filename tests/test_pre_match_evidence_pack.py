"""Pre-match evidence-pack contract and scope tests."""

import unittest

from src.analysis import PreMatchReviewPriority, build_pre_match_evidence_pack


def priority(*, compatibility="direct_attack_vs_defence_counterpart"):
    source_id = "interaction:a_attack_vs_b_defence:shots"
    return PreMatchReviewPriority(
        priority_id="priority-1", rank=1, title="A attack vs B defence: Shots",
        review_question="Review A's shots against B's usual defensive exposure.",
        direction="target_attack_vs_opponent_defence", football_family="chance_creation",
        primary_source_role="directional_matchup_interaction",
        primary_evidence={
            "source_type": "matchup_interaction", "source_role": "directional_matchup_interaction",
            "finding_id": source_id, "production_metric": "shots_per90",
            "exposure_metric": "shots_conceded_per90", "iqr_overlap_ratio": .1,
            "distributions_materially_overlap": False,
            "compatibility": {
                "category": compatibility,
                "primary_candidate_eligible": compatibility != "unsupported_cross_metric",
            },
        },
        supporting_evidence=({
            "source_type": "recurring_event_profile_tendency", "source_role": "supporting_tendency",
            "finding_id": "tendency-1", "recurrence_rate": .4,
        },),
        target_baseline={
            "team_id": 1, "team_name": "A", "role": "attacking_production",
            "metric": "shots_per90", "median": 15.0, "q25": 12.0, "q75": 18.0, "unit": "count_per_90",
        },
        opponent_baseline={
            "team_id": 2, "team_name": "B", "role": "defensive_exposure",
            "metric": "shots_conceded_per90", "median": 9.0, "q25": 7.0, "q75": 11.0, "unit": "count_per_90",
        },
        interaction_strength=.8, evidence_basis="High",
        match_counts={"attacking_team": 20, "defending_team": 20},
        coverage={"attacking_team": 1.0, "defending_team": 1.0},
        limitations=("Descriptive season evidence only.",), source_finding_ids=(source_id,),
        priority_score=.82, selection_reason="directional_matchup_interaction_primary",
    )


class PreMatchEvidencePackTests(unittest.TestCase):
    def test_pack_preserves_priority_identity_scope_and_video_unavailability(self):
        item = priority()
        pack = build_pre_match_evidence_pack(
            item,
            target_identity={"team_id": 1, "provider": "statsbomb_open_data"},
            opponent_identity={"team_id": 2, "provider": "statsbomb_open_data"},
            comparison_compatibility={"comparable": True, "required_capabilities": ["has_events"]},
        )
        self.assertIs(pack.priority, item)
        self.assertEqual(pack.primary_interaction_or_comparison["finding_id"], item.source_finding_ids[0])
        self.assertEqual(pack.primary_source_role, "directional_matchup_interaction")
        self.assertEqual(pack.sequence_pattern_summaries["retrieved_sample_count"], 0)
        self.assertIn("not all season events", pack.sequence_pattern_summaries["denominator_statement"])
        self.assertFalse(pack.optional_360_context["available"])
        self.assertFalse(pack.video_status["available"])
        self.assertIn("unavailable", pack.video_status["message"].lower())
        self.assertLessEqual(len(pack.limitations), 3)
        self.assertNotIn("priority_fill", pack.why_selected["description"])
        self.assertIn("A's attacking shots", pack.why_selected["description"])
        self.assertEqual(
            pack.technical_provenance["internal_selection"]["selection_reason"],
            "directional_matchup_interaction_primary",
        )
        self.assertIn("detailed_limitations", pack.technical_provenance)

    def test_unsupported_cross_metric_cannot_be_primary(self):
        with self.assertRaisesRegex(ValueError, "not eligible"):
            build_pre_match_evidence_pack(
                priority(compatibility="unsupported_cross_metric"),
                target_identity={"team_id": 1}, opponent_identity={"team_id": 2},
                comparison_compatibility={"comparable": True},
            )

    def test_primary_source_id_must_be_preserved(self):
        item = priority()
        altered = PreMatchReviewPriority(
            **{**item.__dict__, "source_finding_ids": ("different-source",)}
        )
        with self.assertRaisesRegex(ValueError, "preserve a selected source finding ID"):
            build_pre_match_evidence_pack(
                altered, target_identity={"team_id": 1}, opponent_identity={"team_id": 2},
                comparison_compatibility={"comparable": True},
            )


if __name__ == "__main__":
    unittest.main()
