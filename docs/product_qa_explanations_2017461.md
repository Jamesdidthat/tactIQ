# Explanation product QA — match 2017461

Run date: 2026-09-07

## Execution status

Six shortlisted findings were loaded through `MatchAnalysisService`, with their
real EvidencePacks and explanation endpoint responses. The configured provider
was the default `deterministic` backend, so all six responses correctly used
`deterministic_fallback`. No model-generated explanation was available to
evaluate, and this report does not represent fallback prose as AI output.

The captured source payload is
`artifacts/ui_review/explanation_qa_inputs_2017461.json`. Re-running
`python -m scripts.qa_explanations_2017461` after selecting and configuring an
`openai` or `local` provider will replace the capture with model outputs suitable
for the missing AI-versus-evidence review.

## Fallback review

| Rank | Finding | Summary clearer than deterministic text? | Why-it-matters usefulness | Video-review support | Confidence note | Fallback assessment |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | AUC width during chance creation: narrower and wider shapes | No; it repeats the description exactly. | Weak and generic; it says only that recurrence may be worth assessing. | Partly supported: width is visible, but it mentions only Narrow and Typical and omits the Wide example. | Appropriately cautious and names 44 phase intervals. | Safe, but materially less useful than a good football explanation. |
| 2 | AUC width during finishing attacks: narrower and wider shapes | No; exact repetition. | Weak and identical to rank 1 apart from the implied dimension. | Partly supported: the supplied frames show width, but Wide is again omitted. | Appropriately cautious and names 25 intervals. | Safe but repetitive. |
| 3 | AUC length during defending direct play: shorter and longer shapes | No; exact repetition. | Weak and generic; no direct-play-specific football context is added. | Partly supported: line length can be inspected, but Short and Typical are named while Long is omitted. | Appropriately cautious and names 26 intervals. | Grounded, but not meaningfully explanatory. |
| 4 | AUC length during a low block: shorter and longer shapes | No; exact repetition. | Weak; it does not explain what changing low-block length might allow an analyst to inspect. | Partly supported: vertical spacing is observable, but the Long example is omitted. | Appropriately cautious and names 39 intervals. | The deterministic evidence is as useful as the fallback. |
| 5 | Auckland FC outfield length: typical and more extended shapes | No; exact repetition. | Weak and generic. | Supported: Typical and Extended are the two supplied evidence moments, and outfield length is directly visible. | Cautious, but 40,404 tracked frames may sound more independent than they are; the episode limitation remains important. | Safe and grounded; only marginally more structured than the evidence itself. |
| 6 | Melbourne Victory outfield length: typical and more extended shapes | No; exact repetition. | Weak and generic. | Supported: the Typical and Extended frames directly expose vertical spacing, with the extended moment labelled chaotic. | Cautious, with the same frame-independence caveat as rank 5. | Safe and grounded; deterministic evidence is just as informative. |

## Cross-finding conclusions

- Grounding passed: the fallback introduced no unsupported numerical claims,
  causes, or tactical recommendations.
- Clarity did not improve: every plain-English summary is the deterministic
  description verbatim.
- `why_it_matters` is repeated across all six findings and adds almost no
  phase-specific football value.
- Video guidance is genuinely inspectable for the two team-shape extremes.
  For the four phase-shape findings it is incomplete because it ignores the
  third quartile example.
- Confidence notes are cautious and transparent about sample units. For the
  frame-level extremes, analysts still need the adjacent-frame/episode
  limitation to avoid reading 40,404 frames as independent observations.
- In the current no-model state, fallback is often just as good as the
  deterministic title and EvidencePack because it mostly restates them. It is
  not good enough to establish that the AI layer adds product value.

## Remaining model QA gate

The requested AI evaluation remains open until a configured model produces six
validated `source: model` responses. The acceptance review should compare those
responses against this fallback baseline and reject the AI layer for product
use if it remains generic, repeats the evidence, omits supplied moments, or
turns possible interpretations into tactical prescriptions.
