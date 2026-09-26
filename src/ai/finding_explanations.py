"""Evidence-bounded AI explanations for already-generated tactical findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import math
import os
import re
from threading import RLock
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd

from src.analysis.finding_prioritization import EvidencePack
from src.analysis.tactical_findings import TacticalFinding


PROMPT_VERSION = "tactiq-finding-explanation-v1"

EXPLANATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "plain_english_summary",
        "why_it_matters",
        "what_to_review_in_video",
        "confidence_note",
    ],
    "properties": {
        "plain_english_summary": {"type": "string", "minLength": 1, "maxLength": 600},
        "why_it_matters": {"type": "string", "minLength": 1, "maxLength": 600},
        "what_to_review_in_video": {"type": "string", "minLength": 1, "maxLength": 600},
        "confidence_note": {"type": "string", "minLength": 1, "maxLength": 600},
    },
}

SYSTEM_PROMPT = """You explain an existing deterministic football finding to a professional analyst.
Use only the supplied finding and EvidencePack fields. Do not create a new finding, infer missing match
facts, claim causation, or recommend a tactical change. Phrase why_it_matters as a possible football
interpretation using language such as may, might, or could. In what_to_review_in_video, direct attention
to observable player spacing, positioning, movement, or ball context in the supplied representative
moments. Every numerical claim must be copied from, or be a normal rounding of, a supplied value.
Return only the requested structured object."""

_OUTPUT_FIELDS = tuple(EXPLANATION_OUTPUT_SCHEMA["required"])
_NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?%?")
_POSSIBILITY = re.compile(r"\b(may|might|could|possible|possibly|potential|potentially)\b", re.IGNORECASE)
_RECOMMENDATION = re.compile(
    r"\b(should|must|need(?:s)? to|recommend(?:s|ed|ation)?|consider changing|switch to|instruct(?:s|ed)? to)\b",
    re.IGNORECASE,
)
_CAUSAL_CLAIM = re.compile(
    r"\b(cause(?:d|s)?|proves?|resulted in|responsible for|led to)\b",
    re.IGNORECASE,
)
_OBSERVABLE_BEHAVIOR = re.compile(
    r"\b(spacing|position(?:ing)?|movement|distance|line|width|length|player|ball|shape)\b",
    re.IGNORECASE,
)


class ExplanationProvider(Protocol):
    """Backend boundary; implementations never receive a match bundle."""

    provider_id: str
    model_id: str
    source: str

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_input: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class TacticalExplanation:
    plain_english_summary: str
    why_it_matters: str
    what_to_review_in_video: str
    confidence_note: str


@dataclass(frozen=True)
class ExplanationResult:
    finding_id: str
    explanation: TacticalExplanation
    evidence_hash: str
    prompt_version: str
    model_id: str
    source: str
    cache_hit: bool
    validation_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


class OpenAIResponsesExplanationClient:
    """Small optional OpenAI Responses API client using strict JSON Schema."""

    provider_id = "openai"
    source = "model"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        if not api_key or not model:
            raise ValueError("OpenAI explanation client requires an API key and explicit model.")
        self._api_key = api_key
        self.model_id = model
        self._timeout = timeout_seconds

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_input: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
    ) -> Mapping[str, Any]:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model_id,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps({"prompt_version": prompt_version, "finding_evidence": evidence_input}, sort_keys=True)},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "tactical_finding_explanation",
                        "strict": True,
                        "schema": output_schema,
                    }
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text")
        if not text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        if not text:
            raise ValueError("OpenAI response contained no structured output text.")
        parsed = json.loads(text)
        if not isinstance(parsed, Mapping):
            raise ValueError("OpenAI structured output was not an object.")
        return parsed


class LocalOpenAICompatibleExplanationClient:
    """OpenAI-style chat-completions provider restricted to loopback hosts."""

    provider_id = "local"
    source = "model"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Local explanation base URL must use HTTP(S) on a loopback host.")
        if not model:
            raise ValueError("Local explanation provider requires an explicit model.")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model_id = model
        self._timeout = timeout_seconds
        self._client = client

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_input: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
    ) -> Mapping[str, Any]:
        request = self._client.post if self._client is not None else httpx.post
        response = request(
            self._endpoint,
            json={
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps({"prompt_version": prompt_version, "finding_evidence": evidence_input}, sort_keys=True)},
                ],
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "tactical_finding_explanation",
                        "strict": True,
                        "schema": output_schema,
                    },
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Local model response contained no assistant content.") from error
        parsed = content if isinstance(content, Mapping) else json.loads(content)
        if not isinstance(parsed, Mapping):
            raise ValueError("Local model structured output was not an object.")
        return parsed


def build_explanation_input(finding: TacticalFinding, evidence: EvidencePack) -> dict[str, Any]:
    """Return the complete and exclusive allowlist sent to an explanation model."""
    return _json_safe({
        "finding_title": finding.title,
        "finding_description": finding.description,
        "evidence_metrics": evidence.exact_metrics,
        "comparator_baseline": evidence.comparator,
        "representative_moments": evidence.representative_moments,
        "evidence_strength": evidence.priority.evidence_strength,
        "sample_size": finding.sample_size,
        "capability_provenance": evidence.capability_provenance,
        "limitations": evidence.limitations,
    })


def _json_safe(value: Any) -> Any:
    """Keep the AI boundary independent from the product API package."""
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _walk_numeric_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, bool) or value is None:
        return tokens
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        number = float(value)
        tokens.update({str(int(round(number))), f"{number:.1f}", f"{number:.2f}", str(number)})
        if abs(number) <= 1:
            percentage = number * 100
            tokens.update({str(int(round(percentage))), f"{percentage:.1f}", f"{percentage:.2f}"})
        return {token.rstrip("0").rstrip(".") if "." in token else token for token in tokens}
    if isinstance(value, str):
        return {match.group(0).rstrip("%") for match in _NUMBER.finditer(value)}
    if isinstance(value, Mapping):
        for key, item in value.items():
            tokens.update(_walk_numeric_tokens(str(key)))
            tokens.update(_walk_numeric_tokens(item))
        return tokens
    if isinstance(value, (list, tuple)):
        for item in value:
            tokens.update(_walk_numeric_tokens(item))
    return tokens


def validate_model_explanation(output: Mapping[str, Any], evidence_input: Mapping[str, Any]) -> TacticalExplanation:
    """Validate schema, epistemic language, recommendation ban, and numbers."""
    if set(output) != set(_OUTPUT_FIELDS):
        raise ValueError("Explanation output must contain exactly the four contracted fields.")
    if any(not isinstance(output[field], str) or not output[field].strip() for field in _OUTPUT_FIELDS):
        raise ValueError("Every explanation field must be a non-empty string.")
    if any(len(output[field]) > 600 for field in _OUTPUT_FIELDS):
        raise ValueError("Explanation fields may not exceed 600 characters.")
    if not _POSSIBILITY.search(output["why_it_matters"]):
        raise ValueError("why_it_matters must be framed as a possible interpretation.")
    combined = " ".join(output[field] for field in _OUTPUT_FIELDS)
    if _RECOMMENDATION.search(combined):
        raise ValueError("Explanation output contains a tactical recommendation.")
    if _CAUSAL_CLAIM.search(combined):
        raise ValueError("Explanation output contains a causal claim.")

    review = output["what_to_review_in_video"]
    if not _OBSERVABLE_BEHAVIOR.search(review):
        raise ValueError("Video review guidance must identify observable football behavior.")
    moments = evidence_input.get("representative_moments") or []
    if moments:
        markers: set[str] = set()
        for moment in moments:
            for key in ("label", "timestamp", "tactical_phase"):
                if moment.get(key) is not None:
                    markers.add(str(moment[key]).lower())
                    markers.add(str(moment[key]).replace("_", " ").lower())
            if moment.get("frame") is not None:
                markers.add(f"frame {moment['frame']}".lower())
        if markers and not any(marker in review.lower() for marker in markers):
            raise ValueError("Video review guidance must reference a supplied representative moment.")

    allowed = _walk_numeric_tokens(evidence_input)
    claimed = {match.group(0).rstrip("%") for match in _NUMBER.finditer(combined)}
    unsupported = sorted(token for token in claimed if token not in allowed)
    if unsupported:
        raise ValueError(f"Explanation contains unsupported numerical claims: {unsupported}")
    return TacticalExplanation(**{field: output[field].strip() for field in _OUTPUT_FIELDS})


def deterministic_explanation_output(evidence_input: Mapping[str, Any]) -> dict[str, str]:
    """Return provider output derived exclusively from the shared allowlist."""
    metrics = evidence_input["evidence_metrics"]
    dimension = str(metrics.get("dimension", "team shape")).replace("_", " ")
    moments = evidence_input["representative_moments"]
    labels = [str(moment.get("label")) for moment in moments if moment.get("label")]
    if labels:
        moment_text = " and ".join(labels[:2])
    elif moments and moments[0].get("frame") is not None:
        moment_text = f"frame {moments[0]['frame']}"
    elif moments and moments[0].get("timestamp") is not None:
        moment_text = str(moments[0]["timestamp"])
    else:
        moment_text = "the supplied representative moments"
    sample_unit = str(metrics.get("sample_unit", "observations"))
    return {
        "plain_english_summary": str(evidence_input["finding_description"]),
        "why_it_matters": f"This may help an analyst assess whether the observed {dimension} pattern recurs in the football context shown by the evidence.",
        "what_to_review_in_video": f"Compare {moment_text}, focusing on the observable player spacing along the {dimension} dimension and the listed phase context.",
        "confidence_note": f"This is descriptive evidence from {evidence_input['sample_size']} {sample_unit}; the listed data and interpretation limitations still apply.",
    }


class DeterministicExplanationProvider:
    """Free, offline provider and the default TactIQ explanation backend."""

    provider_id = "deterministic"
    model_id = "deterministic_fallback"
    source = "deterministic_fallback"

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_input: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
    ) -> Mapping[str, Any]:
        del system_prompt, output_schema, prompt_version
        return deterministic_explanation_output(evidence_input)


def explanation_provider_from_environment(
    environment: Mapping[str, str] | None = None,
) -> ExplanationProvider:
    """Build the configured backend; deterministic is explicit and default."""
    values = os.environ if environment is None else environment
    provider = values.get("TACTIQ_EXPLANATION_PROVIDER", "deterministic").strip().lower()
    if provider == "deterministic":
        return DeterministicExplanationProvider()
    if provider == "openai":
        api_key = values.get("OPENAI_API_KEY", "")
        model = values.get("TACTIQ_EXPLANATION_MODEL", "")
        if not api_key or not model:
            raise ValueError("The openai explanation provider requires OPENAI_API_KEY and TACTIQ_EXPLANATION_MODEL.")
        return OpenAIResponsesExplanationClient(api_key=api_key, model=model)
    if provider == "local":
        base_url = values.get("TACTIQ_LOCAL_BASE_URL", "")
        model = values.get("TACTIQ_LOCAL_MODEL", "")
        if not base_url or not model:
            raise ValueError("The local explanation provider requires TACTIQ_LOCAL_BASE_URL and TACTIQ_LOCAL_MODEL.")
        return LocalOpenAICompatibleExplanationClient(base_url=base_url, model=model)
    raise ValueError("TACTIQ_EXPLANATION_PROVIDER must be deterministic, openai, or local.")


class TacticalExplanationService:
    """Validate and cache provider output without exposing raw match data."""

    def __init__(self, provider: ExplanationProvider | None = None) -> None:
        self._provider = provider or DeterministicExplanationProvider()
        self._fallback_provider = DeterministicExplanationProvider()
        self._cache: dict[tuple[str, str, str, str], ExplanationResult] = {}
        self._lock = RLock()

    def explain(self, finding: TacticalFinding, evidence: EvidencePack) -> ExplanationResult:
        provider_id = getattr(self._provider, "provider_id", "model")
        model_id = self._provider.model_id
        evidence_input = build_explanation_input(finding, evidence)
        evidence_hash = _canonical_hash({"finding_id": finding.finding_id, "evidence": evidence_input})
        cache_key = (PROMPT_VERSION, provider_id, model_id, evidence_hash)
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return replace(cached, cache_hit=True)

            warnings: list[str] = []
            source = getattr(self._provider, "source", "model")
            try:
                output = self._provider.generate(
                    system_prompt=SYSTEM_PROMPT,
                    evidence_input=evidence_input,
                    output_schema=EXPLANATION_OUTPUT_SCHEMA,
                    prompt_version=PROMPT_VERSION,
                )
                explanation = validate_model_explanation(output, evidence_input)
            except Exception as error:
                fallback_output = self._fallback_provider.generate(
                    system_prompt=SYSTEM_PROMPT,
                    evidence_input=evidence_input,
                    output_schema=EXPLANATION_OUTPUT_SCHEMA,
                    prompt_version=PROMPT_VERSION,
                )
                explanation = validate_model_explanation(fallback_output, evidence_input)
                source = self._fallback_provider.source
                warnings.append(f"{provider_id} explanation failed validation: {type(error).__name__}.")
            result = ExplanationResult(
                finding_id=finding.finding_id,
                explanation=explanation,
                evidence_hash=evidence_hash,
                prompt_version=PROMPT_VERSION,
                model_id=model_id,
                source=source,
                cache_hit=False,
                validation_warnings=tuple(warnings),
            )
            self._cache[cache_key] = result
            return result
