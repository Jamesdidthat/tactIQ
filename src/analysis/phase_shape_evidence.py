"""Deterministic, interval-diverse examples of frame-level shape quartiles."""
from itertools import product

import numpy as np
import pandas as pd

INTERVAL_KEY = ['period', 'phase_frame_start', 'phase_frame_end']
PHASE_NAMES = {
    'create': 'chance creation', 'build_up': 'build-up', 'finish': 'finishing attacks',
    'high_block': 'a high block', 'medium_block': 'a mid-block', 'low_block': 'a low block',
    'defending_direct': 'defending direct play', 'defending_transition': 'defensive transitions',
    'defending_quick_break': 'defending quick breaks', 'defending_set_play': 'defending set plays',
    'transition': 'attacking transitions', 'quick_break': 'quick breaks',
    'chaotic': 'provider-labelled chaotic phases',
}


def quartile_moments(rows: pd.DataFrame, dimension: str) -> tuple[dict, ...]:
    """Choose Q25/median/Q75 examples from distinct intervals, never neighbours.

    Retain the nearest frame in each interval for each target, then search the
    six nearest interval candidates per target for the lowest combined error.
    Examples must be within max(1 m, IQR/4) of their targets. If no faithful
    three-interval representation exists, return no examples rather than label
    an unrelated frame as narrow/wide. Quartiles remain frame weighted.
    """
    metric = f'outfield_{dimension}'
    valid = rows.dropna(subset=[metric, 'frame', *INTERVAL_KEY]).copy()
    valid = valid.loc[np.isfinite(valid[metric]) & valid.frame.ge(valid.phase_frame_start) & valid.frame.lt(valid.phase_frame_end)]
    if len(valid[INTERVAL_KEY].drop_duplicates()) < 3:
        return ()
    targets = valid[metric].quantile([.25, .5, .75]).tolist()
    tolerance = max(1., (targets[2] - targets[0]) / 4)
    candidates = []
    for target in targets:
        ranked = valid.assign(error=(valid[metric] - target).abs()).sort_values(['error', *INTERVAL_KEY, 'frame'], kind='stable')
        candidates.append(ranked.loc[ranked.error.le(tolerance)].drop_duplicates(INTERVAL_KEY).head(6).to_dict('records'))
    choices = []
    for triple in product(*candidates):
        if len({tuple(row[key] for key in INTERVAL_KEY) for row in triple}) < 3:
            continue
        if any(a['period'] == b['period'] and abs(a['frame'] - b['frame']) <= 1 for i, a in enumerate(triple) for b in triple[i+1:]):
            continue
        if not triple[0][metric] <= triple[1][metric] <= triple[2][metric]:
            continue
        choices.append(triple)
    if not choices:
        return ()
    chosen = min(choices, key=lambda triple: (sum(row['error'] for row in triple), tuple((row['period'], row['frame']) for row in triple)))
    labels = ('Narrow example', 'Typical example', 'Wide example') if dimension == 'width' else ('Short example', 'Typical example', 'Long example')
    result = []
    for row, target, label, quantile in zip(chosen, targets, labels, (.25, .5, .75)):
        reference = {key: row[key] for key in ('frame', 'period', 'timestamp', 'elapsed_seconds', 'phase_frame_start', 'phase_frame_end') if key in row}
        reference.update(label=label, metric=metric, metric_value_metres=row[metric], target_quantile=quantile,
                         target_value_metres=target, target_error_metres=row['error'])
        result.append(reference)
    return tuple(result)


def dimension_distinction(rows: pd.DataFrame) -> dict:
    """Exploratory duplication rule, not a statistical confidence estimate.

    Separate dimensions only with >=10 complete interval medians, absolute
    Spearman correlation <.7, and at least 30% of intervals placing width and
    length in different quartile bands. Otherwise suppress conservatively.
    """
    paired = rows.groupby(INTERVAL_KEY)[['outfield_width', 'outfield_length']].median().dropna()
    ranks = paired.rank(method='average', pct=True)
    correlation = ranks.outfield_width.corr(ranks.outfield_length) if len(paired) >= 2 else float('nan')
    discordance = float((np.ceil(ranks.outfield_width * 4) != np.ceil(ranks.outfield_length * 4)).mean()) if len(paired) else 0.
    distinct = len(paired) >= 10 and pd.notna(correlation) and abs(correlation) < .7 and discordance >= .3
    return {'dimensions_materially_distinct': int(distinct), 'paired_interval_count': len(paired),
            'width_length_interval_rank_correlation': float(correlation) if pd.notna(correlation) else 'Unavailable',
            'dimension_quartile_disagreement': discordance}
