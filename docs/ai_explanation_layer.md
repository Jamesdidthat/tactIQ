# Constrained finding explanation layer

The explanation layer is a presentation step after deterministic finding
generation, prioritisation, and EvidencePack construction. It cannot generate
findings and is never passed a `CanonicalMatchBundle`, tracking table, event
table, phase table, or pitch frame response.

## Model input allowlist

Only these fields cross the model boundary:

- finding title and description;
- EvidencePack metrics and comparator/baseline;
- representative moments;
- evidence strength and finding sample size;
- capability provenance;
- limitations.

The output contract contains exactly:

- `plain_english_summary`;
- `why_it_matters`;
- `what_to_review_in_video`;
- `confidence_note`.

The validator requires possible-interpretation language in `why_it_matters`,
rejects tactical recommendations, checks that video guidance names observable
football behaviour and a supplied evidence moment, and rejects numerical claims
that cannot be traced to the allowlisted input. Invalid output is discarded and
replaced with deterministic evidence-only prose.

## Versioning and reuse

`tactiq-finding-explanation-v1` identifies the prompt/validation contract. The
cache key combines this version, the explicit model ID, and a SHA-256 hash of
the finding ID plus its allowlisted evidence input. Cache metadata is returned
with every explanation so product QA can distinguish model output from fallback
and first generation from reuse.

## Provider configuration

The default provider is fully offline and requires no API key:

```text
TACTIQ_EXPLANATION_PROVIDER=deterministic
```

The value may be `deterministic`, `openai`, or `local`. Every provider receives
the same allowlisted EvidencePack input and its output passes through the same
schema, grounding, causal-language, recommendation, and video-reference
validation before it can reach the API.

For OpenAI:

```text
TACTIQ_EXPLANATION_PROVIDER=openai
OPENAI_API_KEY=<local secret>
TACTIQ_EXPLANATION_MODEL=<explicit model ID>
```

For a local OpenAI-compatible chat-completions endpoint such as Ollama or LM
Studio:

```text
TACTIQ_EXPLANATION_PROVIDER=local
TACTIQ_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
TACTIQ_LOCAL_MODEL=<installed local model name>
```

Local-provider URLs are restricted to `localhost`, `127.0.0.1`, or `::1`.
Provider-specific missing configuration fails clearly at startup; it never
silently selects a paid backend. API keys are never included in prompts,
responses, logs, hashes, or cached analysis objects.

## Match Story explanations

The same provider boundary also serves the downstream Match Story explainer.
Its prompt contract is versioned as `tactiq-match-story-explanation-v1`, and its
cache key combines prompt version, provider, model, and the SHA-256 hash of the
allowlisted story evidence. The model receives only the assembled story points,
their deterministic linkages, and verified match context; candidate audits,
internal scores, raw events, and match data never cross this boundary.

The output contains `headline`, `summary`, ordered `story_point_explanations`,
ordered `what_to_review_in_video`, and `evidence_caveat`. Validation preserves
story-point identity and order, rejects invented numeric claims, unsupported
causal/sequence language, recommendations, and unsupported football context,
and enforces event-derived possession wording. Invalid model output is discarded
in full and replaced by deterministic text. `no_qualifying_patterns` always
preserves the deterministic empty state and cannot acquire a generated story.
