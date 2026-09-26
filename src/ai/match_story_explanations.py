"""Grounded prose for an already-assembled deterministic Match Story."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import re
from threading import RLock
from typing import Any, Mapping

from src.analysis.match_story import MatchStoryResult

from .finding_explanations import (
    DeterministicExplanationProvider,
    ExplanationProvider,
    _canonical_hash,
    _json_safe,
    _walk_numeric_tokens,
)


PROMPT_VERSION = "tactiq-match-story-explanation-v1"
EMPTY_STATE = "No unusual season-relative patterns qualified. This does not mean the match lacked important events."

MATCH_STORY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "summary", "story_point_explanations", "what_to_review_in_video", "evidence_caveat"],
    "properties": {
        "headline": {"type": "string", "minLength": 1, "maxLength": 240},
        "summary": {"type": "string", "minLength": 1, "maxLength": 900},
        "story_point_explanations": {
            "type": "array", "maxItems": 4,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["story_id", "explanation"],
                "properties": {
                    "story_id": {"type": "string", "minLength": 1},
                    "explanation": {"type": "string", "minLength": 1, "maxLength": 600},
                },
            },
        },
        "what_to_review_in_video": {
            "type": "array", "maxItems": 4,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["story_id", "guidance"],
                "properties": {
                    "story_id": {"type": "string", "minLength": 1},
                    "guidance": {"type": "string", "minLength": 1, "maxLength": 600},
                },
            },
        },
        "evidence_caveat": {"type": "string", "minLength": 1, "maxLength": 600},
    },
}

SYSTEM_PROMPT = """You explain an already-assembled deterministic football Match Story.
You may not select, rank, merge, remove, or add story points. Use only the supplied Match Story and
verified match context. Preserve every story point exactly once and in the supplied order. For
connected_story, explain only the explicit supplied linkages and do not imply causation. For
parallel_observations, state clearly that the observations are separate. For a single point, explain
only that point without padding. For no_qualifying_patterns, return the supplied deterministic empty
state and empty arrays. Do not add numerical claims, recommendations, intentions, opponent-shape
claims, pressing triggers, overloads, or specific passages. Chronology is descriptive and never proves
that observations occurred in one sequence. Describe possession as event-derived. Evidence basis is
descriptive support, not certainty or tactical importance. Preserve unavailable score-state context as
unavailable. Return only the requested structured object."""

_OUTPUT_FIELDS = tuple(MATCH_STORY_OUTPUT_SCHEMA["required"])
_RECOMMENDATION = re.compile(
    r"\b(should|must|need(?:s)? to|recommend(?:s|ed|ation)?|consider|switch to|instruct(?:s|ed)?|adjust|improve|fix)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_CAUSAL = re.compile(
    r"\b(because|therefore|thus|caus(?:e|ed|es|ing)|result(?:ed|s)? in|led to|leads to|"
    r"responsible for|enabled|allowed|forced|drove|produced|so that)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_FOOTBALL_INFERENCE = re.compile(
    r"\b(player intention|intended to|opponent shape|pressing trigger|overload(?:ed|s)?|"
    r"same sequence|same passage|specific passage)\b",
    re.IGNORECASE,
)
_QUANTITATIVE_WORD = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|half|double|twice|triple)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?%?")
_SCORE_STATE_CLAIM = re.compile(r"\b(leading|trailing|drawing|led|trailed)\b", re.IGNORECASE)


@dataclass(frozen=True)
class StoryPointExplanation:
    story_id: str
    explanation: str


@dataclass(frozen=True)
class VideoReviewGuidance:
    story_id: str
    guidance: str


@dataclass(frozen=True)
class MatchStoryExplanation:
    headline: str
    summary: str
    story_point_explanations: tuple[StoryPointExplanation, ...]
    what_to_review_in_video: tuple[VideoReviewGuidance, ...]
    evidence_caveat: str


@dataclass(frozen=True)
class MatchStoryExplanationResult:
    match_id: str | int
    explanation: MatchStoryExplanation
    evidence_hash: str
    prompt_version: str
    provider_id: str
    model_id: str
    source: str
    cache_hit: bool
    validation_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def build_match_story_explanation_input(story: MatchStoryResult) -> dict[str, Any]:
    """Build the exclusive model allowlist; no events, raw data, or candidate audit."""
    context_keys = (
        "opponent_team_id", "opponent_team_name", "home_away", "team_score",
        "opponent_score", "team_relative_score", "match_date", "score_state_exposure",
        "score_state_source",
    )
    point_keys = (
        "story_id", "story_type", "title", "observation", "supporting_metrics",
        "comparator", "deviation", "primary_evidence_basis", "supporting_evidence_bases",
        "source_match_id", "contributing_season_match_count", "coverage", "limitations",
        "semantic_topic", "chronology",
    )
    return _json_safe({
        "match_story": {
            "team_id": story.team_id,
            "team_name": story.team_name,
            "match_id": story.match_id,
            "status": story.status,
            "message": story.message,
            "presentation_mode": story.presentation_mode,
            "coherence_linkages": list(story.coherence_linkages),
            "story_points": [
                {key: getattr(point, key) for key in point_keys}
                for point in story.story_points
            ],
        },
        "verified_match_context": {
            key: story.match_context.get(key) for key in context_keys
        },
    })


def _all_text(output: Mapping[str, Any]) -> str:
    pieces = [str(output.get("headline", "")), str(output.get("summary", "")), str(output.get("evidence_caveat", ""))]
    pieces.extend(str(item.get("explanation", "")) for item in output.get("story_point_explanations", []))
    pieces.extend(str(item.get("guidance", "")) for item in output.get("what_to_review_in_video", []))
    return " ".join(pieces)


def _validate_item_array(output: Mapping[str, Any], field: str, text_field: str, story_ids: list[str]) -> None:
    items = output[field]
    if not isinstance(items, list):
        raise ValueError(f"{field} must be an array.")
    if len(items) != len(story_ids):
        raise ValueError(f"{field} must preserve every supplied story point exactly once.")
    seen = []
    for item in items:
        if not isinstance(item, Mapping) or set(item) != {"story_id", text_field}:
            raise ValueError(f"Every {field} item must match its contracted schema.")
        if not isinstance(item["story_id"], str) or not isinstance(item[text_field], str) or not item[text_field].strip():
            raise ValueError(f"Every {field} item must contain a story id and non-empty text.")
        seen.append(item["story_id"])
    if seen != story_ids:
        raise ValueError(f"{field} changed the supplied story-point order or identity.")


def validate_match_story_explanation(output: Mapping[str, Any], evidence_input: Mapping[str, Any]) -> MatchStoryExplanation:
    """Enforce structure, identity, grounding, and epistemic constraints."""
    if set(output) != set(_OUTPUT_FIELDS):
        raise ValueError("Match Story explanation does not match the contracted fields.")
    for field, limit in (("headline", 240), ("summary", 900), ("evidence_caveat", 600)):
        if not isinstance(output[field], str) or not output[field].strip() or len(output[field]) > limit:
            raise ValueError(f"{field} must be non-empty and within its length limit.")

    story = evidence_input["match_story"]
    story_ids = [str(point["story_id"]) for point in story["story_points"]]
    _validate_item_array(output, "story_point_explanations", "explanation", story_ids)
    _validate_item_array(output, "what_to_review_in_video", "guidance", story_ids)
    if story["presentation_mode"] == "no_qualifying_patterns":
        if story_ids or output["story_point_explanations"] or output["what_to_review_in_video"]:
            raise ValueError("An empty Match Story may not acquire invented story points or review guidance.")
        if EMPTY_STATE not in output["summary"]:
            raise ValueError("The no-pattern explanation must preserve the deterministic empty state.")
    if story["presentation_mode"] == "parallel_observations" and not re.search(r"\b(separate|independent|not linked)\b", output["summary"], re.IGNORECASE):
        raise ValueError("Parallel observations must be explicitly presented as separate.")

    combined = _all_text(output)
    if _RECOMMENDATION.search(combined):
        raise ValueError("Match Story explanation contains a tactical recommendation.")
    if _UNSUPPORTED_CAUSAL.search(combined):
        raise ValueError("Match Story explanation contains unsupported causal language.")
    if _UNSUPPORTED_FOOTBALL_INFERENCE.search(combined):
        raise ValueError("Match Story explanation invents unsupported football context.")
    if _QUANTITATIVE_WORD.search(combined):
        raise ValueError("Match Story explanation contains an unverified word-form numerical claim.")

    allowed = _walk_numeric_tokens(evidence_input)
    claimed = {match.group(0).rstrip("%") for match in _NUMBER.finditer(combined)}
    unsupported = sorted(token for token in claimed if token not in allowed)
    if unsupported:
        raise ValueError(f"Match Story explanation contains unsupported numerical claims: {unsupported}")

    possession_mentions = [sentence for sentence in re.split(r"(?<=[.!?])\s+", combined) if re.search(r"\bpossession\b", sentence, re.IGNORECASE)]
    if any(not re.search(r"event[- ]derived", sentence, re.IGNORECASE) for sentence in possession_mentions):
        raise ValueError("StatsBomb possession must be described as event-derived.")
    context = evidence_input["verified_match_context"]
    if not context.get("score_state_source") and _SCORE_STATE_CLAIM.search(combined) and "unavailable" not in combined.lower():
        raise ValueError("Unavailable score-state context may not be inferred.")

    return MatchStoryExplanation(
        headline=output["headline"].strip(), summary=output["summary"].strip(),
        story_point_explanations=tuple(StoryPointExplanation(str(item["story_id"]), item["explanation"].strip()) for item in output["story_point_explanations"]),
        what_to_review_in_video=tuple(VideoReviewGuidance(str(item["story_id"]), item["guidance"].strip()) for item in output["what_to_review_in_video"]),
        evidence_caveat=output["evidence_caveat"].strip(),
    )


def _safe_title(title: str) -> str:
    safe = re.sub(r"\bled to\b", "was followed by", title, flags=re.IGNORECASE)
    safe = re.sub(r"\bproduced\b", "recorded", safe, flags=re.IGNORECASE)
    if re.search(r"\bpossession\b", safe, re.IGNORECASE) and not re.search(r"event[- ]derived", safe, re.IGNORECASE):
        safe = re.sub(r"\bpossession\b", "event-derived possession", safe, flags=re.IGNORECASE)
    return safe


def deterministic_match_story_explanation_output(evidence_input: Mapping[str, Any]) -> dict[str, Any]:
    story = evidence_input["match_story"]
    points = story["story_points"]
    mode = story["presentation_mode"]
    if mode == "no_qualifying_patterns":
        return {
            "headline": "No unusual season-relative patterns qualified",
            "summary": EMPTY_STATE,
            "story_point_explanations": [], "what_to_review_in_video": [],
            "evidence_caveat": "No explanatory narrative was generated when the deterministic Match Story was empty.",
        }
    if len(points) == 1:
        headline = _safe_title(str(points[0]["title"]))
        summary = "This explanation stays with the supplied observation and does not add a broader match narrative."
    elif mode == "connected_story":
        headline = "Deterministically linked match observations"
        summary = "The supplied evidence graph links these observations descriptively. The link does not establish causation or tactical importance."
    else:
        headline = "Separate notable match observations"
        summary = "These are separate observations. The supplied evidence does not establish that they form a shared tactical sequence or causal story."

    explanations, reviews = [], []
    for point in points:
        story_id = str(point["story_id"])
        title = _safe_title(str(point["title"]))
        explanation = f"{title}. This restates the deterministic comparison without adding a new finding."
        metrics = [str(item.get("metric", "the supplied metric")).replace("_", " ") for item in point.get("supporting_metrics", [])]
        metric_text = ", ".join(metrics) if metrics else "the supplied event metrics"
        if "possession" in metric_text.lower() and "event-derived" not in metric_text.lower():
            metric_text = metric_text.replace("possession", "event-derived possession")
        guidance = f"Review the event-defined actions underlying {metric_text}; do not treat their match chronology as a shared passage."
        explanations.append({"story_id": story_id, "explanation": explanation})
        reviews.append({"story_id": story_id, "guidance": guidance})
    return {
        "headline": headline, "summary": summary,
        "story_point_explanations": explanations,
        "what_to_review_in_video": reviews,
        "evidence_caveat": "Evidence basis describes the supplied season-relative support; it is not certainty, causal proof, or tactical importance.",
    }


class MatchStoryExplanationService:
    """Generate, validate, fall back, and cache explanations by grounded evidence."""

    def __init__(self, provider: ExplanationProvider | None = None) -> None:
        self._provider = provider or DeterministicExplanationProvider()
        self._fallback_provider = DeterministicExplanationProvider()
        self._cache: dict[tuple[str, str, str, str], MatchStoryExplanationResult] = {}
        self._lock = RLock()

    def explain(self, story: MatchStoryResult) -> MatchStoryExplanationResult:
        provider_id = getattr(self._provider, "provider_id", "model")
        model_id = self._provider.model_id
        evidence_input = build_match_story_explanation_input(story)
        evidence_hash = _canonical_hash(evidence_input)
        cache_key = (PROMPT_VERSION, provider_id, model_id, evidence_hash)
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return replace(cached, cache_hit=True)
            warnings: list[str] = []
            source = getattr(self._provider, "source", "model")
            try:
                if provider_id == "deterministic":
                    output = deterministic_match_story_explanation_output(evidence_input)
                else:
                    output = self._provider.generate(
                        system_prompt=SYSTEM_PROMPT, evidence_input=evidence_input,
                        output_schema=MATCH_STORY_OUTPUT_SCHEMA, prompt_version=PROMPT_VERSION,
                    )
                explanation = validate_match_story_explanation(output, evidence_input)
            except Exception as error:
                fallback = deterministic_match_story_explanation_output(evidence_input)
                explanation = validate_match_story_explanation(fallback, evidence_input)
                source = self._fallback_provider.source
                warnings.append(f"{provider_id} Match Story explanation failed validation: {type(error).__name__}.")
            result = MatchStoryExplanationResult(
                match_id=story.match_id, explanation=explanation, evidence_hash=evidence_hash,
                prompt_version=PROMPT_VERSION, provider_id=provider_id, model_id=model_id,
                source=source, cache_hit=False, validation_warnings=tuple(warnings),
            )
            self._cache[cache_key] = result
            return result
