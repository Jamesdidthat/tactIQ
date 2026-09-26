# Event-sequence grouping QA and stability audit

Audit date: 2026-09-12

## Scope

Frozen grouping logic was audited across **7 contrasting teams**, **7 moment families**, and **49 team-family cases** from La Liga 2015/2016.

The audit evaluated **392 representative moments** assigned to **150 sequence groups**. Feature weights, distance rules, and grouping thresholds were not changed.

## Overall stability

- Reordered-input partition failures: **0**.
- Minimum leave-one-out assignment stability: **100.0%**.
- Moments in singleton groups: **18.4%**.

## Family summary

| Family | Cases with moments | Moments | Groups | Singleton share | Fragmented cases | Possible merge cases | Close split cases | Reorder failures | Min removal stability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Penalty Area Entries | 7/7 | 56 | 29 | 33.9% | 2 | 0 | 0 | 0 | 100.0% |
| Final Third Entries | 7/7 | 56 | 35 | 37.5% | 5 | 1 | 4 | 0 | 100.0% |
| Shots | 7/7 | 56 | 18 | 10.7% | 0 | 3 | 0 | 0 | 100.0% |
| Interceptions | 7/7 | 56 | 23 | 14.3% | 0 | 0 | 0 | 0 | 100.0% |
| High Regains | 7/7 | 56 | 22 | 19.6% | 0 | 1 | 0 | 0 | 100.0% |
| Set Play Shots | 7/7 | 56 | 16 | 12.5% | 0 | 2 | 1 | 0 | 100.0% |
| Counter Attacks | 7/7 | 56 | 7 | 0.0% | 0 | 4 | 0 | 0 | 100.0% |

## Before vs refined grouping

The comparison uses the exact same selected event IDs in every team-family case.

| Scope | Metric | Before | Refined | Change |
|---|---|---:|---:|---:|
| All families | Groups | 164 | 150 | -14 |
| All families | Singleton share | 20.9% | 18.4% | -2.6% |
| All families | Over-fragmented cases | 7 | 7 | +0 |
| All families | Sequence-length split cases | 18 | 0 | -18 |
| All families | Possible heterogeneous-group cases | 13 | 11 | -2 |
| All families | Very-similar-across-group cases | 5 | 5 | +0 |
| Final-third entries | Groups | 37 | 35 | -2 |
| Final-third entries | Singleton share | 42.9% | 37.5% | -5.4% |
| Final-third entries | Over-fragmented cases | 5 | 5 | +0 |
| Final-third entries | Sequence-length split cases | 2 | 0 | -2 |
| Final-third entries | Possible heterogeneous-group cases | 1 | 1 | +0 |
| Final-third entries | Very-similar-across-group cases | 4 | 4 | +0 |

### Within-group distance check

- All families: median case-level within-group distance changed from 0.209 (Q25 0.158, Q75 0.229) to 0.219 (Q25 0.168, Q75 0.257).
- Final-third entries: median case-level within-group distance changed from 0.110 (Q25 0.074, Q75 0.139) to 0.158 (Q25 0.087, Q75 0.172).

## Recurring deterministic QA flags

- Over-fragmentation: **7/49 cases**.
- Overly generic or inaccurate labels: **0/49 cases**.
- Score state dominating grouping: **0/49 cases**.
- Sequence-length splits among otherwise similar features: **0/49 cases**.
- Set-play/open-play mixing: **0/49 cases**.
- Start/end zones overpowering event type: **0/49 cases**.

## Audit conclusions

- Labels matched their defining signature fields in **49/49 cases**.
- Automated broad-within-group screens flagged **11/49 cases** for manual review; these screens indicate heterogeneous duration, xG, or origin-zone ranges, not proven grouping errors.
- Very close cross-group pairs appeared in **5/49 cases**.
- Fragmentation is concentrated in entry families, especially final-third entries; shot and defensive-event families are materially less fragmented in this representative sample.
- The refinement removed all audited non-zero sequence splits caused only by the former neighboring length bands; the intentional no-context boundary remains.
- Score state and start/end zones do not determine the current group signature, so neither can dominate group assignment. They remain similarity/context features.
- Set-play and open-play contexts remained separated in every audited case.

## Case details

### Barcelona - Penalty Area Entries

Moments: 8 | Groups: 4 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.120 median (10 pairs). Between-group distance: 0.281 median (18 pairs).

### Barcelona - Final Third Entries

Moments: 8 | Groups: 5 | Singleton share: 50.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Wide pass entry after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play wide carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.037 median (6 pairs). Between-group distance: 0.338 median (22 pairs).

### Barcelona - Shots

Moments: 8 | Groups: 4 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Explicit counter central shot after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Open-play central shot after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.180 median (10 pairs). Between-group distance: 0.351 median (18 pairs).

### Barcelona - Interceptions

Moments: 8 | Groups: 4 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after 3+ preceding events - from middle third to unknown destination | 4 | 50.0% | 4 | Yes | No |
| Interception without a preceding relevant event | 2 | 25.0% | 2 | Yes | No |
| Interception after 3+ preceding events - from final third to unknown destination | 1 | 12.5% | 1 | Yes | No |
| Set-play interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.142 median (7 pairs). Between-group distance: 0.453 median (21 pairs).

### Barcelona - High Regains

Moments: 8 | Groups: 4 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Set-play recovery after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Interception without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.168 median (7 pairs). Between-group distance: 0.419 median (21 pairs).

### Barcelona - Set Play Shots

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot without a preceding relevant event | 5 | 62.5% | 5 | Yes | Yes |
| Set-play central shot after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |

Within-group distance: 0.243 median (13 pairs). Between-group distance: 0.406 median (15 pairs).

### Barcelona - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after 3+ preceding events | 8 | 100.0% | 8 | Yes | Yes |

Within-group distance: 0.209 median (28 pairs). Between-group distance: - median (0 pairs).

### Real Madrid - Penalty Area Entries

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Central carry entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Set-play central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.103 median (9 pairs). Between-group distance: 0.274 median (19 pairs).

### Real Madrid - Final Third Entries

Moments: 8 | Groups: 6 | Singleton share: 50.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Wide pass entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play wide pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Wide carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.063 median (2 pairs). Between-group distance: 0.279 median (26 pairs).

### Real Madrid - Shots

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Open-play central shot after 3+ preceding events | 6 | 75.0% | 6 | Yes | Yes |
| Set-play central shot after a possession sequence | 2 | 25.0% | 2 | Yes | No |

Within-group distance: 0.229 median (16 pairs). Between-group distance: 0.383 median (12 pairs).

### Real Madrid - Interceptions

Moments: 8 | Groups: 4 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after 3+ preceding events - from middle third to unknown destination | 3 | 37.5% | 3 | Yes | No |
| Interception without a preceding relevant event | 2 | 25.0% | 2 | Yes | No |
| Set-play interception after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Interception after 3+ preceding events - from final third to unknown destination | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.187 median (5 pairs). Between-group distance: 0.428 median (23 pairs).

### Real Madrid - High Regains

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Set-play recovery after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Recovery without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.256 median (9 pairs). Between-group distance: 0.371 median (19 pairs).

### Real Madrid - Set Play Shots

Moments: 8 | Groups: 2 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 7 | 87.5% | 7 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.245 median (21 pairs). Between-group distance: 0.401 median (7 pairs).

### Real Madrid - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after 3+ preceding events | 8 | 100.0% | 8 | Yes | No |

Within-group distance: 0.259 median (28 pairs). Between-group distance: - median (0 pairs).

### Atlético Madrid - Penalty Area Entries

Moments: 8 | Groups: 5 | Singleton share: 50.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Explicit counter central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.156 median (6 pairs). Between-group distance: 0.345 median (22 pairs).

### Atlético Madrid - Final Third Entries

Moments: 8 | Groups: 5 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Wide pass entry after a possession sequence | 3 | 37.5% | 3 | Yes | No |
| Wide carry entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Set-play wide pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.162 median (4 pairs). Between-group distance: 0.357 median (24 pairs).

### Atlético Madrid - Shots

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Open-play central shot after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Set-play central shot after a possession sequence | 2 | 25.0% | 2 | Yes | No |
| Explicit counter central shot after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.226 median (11 pairs). Between-group distance: 0.366 median (17 pairs).

### Atlético Madrid - Interceptions

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Interception without a preceding relevant event | 2 | 25.0% | 2 | Yes | No |
| Set-play interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.189 median (11 pairs). Between-group distance: 0.417 median (17 pairs).

### Atlético Madrid - High Regains

Moments: 8 | Groups: 3 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 6 | 75.0% | 6 | Yes | No |
| Explicit counter recovery after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play recovery after a short possession sequence | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.199 median (15 pairs). Between-group distance: 0.523 median (13 pairs).

### Atlético Madrid - Set Play Shots

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 5 | 62.5% | 5 | Yes | No |
| Set-play central shot without a preceding relevant event | 3 | 37.5% | 3 | Yes | Yes |

Within-group distance: 0.326 median (13 pairs). Between-group distance: 0.347 median (15 pairs).

### Atlético Madrid - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after a possession sequence | 8 | 100.0% | 8 | Yes | No |

Within-group distance: 0.206 median (28 pairs). Between-group distance: - median (0 pairs).

### Las Palmas - Penalty Area Entries

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Central carry entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Set-play central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.179 median (9 pairs). Between-group distance: 0.397 median (19 pairs).

### Las Palmas - Final Third Entries

Moments: 8 | Groups: 5 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Wide pass entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | Yes |
| Central pass entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry after a short possession sequence | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.182 median (4 pairs). Between-group distance: 0.421 median (24 pairs).

### Las Palmas - Shots

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Open-play central shot after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Set-play central shot after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Set-play wide shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.227 median (9 pairs). Between-group distance: 0.407 median (19 pairs).

### Las Palmas - Interceptions

Moments: 8 | Groups: 4 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after a possession sequence | 3 | 37.5% | 3 | Yes | No |
| Interception without a preceding relevant event | 2 | 25.0% | 2 | Yes | No |
| Set-play interception after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.280 median (5 pairs). Between-group distance: 0.483 median (23 pairs).

### Las Palmas - High Regains

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Set-play recovery after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Set-play interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.195 median (11 pairs). Between-group distance: 0.413 median (17 pairs).

### Las Palmas - Set Play Shots

Moments: 8 | Groups: 3 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 6 | 75.0% | 6 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Set-play wide shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.346 median (15 pairs). Between-group distance: 0.447 median (13 pairs).

### Las Palmas - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after a possession sequence | 8 | 100.0% | 8 | Yes | Yes |

Within-group distance: 0.265 median (28 pairs). Between-group distance: - median (0 pairs).

### Sporting Gijón - Penalty Area Entries

Moments: 8 | Groups: 4 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central carry entry after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Central pass entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Explicit counter central carry entry after a short possession sequence | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.213 median (7 pairs). Between-group distance: 0.401 median (21 pairs).

### Sporting Gijón - Final Third Entries

Moments: 8 | Groups: 4 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Wide pass entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Central carry entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central pass entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Explicit counter central carry entry after a short possession sequence | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.110 median (5 pairs). Between-group distance: 0.340 median (23 pairs).

### Sporting Gijón - Shots

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Open-play central shot after 3+ preceding events | 6 | 75.0% | 6 | Yes | Yes |
| Set-play central shot after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |

Within-group distance: 0.234 median (16 pairs). Between-group distance: 0.322 median (12 pairs).

### Sporting Gijón - Interceptions

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after 3+ preceding events - from middle third to unknown destination | 4 | 50.0% | 4 | Yes | No |
| Interception without a preceding relevant event | 3 | 37.5% | 3 | Yes | No |
| Interception after 3+ preceding events - from final third to unknown destination | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.257 median (9 pairs). Between-group distance: 0.390 median (19 pairs).

### Sporting Gijón - High Regains

Moments: 8 | Groups: 3 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 6 | 75.0% | 6 | Yes | Yes |
| Interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play recovery after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.219 median (15 pairs). Between-group distance: 0.375 median (13 pairs).

### Sporting Gijón - Set Play Shots

Moments: 8 | Groups: 2 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 7 | 87.5% | 7 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.327 median (21 pairs). Between-group distance: 0.358 median (7 pairs).

### Sporting Gijón - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after a possession sequence | 8 | 100.0% | 8 | Yes | No |

Within-group distance: 0.287 median (28 pairs). Between-group distance: - median (0 pairs).

### Granada - Penalty Area Entries

Moments: 8 | Groups: 6 | Singleton share: 62.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central carry entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Explicit counter central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.154 median (3 pairs). Between-group distance: 0.409 median (25 pairs).

### Granada - Final Third Entries

Moments: 8 | Groups: 6 | Singleton share: 50.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Central pass entry after a possession sequence | 2 | 25.0% | 2 | Yes | No |
| Wide carry entry after 3+ preceding events | 2 | 25.0% | 2 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Explicit counter central carry entry after a short possession sequence | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Wide pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.226 median (2 pairs). Between-group distance: 0.430 median (26 pairs).

### Granada - Shots

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Open-play central shot after 3+ preceding events | 8 | 100.0% | 8 | Yes | No |

Within-group distance: 0.237 median (28 pairs). Between-group distance: - median (0 pairs).

### Granada - Interceptions

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after a possession sequence | 5 | 62.5% | 5 | Yes | No |
| Interception without a preceding relevant event | 3 | 37.5% | 3 | Yes | No |

Within-group distance: 0.275 median (13 pairs). Between-group distance: 0.379 median (15 pairs).

### Granada - High Regains

Moments: 8 | Groups: 4 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 5 | 62.5% | 5 | Yes | No |
| Interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Recovery without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Set-play recovery after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.173 median (10 pairs). Between-group distance: 0.395 median (18 pairs).

### Granada - Set Play Shots

Moments: 8 | Groups: 3 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 6 | 75.0% | 6 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Set-play wide shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.382 median (15 pairs). Between-group distance: 0.374 median (13 pairs).

### Granada - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after a possession sequence | 8 | 100.0% | 8 | Yes | Yes |

Within-group distance: 0.231 median (28 pairs). Between-group distance: - median (0 pairs).

### Sevilla - Penalty Area Entries

Moments: 8 | Groups: 4 | Singleton share: 37.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central pass entry without a preceding relevant event | 5 | 62.5% | 5 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Central pass entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Set-play central pass entry after a short possession sequence | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.103 median (10 pairs). Between-group distance: 0.452 median (18 pairs).

### Sevilla - Final Third Entries

Moments: 8 | Groups: 4 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central pass entry without a preceding relevant event | 3 | 37.5% | 3 | Yes | No |
| Wide pass entry after 3+ preceding events | 3 | 37.5% | 3 | Yes | No |
| Central carry entry after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |
| Wide pass entry without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.158 median (6 pairs). Between-group distance: 0.557 median (22 pairs).

### Sevilla - Shots

Moments: 8 | Groups: 3 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 5 | 62.5% | 5 | Yes | No |
| Open-play central shot after 3+ preceding events | 2 | 25.0% | 2 | Yes | Yes |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.278 median (11 pairs). Between-group distance: 0.410 median (17 pairs).

### Sevilla - Interceptions

Moments: 8 | Groups: 3 | Singleton share: 25.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Interception after 3+ preceding events | 6 | 75.0% | 6 | Yes | No |
| Interception without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |
| Set-play interception after 3+ preceding events | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.157 median (15 pairs). Between-group distance: 0.339 median (13 pairs).

### Sevilla - High Regains

Moments: 8 | Groups: 2 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Recovery after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |
| Set-play recovery after 3+ preceding events | 4 | 50.0% | 4 | Yes | No |

Within-group distance: 0.287 median (12 pairs). Between-group distance: 0.354 median (16 pairs).

### Sevilla - Set Play Shots

Moments: 8 | Groups: 2 | Singleton share: 12.5% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Set-play central shot after a possession sequence | 7 | 87.5% | 7 | Yes | No |
| Set-play central shot without a preceding relevant event | 1 | 12.5% | 1 | Yes | No |

Within-group distance: 0.263 median (21 pairs). Between-group distance: 0.323 median (7 pairs).

### Sevilla - Counter Attacks

Moments: 8 | Groups: 1 | Singleton share: 0.0% | Reorder stable: Yes | Leave-one-out stability: 100.0%

| Pattern | N | Share | Matches | Label accurate | Possible merge flag |
|---|---:|---:|---:|---|---|
| Explicit counter central shot after a possession sequence | 8 | 100.0% | 8 | Yes | Yes |

Within-group distance: 0.250 median (28 pairs). Between-group distance: - median (0 pairs).

## Interpretation limits

- This audit uses deterministic representative selections of at most eight moments per team-family case.
- The sequence context is bounded by the existing Moment Detail window and relevant-event filter.
- Automated merge/split flags identify review candidates; they are not tactical judgments.
- No 360 geometry, tracking, defensive shape, passing lanes, pressing, overloads, or tactical intent is used.

The machine-readable artifact preserves all group definitions, representative IDs, similarity distributions, close split pairs, label checks, and removal/reordering results.
