"""Security boundary, validation, caching, and fallback tests for AI prose."""

import json
import unittest

import httpx

from src.ai.finding_explanations import (
    DeterministicExplanationProvider,
    LocalOpenAICompatibleExplanationClient,
    OpenAIResponsesExplanationClient,
    PROMPT_VERSION,
    TacticalExplanationService,
    build_explanation_input,
    explanation_provider_from_environment,
)
from src.analysis.finding_prioritization import prioritize_findings
from tests.test_finding_prioritization import make_result, shape_finding


class FakeModel:
    model_id = "fake-structured-model"

    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def finding_and_pack():
    finding = shape_finding(
        "m1:team1:shape_extreme:length",
        metric="length",
        sample=600,
        q95=50,
        median=30,
    )
    pack = prioritize_findings(make_result([finding])).evidence_packs[0]
    return finding, pack


def valid_output():
    return {
        "plain_english_summary": "The median was 30 m and the high-tail reference was 50 m.",
        "why_it_matters": "This may indicate that the team's vertical spacing varied during the observed moments.",
        "what_to_review_in_video": "At frame 1, review the distance between the deepest and highest outfield players.",
        "confidence_note": "This is descriptive evidence from 600 observations.",
    }


class FindingExplanationTests(unittest.TestCase):
    def test_provider_configuration_defaults_to_free_deterministic(self) -> None:
        provider = explanation_provider_from_environment({})
        self.assertIsInstance(provider, DeterministicExplanationProvider)
        self.assertEqual(provider.provider_id, "deterministic")

    def test_provider_configuration_requires_only_backend_specific_values(self) -> None:
        openai = explanation_provider_from_environment({
            "TACTIQ_EXPLANATION_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "TACTIQ_EXPLANATION_MODEL": "test-model",
        })
        self.assertIsInstance(openai, OpenAIResponsesExplanationClient)
        local = explanation_provider_from_environment({
            "TACTIQ_EXPLANATION_PROVIDER": "local",
            "TACTIQ_LOCAL_BASE_URL": "http://127.0.0.1:11434/v1",
            "TACTIQ_LOCAL_MODEL": "local-model",
        })
        self.assertIsInstance(local, LocalOpenAICompatibleExplanationClient)
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            explanation_provider_from_environment({"TACTIQ_EXPLANATION_PROVIDER": "openai"})
        with self.assertRaisesRegex(ValueError, "TACTIQ_LOCAL_BASE_URL"):
            explanation_provider_from_environment({"TACTIQ_EXPLANATION_PROVIDER": "local"})
        with self.assertRaisesRegex(ValueError, "deterministic, openai, or local"):
            explanation_provider_from_environment({"TACTIQ_EXPLANATION_PROVIDER": "unknown"})

    def test_local_provider_uses_openai_style_schema_and_shared_validation(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(body["response_format"]["type"], "json_schema")
            self.assertTrue(body["response_format"]["json_schema"]["strict"])
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(valid_output())}}]})

        provider = LocalOpenAICompatibleExplanationClient(
            base_url="http://localhost:11434/v1",
            model="test-local-model",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        finding, pack = finding_and_pack()
        result = TacticalExplanationService(provider).explain(finding, pack)
        self.assertEqual(result.source, "model")
        self.assertEqual(result.model_id, "test-local-model")
        self.assertEqual(len(requests), 1)

    def test_local_provider_is_loopback_only_and_invalid_output_falls_back(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            LocalOpenAICompatibleExplanationClient(base_url="https://example.com/v1", model="x")

        def handler(request: httpx.Request) -> httpx.Response:
            invalid = valid_output()
            invalid["plain_english_summary"] = "The distance was 999 m."
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(invalid)}}]})

        provider = LocalOpenAICompatibleExplanationClient(
            base_url="http://127.0.0.1:1234/v1",
            model="test-local-model",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        finding, pack = finding_and_pack()
        result = TacticalExplanationService(provider).explain(finding, pack)
        self.assertEqual(result.source, "deterministic_fallback")
        self.assertTrue(result.validation_warnings)

    def test_model_receives_only_the_explicit_allowlist(self) -> None:
        finding, pack = finding_and_pack()
        model = FakeModel(valid_output())
        result = TacticalExplanationService(model).explain(finding, pack)
        self.assertEqual(result.source, "model")
        supplied = model.calls[0]["evidence_input"]
        self.assertEqual(set(supplied), {
            "finding_title", "finding_description", "evidence_metrics",
            "comparator_baseline", "representative_moments", "evidence_strength",
            "sample_size", "capability_provenance", "limitations",
        })
        self.assertNotIn("player_positions", json.dumps(supplied))
        self.assertEqual(model.calls[0]["prompt_version"], PROMPT_VERSION)
        self.assertTrue(model.calls[0]["output_schema"]["additionalProperties"] is False)

    def test_identical_finding_and_evidence_reuses_cached_explanation(self) -> None:
        finding, pack = finding_and_pack()
        model = FakeModel(valid_output())
        service = TacticalExplanationService(model)
        first = service.explain(finding, pack)
        second = service.explain(finding, pack)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.evidence_hash, second.evidence_hash)
        self.assertEqual(first.explanation, second.explanation)
        self.assertEqual(len(model.calls), 1)

    def test_unsupported_number_triggers_deterministic_fallback(self) -> None:
        finding, pack = finding_and_pack()
        output = valid_output()
        output["plain_english_summary"] = "The shape expanded by 999 m."
        result = TacticalExplanationService(FakeModel(output)).explain(finding, pack)
        self.assertEqual(result.source, "deterministic_fallback")
        self.assertEqual(result.explanation.plain_english_summary, finding.description)
        self.assertTrue(result.validation_warnings)

    def test_causal_word_choice_or_recommendation_triggers_fallback(self) -> None:
        finding, pack = finding_and_pack()
        causal = valid_output()
        causal["why_it_matters"] = "This may prove the spacing caused the outcome."
        self.assertEqual(TacticalExplanationService(FakeModel(causal)).explain(finding, pack).source, "deterministic_fallback")
        recommendation = valid_output()
        recommendation["what_to_review_in_video"] = "At frame 1, the team should switch to a narrower defensive line."
        self.assertEqual(TacticalExplanationService(FakeModel(recommendation)).explain(finding, pack).source, "deterministic_fallback")

    def test_video_guidance_must_reference_supplied_moment_and_behavior(self) -> None:
        finding, pack = finding_and_pack()
        output = valid_output()
        output["what_to_review_in_video"] = "Review the evidence carefully."
        self.assertEqual(TacticalExplanationService(FakeModel(output)).explain(finding, pack).source, "deterministic_fallback")

    def test_no_model_returns_json_safe_versioned_fallback(self) -> None:
        finding, pack = finding_and_pack()
        result = TacticalExplanationService().explain(finding, pack)
        payload = result.to_dict()
        self.assertEqual(payload["prompt_version"], PROMPT_VERSION)
        self.assertEqual(payload["source"], "deterministic_fallback")
        json.dumps(payload, allow_nan=False)
        self.assertEqual(set(build_explanation_input(finding, pack)), {
            "finding_title", "finding_description", "evidence_metrics",
            "comparator_baseline", "representative_moments", "evidence_strength",
            "sample_size", "capability_provenance", "limitations",
        })


if __name__ == "__main__":
    unittest.main()
