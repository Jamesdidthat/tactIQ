"""Grounding, mode behavior, caching, and API tests for Match Story prose."""

from dataclasses import replace
import json
from pathlib import Path
import unittest

from src.ai.match_story_explanations import (
    EMPTY_STATE,
    PROMPT_VERSION,
    MatchStoryExplanationService,
    build_match_story_explanation_input,
    deterministic_match_story_explanation_output,
    validate_match_story_explanation,
)
from src.analysis.match_story import MatchStoryPoint, MatchStoryResult, assemble_match_story
from src.api.event_profile_service import EventProfileService, artifact_event_profile_resolver, load_event_profile_artifact


class FakeModel:
    provider_id = "fake"
    model_id = "fake-story-model"
    source = "model"

    def __init__(self, output):
        self.output, self.calls = output, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def point(identifier: str, title: str = "Penalty-area access was unusually high") -> MatchStoryPoint:
    return MatchStoryPoint(
        story_id=identifier, story_type="single_metric_deviation", title=title,
        observation="Penalty-area entries were above the season median.",
        supporting_metrics=({"metric": "passes_into_penalty_area_per90", "observed_value": 18.0, "season_baseline": 12.0},),
        comparator={"value": 12.0}, deviation={"signed": 6.0}, evidence_level="moderate",
        source_match_id=101, contributing_season_match_count=20, coverage=1.0,
        limitations=("Descriptive match-level evidence only.",), redundancy_group="territory",
        priority_score=.8, priority_components={"coverage": 1.0}, selection_reason="strong_standalone",
        semantic_topic="territorial_access", chronology={"available": False}, evidence_basis="Moderate",
        primary_evidence_basis="Moderate", supporting_evidence_bases=(), merged_candidate_ids=(identifier,),
    )


def story(mode: str = "connected_story", count: int = 1, *, score_state_source="event_goal_timeline_verified") -> MatchStoryResult:
    points = [point(f"story-{index}") for index in range(count)]
    return MatchStoryResult(
        team_id=217, team_name="Barcelona", match_id=101, story_points=points,
        candidate_audit=__import__("pandas").DataFrame(), maximum_story_points=4,
        match_context={
            "opponent_team_id": 1, "opponent_team_name": "Opponent", "home_away": "home",
            "team_score": 2, "opponent_score": 1, "team_relative_score": "2-1", "match_date": "2016-01-01",
            "score_state_exposure": {}, "score_state_source": score_state_source,
        }, status="story_available", message=None, presentation_mode=mode,
        coherence_linkages=({"from_story_candidate_id": "story-0", "to_story_candidate_id": "story-1", "linkage_type": "shared_metric"},) if count > 1 and mode == "connected_story" else (),
    )


def valid_model_output(source_story: MatchStoryResult):
    supplied = build_match_story_explanation_input(source_story)
    return deterministic_match_story_explanation_output(supplied)


class MatchStoryExplanationTests(unittest.TestCase):
    def test_model_boundary_is_allowlisted_and_excludes_internal_audit(self):
        supplied = build_match_story_explanation_input(story())
        self.assertEqual(set(supplied), {"match_story", "verified_match_context"})
        self.assertEqual(set(supplied["match_story"]), {
            "team_id", "team_name", "match_id", "status", "message", "presentation_mode",
            "coherence_linkages", "story_points",
        })
        encoded = json.dumps(supplied)
        self.assertNotIn("candidate_audit", encoded)
        self.assertNotIn("priority_score", encoded)
        self.assertNotIn("raw_events", encoded)

    def test_deterministic_behavior_respects_all_presentation_modes(self):
        single = MatchStoryExplanationService().explain(story(count=1)).explanation
        self.assertEqual(len(single.story_point_explanations), 1)
        connected = MatchStoryExplanationService().explain(story(count=2)).explanation
        self.assertIn("evidence graph links", connected.summary)
        parallel = MatchStoryExplanationService().explain(story("parallel_observations", 2)).explanation
        self.assertIn("separate observations", parallel.summary)

        empty_story = story("no_qualifying_patterns", 0)
        empty_story.status, empty_story.message = "no_qualifying_patterns", EMPTY_STATE
        empty = MatchStoryExplanationService().explain(empty_story).explanation
        self.assertEqual(empty.summary, EMPTY_STATE)
        self.assertFalse(empty.story_point_explanations)
        self.assertFalse(empty.what_to_review_in_video)

    def test_invalid_numbers_causality_recommendations_and_point_changes_fall_back(self):
        source = story()
        for mutation in ("number", "causal", "recommendation", "removed"):
            output = valid_model_output(source)
            if mutation == "number":
                output["summary"] = "The difference was 999 units."
            elif mutation == "causal":
                output["summary"] = "This caused the match pattern."
            elif mutation == "recommendation":
                output["summary"] = "The team should adjust its structure."
            else:
                output["story_point_explanations"] = []
            result = MatchStoryExplanationService(FakeModel(output)).explain(source)
            self.assertEqual(result.source, "deterministic_fallback", mutation)
            self.assertTrue(result.validation_warnings, mutation)

    def test_possession_and_unavailable_score_state_are_guarded(self):
        source = story(score_state_source=None)
        supplied = build_match_story_explanation_input(source)
        output = valid_model_output(source)
        output["summary"] = "Possession was higher in this match."
        with self.assertRaisesRegex(ValueError, "event-derived"):
            validate_match_story_explanation(output, supplied)
        output = valid_model_output(source)
        output["summary"] = "Barcelona was leading for much of the match."
        with self.assertRaisesRegex(ValueError, "score-state"):
            validate_match_story_explanation(output, supplied)

    def test_cache_keys_include_story_evidence_and_prompt_provider_model(self):
        source = story()
        model = FakeModel(valid_model_output(source))
        service = MatchStoryExplanationService(model)
        first, second = service.explain(source), service.explain(source)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.evidence_hash, second.evidence_hash)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0]["prompt_version"], PROMPT_VERSION)
        self.assertFalse(model.calls[0]["output_schema"]["additionalProperties"])

        changed_point = replace(source.story_points[0], title="A changed grounded title")
        changed_story = replace(source, story_points=[changed_point])
        model.output = valid_model_output(changed_story)
        changed = service.explain(changed_story)
        self.assertNotEqual(first.evidence_hash, changed.evidence_hash)
        self.assertEqual(len(model.calls), 2)

    def test_real_event_profile_endpoint_is_json_safe_and_deterministic(self):
        root = Path(__file__).resolve().parents[1]
        service = EventProfileService(artifact_event_profile_resolver(root / "artifacts"))
        first = service.match_story_explanation("statsbomb_open_data", 217, 11, 27, 266961)
        second = service.match_story_explanation("statsbomb_open_data", 217, 11, 27, 266961)
        self.assertEqual(first["schema_version"], "v1")
        self.assertEqual(first["match_id"], 266961)
        self.assertFalse(first["metadata"]["cache_hit"])
        self.assertTrue(second["metadata"]["cache_hit"])
        json.dumps(second, allow_nan=False)

    def test_real_parallel_and_empty_match_outputs_validate(self):
        root = Path(__file__).resolve().parents[1]
        profile = load_event_profile_artifact(root / "artifacts" / "statsbomb_barcelona_2015_2016_event_profile_v1.json")
        parallel = assemble_match_story(profile, 267327)
        self.assertEqual(parallel.presentation_mode, "parallel_observations")
        self.assertEqual(MatchStoryExplanationService().explain(parallel).source, "deterministic_fallback")


if __name__ == "__main__":
    unittest.main()
