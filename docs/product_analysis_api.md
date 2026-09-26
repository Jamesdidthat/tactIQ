# Product analysis API contract (v1)

`MatchAnalysisService` is an in-process service boundary. It accepts either a
`CanonicalMatchBundle` or a match ID resolved by the configured bundle resolver.
It caches deterministic analysis by provider, match ID, and
`allow_assumed_roles` mode. The optional explanation layer is downstream of
the deterministic finding contract and never receives the canonical bundle.
No database, authentication, or persistence is part of this contract.

Every response is JSON-safe and starts with `schema_version: "v1"`.

| Service method | Response fields |
| --- | --- |
| `get_match_summary` | match identity/provider/pitch/date, home/away teams and nullable scores, capabilities, finding counts, warnings, analysis coverage |
| `get_ranked_findings` | stable ordered shortlist; finding identity/text/sample/confidence/limitations and visible component scores |
| `get_finding_detail` | full finding plus exact metrics, contextual comparator, references, representative moments, provenance, coverage, limitations |
| `get_finding_explanation` | four-field constrained explanation plus prompt/model version, evidence hash, cache status, source and validation warnings |
| `get_analysis_coverage` | module support, status, skip reasons, and finding counts |
| `get_representative_pitch_frame` | canonical pitch, frame/period/time, player positions, ball position/availability |

The API never serializes pandas indexes/dataframes or provider-native raw files.
Pitch frames are built only from canonical player and ball tables. Finding detail
requires a ranked-shortlist finding ID; unknown or suppressed findings return a
local `KeyError` rather than triggering a new analysis run.

The localhost HTTP wrapper also exposes
`GET /matches/{match_id}/findings/{finding_id}/explanation`. Explanation
providers are selected with `TACTIQ_EXPLANATION_PROVIDER`; the default is the
free offline deterministic provider. `openai` uses the Responses API, while
`local` uses a loopback OpenAI-compatible chat-completions endpoint. The JSON
response contract is identical for every provider.

## Event Team Profile endpoints

Event-season profiles use the same JSON-safe `v1` boundary and are addressed by
provider, team, competition, and season:

`GET /event-profiles/{provider}/{team_id}/{competition_id}/{season_id}/{resource}`

| Resource | Product data |
| --- | --- |
| `summary` | Team/season identity, match coverage, coordinate provenance and capabilities |
| `baselines` | Match-weighted median, Q25/Q75, contributing matches, coverage and metric definition |
| `findings` | Deterministic robust deviations with source match and duplicate-suppression audit |
| `tendencies` | Counts of unusual matches and above/below-baseline findings by football family |
| `unusual-matches` | Stable match ranking by strongest absolute robust standardized deviation |
| `archetypes` | Transparent rule definitions, multi-label match assignments, component z-scores, and season frequencies |
| `relationships` | Theil–Sen relationship equations, coverage and uncertainty audit, match residuals, and unusual-residual findings |

Event findings are generated from compact match rows. They use the season
median and `IQR / 1.349` robust scale, with scaled MAD as a fallback. A finding
requires at least 10 contributing matches, at least 80% coverage, and absolute
robust z-score of at least 1.5. This score measures deviation within the team's
season distribution; it is not a probability or a quality judgment.

`GET /event-profiles/{provider}/{team_id}/{competition_id}/{season_id}/matches/{match_id}/story`
returns at most four deterministic, context-aware story points assembled from
relationship residuals, match archetypes, and single metrics. Qualified evidence
is first merged into semantic football topics, then selected as a coherent
possession/progression/territory/chance or transition/defensive sequence. Source
diversity is secondary to narrative unity. Match context includes opponent,
venue, score, event-derived score-state exposure where verifiable, and compact
per-metric chronology. The assembler may return one point or no points rather
than padding a weak story. A zero-point response uses the explicit
`no_qualifying_patterns` state and cautious product wording. Internal ranking
components remain auditable but are not statistical confidence. Multi-point
outputs also expose `presentation_mode`: `connected_story` requires a connected
evidence graph based on fitted metric relationships, shared primary metrics,
shared archetype evidence, or an exact shared event subset. Topic adjacency and
overlapping broad event spans never establish coherence. Disconnected valid
points use `parallel_observations` and are presented as **Notable observations**.
Merged points expose `primary_evidence_basis` separately from
`supporting_evidence_bases`; secondary support cannot upgrade the titled claim.

`GET /event-profiles/{provider}/{team_id}/{competition_id}/{season_id}/matches/{match_id}/story/explanation`
returns the optional grounded explanation of that unchanged deterministic story.
It preserves point identity and order, reports model/fallback and cache metadata,
and uses the same `deterministic`, `local`, or `openai` provider configuration as
single-finding explanations. The default remains the offline deterministic
provider.

## Opponent comparison endpoints

Pre-match event comparisons use:

`GET /opponent-comparisons/{target_provider}/{target_team}/{target_competition}/{target_season}/{opponent_provider}/{opponent_team}/{opponent_competition}/{opponent_season}/{resource}`

Supported opponent-comparison resources are `summary`, `metrics`, `findings`,
`interactions`, `interaction-findings`, and `review-priorities`. The interaction
resources expose attack-versus-defence evidence in both directions; their
interaction-strength value is a deterministic descriptive index, not a
probability. `review-priorities` returns the capped analyst review shortlist and
its complete selection/suppression audit.

Every review-priority primary evidence object includes a compatibility contract.
Only `same_metric`, `direct_attack_vs_defence_counterpart`, and an explicitly
referenced `validated_relationship` are primary-eligible. An
`unsupported_cross_metric` interaction remains available as side-by-side source
analysis, but its mismatch, overlap verdict, and strength are `null`; it cannot
produce or upgrade a review priority.

Every selected review priority exposes `primary_source_role`. Supported primary
roles are `directional_matchup_interaction` and `general_team_comparison`;
`supporting_tendency` is support-only. When directional and general evidence
cover the same football topic, the directional finding remains primary and the
general comparison appears in `supporting_evidence`. The candidate audit marks
that comparison as `demoted_to_support` and records its primary destination.
The response configuration exposes the slot-admission thresholds and semantic
preparation groups. Candidate-audit rows distinguish `below_slot_threshold`
from `suppressed_semantic_group` and include the required score and supporting
priority destination.

`GET /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority_id}/moments`
returns 5–10 deterministic historical event examples where the primary metric
has an explicit query mapping. Each moment preserves its provider event ID,
native coordinate provenance, verified score-state perspective, selection
reason, and video-availability status. Unsupported metrics return an explicit
empty state. These moments illustrate the metric definition and are not evidence
of causality or a forecast for the future matchup.

`GET /opponent-comparisons/{target identity}/{opponent identity}/review-priorities/{priority_id}/moments/{event_id}`
returns one bounded representative-moment detail. Known possession IDs are hard
boundaries; otherwise the response declares a short same-period time-window
fallback. Event order and UUIDs are preserved. Missing coordinates remain null.
The payload includes only event-derived phase/play-pattern context and never
promotes StatsBomb 360 snapshots to continuous tracking.

The resources are `summary`, `metrics`, and `findings`. They return compatibility
provenance, accepted and excluded metric evidence, and a deterministic ranked
contrast list. Differences are always opponent minus target. Unsupported
provider, coordinate, unit, definition, sample-size, or coverage combinations
fail closed or are reported as excluded rather than silently coerced.
