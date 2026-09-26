# Phase-shape finding and presentation revision

Phase-shape findings now describe width or length independently. Titles name
the team, the football phase and the observed narrower/wider or shorter/longer
shapes. Descriptions report Q25, median and Q75 in metres, and interval count.
They do not imply improvement, weakness or causation.

## Evidence selection

- Preserve the existing frame-weighted distribution: longer intervals still
  contribute more frames. Report this explicitly in the limitations.
- Require at least 50 valid frames and an interquartile spread of at least 8 m
  for the individual dimension.
- Select Q25, median and Q75 examples from three different source intervals,
  identified by period, start frame and exclusive end frame.
- For each target, consider the nearest frame from each interval. Search the
  six best interval candidates per target for the minimum total absolute
  target error, breaking ties by period/frame. Reject adjacent frames and
  examples whose metric order contradicts their lower/typical/upper labels.
- Require target error no greater than max(1 m, IQR/4). Suppress the candidate
  finding if three faithful examples cannot be selected. This bounded search
  is conservative and is not a guarantee of a globally optimal assignment.
- Each EvidencePack moment retains its source reference and adds `label`,
  `metric`, `metric_value_metres`, `target_quantile`, `target_value_metres`,
  and `target_error_metres`. Width labels are Narrow/Typical/Wide example;
  length labels are Short/Typical/Long example.

## Duplicate grouping and evidence

Groups retain team, possession status and exact phase, so different football
contexts are not automatically duplicates. Within a context, width and length
share a group unless at least 10 complete interval medians establish both:

- absolute width/length Spearman rank correlation below 0.70;
- at least 30% of intervals place width and length in different quartile bands.

Each dimension must also independently pass the 8 m spread and evidence rules.
These are explicit exploratory product thresholds, not significance tests or
proof of independent tactical mechanisms. Counts, correlation and disagreement
are retained in the evidence metrics. Undefined correlation suppresses a
second dimension conservatively.

Sample size for these findings now means source phase intervals; frame count
is retained separately. Moderate descriptive evidence requires 10 intervals;
the ranking sample component reaches its maximum at 20 intervals. These
categories and components are heuristic, not calibrated confidence.

## Product presentation

The frame serializer exposes optional canonical `player_number`, preferring
roster metadata and using tracking metadata as a fallback. The SkillCorner
adapter now retains supplied shirt numbers in its canonical roster. The UI
uses the number when available and leaves the player ID as a fallback, with
an explicit tooltip for missing shirt numbers.

Football distances display one decimal place, while JSON retains full
precision. Metric rows wrap within the detail panel. Evidence is categorical
(Moderate/Low), and Priority uses High/Medium/Low bands at 0.75 and 0.50.
Raw ranking components remain available in a collapsed, explicitly labelled
0–1 section. They are never displayed as statistical confidence or percentage
change. Quartile example buttons show the actual distance and target distance.

Focused validation covers shuffled input stability, exact source references,
quartile values, missing evidence, duplicate suppression, distinct contexts,
roster number serialization and unchanged player-position input data.

## Real-match verification: 2017461

The updated service returns ten shortlisted phase-shape findings. All thirty
representative frames were checked against the returned player coordinates:
the outfield x/y span equals the labelled metric, interval membership is valid,
each finding uses three distinct intervals, and shirt numbers are available
for all players in these frames. Sixteen focused Python tests passed; the
React/TypeScript production build passed.

For the first finding, **AUC width during chance creation: narrower and wider
shapes**, the sample is 44 intervals / 3,477 frames:

| Example | Width / target | Match timestamp | Period | Source interval [start, end) |
| --- | --- | --- | --- | --- |
| Narrow | 35.7 m / Q25 35.7 m | 01:30:36.50 | 2 | [66971, 67152) |
| Typical | 45.0 m / median 45.0 m | 00:13:38.80 | 1 | [10646, 10725) |
| Wide | 53.8 m / Q75 53.8 m | 00:26:47.70 | 1 | [18515, 18626) |

Rendered-browser inspection confirms labelled quartile buttons, one-decimal
distances, wrapped metric rows, categorical Evidence/Priority, and shirt-number
markers. Screenshot: `artifacts/ui_review/revised/finding_1.png`.
Machine-readable evidence checks: `artifacts/ui_review/phase_evidence_verified.json`.

Product limitation retained for review: because phase contexts now have their
own duplicate groups, all ten shortlist slots are occupied by phase-shape
findings. This revision improves their evidence but does not establish that
the resulting list has sufficient variety or coaching relevance.
