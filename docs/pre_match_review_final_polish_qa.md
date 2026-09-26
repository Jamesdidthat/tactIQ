# Pre-Match Review Final Correctness and UI QA

## Scope

This pass changed presentation only. Source qualification, the priority-score
formula, source-role precedence, semantic grouping, the 0.58/0.66/0.72 slot
thresholds, the family cap of two, and shortlist maximum of five were unchanged.

The audit reran all 190 La Liga 2015/16 team-season pairings and reviewed the
same 10 contrasting pairings used in the previous product QA.

## Automated language audit

- Final priorities audited: 274.
- Plural-subject/singular-verb errors: 0.
- Title-to-primary-metric specificity mismatches: 0.
- Previous 10-pair shortlist identities and ordering changed: no.
- Shortlist distribution remained: 0: 71, 1: 50, 2: 27, 3: 11, 4: 18,
  5: 13.

Metric questions now use an explicit grammatical-number table. Examples:

- `Review how Real Madrid's interceptions per 90 differ from Barcelona's.`
- `Review how Sporting Gijon's pass completion rate differs from Barcelona's.`
- `Review how Las Palmas' high regains per 90 differ from Atletico Madrid's.`
- `Review how Villarreal's xG per shot differs from Real Madrid's.`

## Title specificity

Every selected general-comparison title contains its exact primary metric label.
Every selected directional title contains its exact interaction concept. The
audit found no remaining broad `Defensive activity`, `Shot quality`, or similar
titles standing in for a single narrower measurement.

Examples include `Interceptions per 90`, `Pass completion rate`, `Shots on target
per 90`, `Penalty-area entries`, `Shots`, and `xG`. Broader football-family names
remain metadata for grouping and do not replace the card title.

## Focused UI review

The production frontend was checked against the real pre-match response contract.

- Cards now say `Evidence support: High / Moderate / Limited`.
- Help text states that evidence support represents sample adequacy and
  season-relative evidence quality—not tactical importance, causality, or
  prediction confidence.
- Primary cards display the readable roles `Directional matchup interaction` or
  `General team comparison`.
- `Supporting tendency` is identified when recurring tendency support exists.
- Technical source IDs are absent from the primary card and available inside the
  expanded `Why this was selected` provenance section.
- Long source-role metadata wraps rather than overflowing the card.
- High, Moderate, and Limited visual states are supported, although no selected
  priority in this adequately covered 190-pair sample had a Limited label.

## Remaining wording considerations

No correctness issue remains in the audited output. Two deliberate product
trade-offs remain:

1. General-comparison questions repeat the `Review how ... differs from ...`
   structure. This is less varied than authored prose but makes grammatical
   behavior and metric provenance predictable.
2. Directional questions retain `usual defensive exposure`. That wording is
   slightly analytical, but it accurately distinguishes a conceded season
   baseline from the attacking team's production and avoids implying a forecast.

The machine-readable audit is
`artifacts/pre_match_review_priority_qa_polish_v5.json`.
