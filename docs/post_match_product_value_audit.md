# TactIQ post-match proof-of-value audit

## Purpose

This is a frozen ten-match validation sample. It asks whether TactIQ produces a small number of understandable, grounded observations that a football analyst would actually investigate. It does **not** treat automated checks as a substitute for football judgement.

## Automated audit summary

- Matches: **10**
- Goals expected from recorded scores: **38**
- Goals analysed: **39**
- Matches with complete goal coverage: **9/10**
- Visible technical-language hits: **119**
- Unsupported causal-language hits: **0**
- Broad recurrence claims needing scope correction: **16**
- Empty goal sequences: **0**

| Match | Date | Score | Goals | Technical copy flags | Recurrence-scope flags | Max segment repetition |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 266236 | 2015-08-23 | 0-1 | 1 | 9 | 0 | 71% |
| 266467 | 2015-09-23 | 4-1 | 5 | 13 | 3 | 57% |
| 3825627 | 2015-10-17 | 5-2 | 7 | 13 | 4 | 71% |
| 266424 | 2015-11-21 | 0-4 | 4 | 11 | 1 | 71% |
| 266961 | 2015-12-12 | 2-2 | 4 | 9 | 3 | 71% |
| 266670 | 2016-01-02 | 0-0 | 0 | 6 | 0 | 71% |
| 267576 | 2016-01-30 | 2-1 | 3 | 14 | 1 | 57% |
| 267533 | 2016-04-02 | 1-2 | 3 | 15 | 1 | 71% |
| 266310 | 2016-04-20 | 0-8 | 8 | 16 | 3 | 57% |
| 266557 | 2016-04-17 | 1-2 | 4 | 13 | 0 | 71% |

## What the machine audit can and cannot establish

It can verify goal coverage, evidence presence, prohibited causal wording, recurrence provenance, and repetitive copy. It cannot decide whether the engine identified the match's most important tactical pattern. That requires reviewing footage or an independent trusted match account.

## Acceptance target for the next product milestone

Across this frozen sample, a knowledgeable reviewer should mark at least 70% of shortlisted observations **accurate and useful**, fewer than 10% **unsupported**, and identify no systematic mismatch between a goal explanation and its evidence sequence. Until that happens, TactIQ should remain a research MVP rather than claim reliable pundit-level analysis.

## Match 266236 — 2015-08-23 — 0-1

**Why selected:** Narrow away win and a low-event scoreline.

### Current first impression

- **Athletic Club:** They recorded more defensive pressures than in a typical match from this season sample.
- **Barcelona:** They recorded less passes into the box than in a typical match from this season sample.

### Goal explanations

- **53:50 — Barcelona:** The recorded possession contained 6 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **9**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **0**

Broad recurrence-scope flags:

- None.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266467 — 2015-09-23 — 4-1

**Why selected:** Defeat despite substantial attacking output.

### Current first impression

- **Celta Vigo:** They recorded more explicitly tagged counter-attack shots than in a typical match from this season sample.
- **Barcelona:** They recorded more lost possessions followed quickly by an opposition shot than in a typical match from this season sample.

### Goal explanations

- **25:31 — Celta Vigo:** The recorded possession contained 6 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **29:06 — Celta Vigo:** An explicitly tagged counter attack preceded the finish. _Season check:_ This scoring mechanism appears in 45% of the scoring team's season matches in the available sample.
- **55:40 — Celta Vigo:** An explicitly tagged counter attack preceded the finish. _Season check:_ This scoring mechanism appears in 45% of the scoring team's season matches in the available sample.
- **79:36 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **82:05 — Celta Vigo:** The recorded possession contained 6 passes and 7 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **13**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **0**

Broad recurrence-scope flags:

- 266467:ff3fe7ba-3263-45c3-9450-d4d1e11efda7: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266467:17bc3580-28e2-4318-a4f4-2619d182965b: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266467:c17fb75f-ff3b-41ff-a2cd-73fc8c2877d5: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 3825627 — 2015-10-17 — 5-2

**Why selected:** High-scoring win with unusually low possession for the team.

### Current first impression

- **Barcelona:** They recorded more interceptions than in a typical match from this season sample.
- **Rayo Vallecano:** They recorded more high ball recoveries than in a typical match from this season sample.

### Goal explanations

- **14:04 — Rayo Vallecano:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 89% of the scoring team's season matches in the available sample.
- **21:38 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **31:44 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **68:34 — Barcelona:** The recorded possession contained 4 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **69:54 — Barcelona:** An explicitly tagged counter attack preceded the finish. _Season check:_ This scoring mechanism appears in 50% of the scoring team's season matches in the available sample.
- **76:06 — Barcelona:** The recorded possession contained 3 passes and 1 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **85:43 — Rayo Vallecano:** The recorded possession contained 3 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **13**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **1**

Broad recurrence-scope flags:

- 3825627:6e4c2782-77c1-45d9-87da-8514df87fb7f: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 3825627:dcec0f46-2b2a-41df-a59e-4972ae39830d: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 3825627:43e84a51-2886-4b36-9e04-ec43603b33df: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 3825627:c7111a39-6469-4e38-8947-b0b92979400a: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266424 — 2015-11-21 — 0-4

**Why selected:** High-profile away win against a strong opponent.

### Current first impression

- **Real Madrid:** They recorded less passes into the box than in a typical match from this season sample.
- **Barcelona:** They recorded less share of the event possession timeline than in a typical match from this season sample.

### Goal explanations

- **10:06 — Barcelona:** The recorded possession contained 6 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **38:37 — Barcelona:** The recorded possession contained 3 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **52:19 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **73:42 — Barcelona:** The recorded possession contained 6 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **11**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **3**

Broad recurrence-scope flags:

- 266424:11b23607-fae8-4943-9ce7-3bd43cffa04b: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266961 — 2015-12-12 — 2-2

**Why selected:** Two-goal lead lost in a draw, with contrasting match periods.

### Current first impression

- **Barcelona:** They recorded more passes into the box than in a typical match from this season sample.
- **RC Deportivo La Coruña:** They recorded less lost possessions followed quickly by an opposition shot than in a typical match from this season sample.

### Goal explanations

- **38:03 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **61:03 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **76:27 — RC Deportivo La Coruña:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 92% of the scoring team's season matches in the available sample.
- **85:05 — RC Deportivo La Coruña:** The recorded possession contained 1 passes and 1 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **9**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **1**

Broad recurrence-scope flags:

- 266961:75d33711-acaa-4010-bffb-4a7217cc81bc: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266961:9b54e4f5-9c67-43ca-bd5c-f0c27a580351: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266961:a4f91283-6266-490a-aad7-56d3db162411: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266670 — 2016-01-02 — 0-0

**Why selected:** Goalless match that tests cautious and empty goal states.

### Current first impression

- **Espanyol:** They recorded more defensive pressures than in a typical match from this season sample.
- **Barcelona:** They recorded less quality of chances created than in a typical match from this season sample.

### Goal explanations

- No goals to investigate.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **6**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **0**

Broad recurrence-scope flags:

- None.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 267576 — 2016-01-30 — 2-1

**Why selected:** Win despite low recorded chance quality.

### Current first impression

- **Barcelona:** They recorded less quality of chances created than in a typical match from this season sample.
- **Atlético Madrid:** They recorded less share of the event possession timeline than in a typical match from this season sample.

### Goal explanations

- **9:20 — Atlético Madrid:** The recorded possession contained 2 passes and 1 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **29:36 — Barcelona:** The recorded possession contained 3 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **37:41 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **14**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **1**

Broad recurrence-scope flags:

- 267576:12c8b216-0afc-448b-be99-8b6f043373ee: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 267533 — 2016-04-02 — 1-2

**Why selected:** High-profile home defeat.

### Current first impression

- **Barcelona:** They recorded less quality of chances created than in a typical match from this season sample.
- **Real Madrid:** They recorded less share of the event possession timeline than in a typical match from this season sample.

### Goal explanations

- **55:45 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **61:56 — Real Madrid:** The recorded possession contained 7 passes and 3 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **84:36 — Real Madrid:** The recorded possession contained 3 passes and 3 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **15**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **2**

Broad recurrence-scope flags:

- 267533:78f4c78f-0fc8-493b-9321-bdad695a9d36: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266310 — 2016-04-20 — 0-8

**Why selected:** Eight-goal win that tests extreme-output language.

### Current first impression

- **RC Deportivo La Coruña:** They recorded less interceptions than in a typical match from this season sample.
- **Barcelona:** They recorded more interceptions than in a typical match from this season sample.

### Goal explanations

- **10:44 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **23:48 — Barcelona:** The recorded possession contained 6 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **46:23 — Barcelona:** The recorded possession contained 5 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **52:42 — Barcelona:** The recorded possession contained 6 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **63:40 — Barcelona:** The recorded possession contained 4 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **72:26 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **78:05 — Barcelona:** An explicitly identified set play preceded the finish. _Season check:_ This scoring mechanism appears in 100% of the scoring team's season matches in the available sample.
- **80:22 — Barcelona:** The recorded possession contained 5 passes and 6 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **Yes**
- Technical-language hits in visible copy: **16**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **4**

Broad recurrence-scope flags:

- 266310:154b2712-c83d-49e1-9639-275e2aa67df4: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266310:e8b56951-eec6-4a63-8bd0-9e505410045e: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.
- 266310:9f137cbe-5b2d-4f91-a910-387baa93660a: A broad match-level shot occurrence is not the same as recurrence of this goal mechanism.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

## Match 266557 — 2016-04-17 — 1-2

**Why selected:** Defeat despite high shot and territory-related output.

### Current first impression

- **Barcelona:** They recorded more passes into the box than in a typical match from this season sample.
- **Valencia:** They recorded less share of the event possession timeline than in a typical match from this season sample.

### Goal explanations

- **25:17 — Valencia:** The recorded possession contained 5 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **25:17 — Valencia:** The recorded possession contained 5 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **45:15 — Valencia:** The recorded possession contained 5 passes and 5 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.
- **62:57 — Barcelona:** The recorded possession contained 5 passes and 4 carries before the finish. _Season check:_ No comparable recurring season pattern passed the current rule.

### Automated correctness/copy flags

- Goal count agrees with recorded score: **No**
- Technical-language hits in visible copy: **13**
- Unsupported causal-language hits: **0**
- Empty goal sequences: **0**
- Generic open-play history comparisons: **2**

Broad recurrence-scope flags:

- None.

### Human analyst scorecard

- [ ] Accurate and useful
- [ ] Correct but obvious
- [ ] Technically correct but confusing
- [ ] Unsupported by the supplied evidence
- [ ] Important football pattern missed
- [ ] I would open the supporting moments/video

**Analyst notes:**

