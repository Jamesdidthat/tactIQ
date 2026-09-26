"""Synthetic event-query and representative-selection tests."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import pandas as pd

from src.analysis.representative_moments import (
    RepresentativeMoment, SUPPORTED_EVENT_METRICS, _deduplicate_moments,
    _event_mask, _select_balanced_pass_completion, _select_diverse,
    build_team_style_concept_moments,
)
from src.analysis.event_team_profile import _turnover_shot_links


def event_frame() -> pd.DataFrame:
    def row(event_id, event_type, index, x, y, *, end_x=None, end_y=None, **values):
        return {
            "event_id": event_id, "event_type": event_type, "team_id": 1,
            "location_x": x, "location_y": y, "end_location_x": end_x,
            "end_location_y": end_y, "pass_outcome": None, "outcome": None,
            "play_pattern": None, "shot_type": None, "ball_recovery_failure": False,
            "event_index": index, "shot_xg": None, **values,
        }
    return pd.DataFrame([
        row("pa-pass", "Pass", 1, 90, 40, end_x=105, end_y=40),
        row("pa-carry", "Carry", 2, 100, 30, end_x=104, end_y=30),
        row("progressive-carry", "Carry", 3, 60, 40, end_x=75, end_y=40),
        row("failed-pass", "Pass", 4, 90, 40, end_x=105, end_y=40, pass_outcome="Incomplete"),
        row("third", "Carry", 5, 70, 20, end_x=82, end_y=20),
        row("shot", "Shot", 6, 110, 40, play_pattern="Regular Play", shot_type="Open Play", shot_xg=.2),
        row("counter", "Shot", 7, 108, 42, play_pattern="From Counter", shot_type="Open Play", shot_xg=.1),
        row("set-play", "Shot", 8, 105, 40, play_pattern="From Corner", shot_type="Open Play", shot_xg=.15),
        row("interception", "Interception", 9, 75, 40),
        row("lost-interception", "Interception", 10, 85, 40, outcome="Lost"),
        row("recovery", "Ball Recovery", 11, 82, 40),
    ])


class RepresentativeMomentTests(unittest.TestCase):
    def test_team_style_examples_reuse_supported_queries_and_deduplicate(self):
        profile = type("Profile", (), {"team_id": 1, "team_name": "Example"})()
        def moment(event_id, metric):
            return RepresentativeMoment(
                match_id=1, team_id=1, team_name="Example", opponent_id=2,
                opponent_name="Opponent", match_date="2026-01-01", minute=10,
                second=0, period=1, event_id=event_id, event_type="Pass",
                metric=metric, family="progressive_passes", description="Example.",
                relevant_values={}, score_state="drawing", score_state_verified=True,
                score_state_team_id=1, score_state_team_name="Example",
                source_provenance={"provider": "statsbomb_open_data"},
                video_availability_status="unavailable_in_statsbomb_open_data",
                reason_selected="typical_match_example", evidence_side="team_style_history",
            )
        responses = [
            ([moment("shared", "progressive_passes_per90"), moment("pass-only", "progressive_passes_per90")], {"metric": "progressive_passes_per90", "query": "progressive_passes"}),
            ([moment("shared", "progressive_carries_per90"), moment("carry-only", "progressive_carries_per90")], {"metric": "progressive_carries_per90", "query": "progressive_carries"}),
        ]
        with patch("src.analysis.representative_moments._query_profile", side_effect=responses) as query:
            result = build_team_style_concept_moments(
                "progression", ["progressive_passes_per90", "progressive_carries_per90"],
                profile, lambda *_args: None, limit=6,
            )
        self.assertTrue(result.supported)
        self.assertEqual([item.event_id for item in result.moments], ["shared", "pass-only", "carry-only"])
        self.assertEqual(len(result.suppressed_duplicates), 1)
        self.assertEqual(query.call_count, 2)
        self.assertIn("does not invent", " ".join(result.limitations))

    def test_supported_mapping_covers_requested_initial_metrics(self):
        expected = {
            "passes_into_penalty_area_per90", "passes_into_final_third_per90",
            "shots_per90", "xg_per90", "xg_per_shot", "interceptions_per90",
            "high_regains_per90", "counter_attack_shots_per90", "set_play_shots_per90",
            "progressive_passes_per90", "pass_completion_rate",
            "progressive_carries_per90",
            "turnovers_leading_to_shot_per90",
        }
        self.assertTrue(expected.issubset(SUPPORTED_EVENT_METRICS))

    def test_explicit_event_queries_follow_existing_geometry_and_tags(self):
        events = event_frame()
        selected = lambda query: set(events.loc[_event_mask(events, query, 1), "event_id"])
        self.assertEqual(selected("penalty_area_entries"), {"pa-pass", "pa-carry"})
        self.assertEqual(selected("final_third_entries"), {"third"})
        self.assertEqual(selected("progressive_passes"), {"pa-pass"})
        self.assertEqual(selected("progressive_carries"), {"progressive-carry"})
        self.assertEqual(selected("pass_completion"), {"pa-pass", "failed-pass"})
        self.assertEqual(selected("shots"), {"shot", "counter", "set-play"})
        self.assertEqual(selected("interceptions"), {"interception"})
        self.assertEqual(selected("high_regains"), {"recovery"})
        self.assertEqual(selected("counter_attacks"), {"counter"})
        self.assertEqual(selected("set_play_shots"), {"set-play"})

    def test_xg_quality_selection_uses_distribution_anchors_and_match_diversity(self):
        candidates = []
        for index, value in enumerate((.02, .08, .15, .30, .55), start=1):
            candidates.append({
                "event_id": f"e{index}", "match_id": index, "match_date": f"2016-01-{index:02d}",
                "event_index": index, "selection_value": value, "score_state": "drawing",
            })
        selected = _select_diverse(candidates, 4, "xg_per_shot")
        self.assertEqual(len(selected), 4)
        self.assertEqual(len({row["match_id"] for row in selected}), 4)
        self.assertEqual(
            {row["reason_selected"] for row in selected},
            {"lower_quality_example", "typical_quality_example", "higher_quality_example", "highest_quality_example"},
        )

    def test_high_xg_selection_never_returns_multiple_events_from_one_match(self):
        candidates = [
            {"event_id": "a", "match_id": 1, "match_date": "2016-01-01", "event_index": 1, "selection_value": .5},
            {"event_id": "b", "match_id": 1, "match_date": "2016-01-01", "event_index": 2, "selection_value": .4},
            {"event_id": "c", "match_id": 2, "match_date": "2016-01-02", "event_index": 3, "selection_value": .3},
        ]
        selected = _select_diverse(candidates, 5, "xg")
        self.assertEqual([row["event_id"] for row in selected], ["a", "c"])

    def test_pass_completion_examples_are_balanced_and_explicit(self):
        candidates = [
            {"event_id": f"c{i}", "match_id": i, "match_date": f"2016-01-{i:02d}", "event_index": i, "pass_completed": True}
            for i in range(1, 6)
        ] + [
            {"event_id": f"i{i}", "match_id": i + 10, "match_date": f"2016-02-{i:02d}", "event_index": i, "pass_completed": False}
            for i in range(1, 6)
        ]
        selected = _select_balanced_pass_completion(candidates, 8)
        self.assertEqual(sum(item["pass_completed"] for item in selected), 4)
        self.assertEqual(sum(not item["pass_completed"] for item in selected), 4)
        self.assertEqual(
            {item["reason_selected"] for item in selected},
            {"completed_pass_example", "incomplete_pass_example"},
        )

    def test_turnover_to_shot_link_uses_existing_time_and_event_bounds(self):
        events = pd.DataFrame([
            {"event_id": "build", "event_index": 1, "period": 1, "possession_id": 10, "possession_team_id": 1, "event_type": "Pass", "elapsed_seconds": 100.0},
            {"event_id": "turnover", "event_index": 2, "period": 1, "possession_id": 10, "possession_team_id": 1, "event_type": "Miscontrol", "elapsed_seconds": 101.0},
            {"event_id": "counter-pass", "event_index": 3, "period": 1, "possession_id": 11, "possession_team_id": 2, "event_type": "Pass", "elapsed_seconds": 102.0},
            {"event_id": "linked-shot", "event_index": 4, "period": 1, "possession_id": 11, "possession_team_id": 2, "event_type": "Shot", "elapsed_seconds": 110.0},
            {"event_id": "later", "event_index": 5, "period": 1, "possession_id": 12, "possession_team_id": 1, "event_type": "Pass", "elapsed_seconds": 112.0},
        ])
        links = _turnover_shot_links(events, 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["turnover_event_id"], "turnover")
        self.assertEqual(links[0]["shot_event_id"], "linked-shot")
        self.assertEqual(links[0]["linked_sequence_event_ids"], ("turnover", "counter-pass", "linked-shot"))

    def test_sevilla_malaga_duplicate_event_is_reconciled_deterministically(self):
        def example(side: str) -> RepresentativeMoment:
            return RepresentativeMoment(
                match_id=99, team_id=213, team_name="Sevilla", opponent_id=223,
                opponent_name="Málaga", match_date="2016-01-01", minute=10,
                second=0, period=1, event_id="stable-entry-event", event_type="Pass",
                metric="passes_into_penalty_area_per90", family="penalty_area_entries",
                description="Entry.", relevant_values={}, score_state="drawing",
                score_state_verified=True, score_state_team_id=213,
                score_state_team_name="Sevilla",
                source_provenance={"provider": "statsbomb_open_data"},
                video_availability_status="unavailable_in_statsbomb_open_data",
                reason_selected="typical_match_example", evidence_side=side,
            )
        unique, suppressed = _deduplicate_moments([
            example("attacking_production"), example("defensive_exposure"),
        ])
        self.assertEqual([item.event_id for item in unique], ["stable-entry-event"])
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0]["kept_evidence_side"], "attacking_production")
        self.assertEqual(suppressed[0]["suppressed_evidence_side"], "defensive_exposure")

        with self.assertRaisesRegex(ValueError, "cannot be reconciled"):
            _deduplicate_moments([replace(example("attacking_production"), source_provenance={})])


if __name__ == "__main__":
    unittest.main()
