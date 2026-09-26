"""Product-facing quartile evidence, distinct intervals and redundancy rules."""
import unittest

import pandas as pd

from src.analysis.phase_shape import summarize_phase_shape
from src.analysis.phase_shape_evidence import quartile_moments
from src.analysis.tactical_findings import generate_phase_shape_findings
from src.analysis.finding_prioritization import prioritize_findings
from test_finding_prioritization import make_result


def phase_rows(independent=False):
    permutation = [5, 0, 10, 3, 8, 1, 11, 6, 2, 9, 4, 7]
    return pd.DataFrame([{
        'frame': i * 100 + j, 'period': 1, 'team_id': 'A', 'team_acronym': 'AUC',
        'timestamp': f'{i}:{j}', 'elapsed_seconds': i * 10 + j / 10,
        'possession_status': 'in_possession', 'tactical_phase': 'create', 'possession_team_id': 'A',
        'phase_frame_start': i * 100, 'phase_frame_end': i * 100 + 10,
        'outfield_width': 20. + i * 2, 'outfield_length': 25. + (permutation[i] if independent else i) * 2,
    } for i in range(12) for j in range(10)])


def generate(rows):
    summary = summarize_phase_shape(rows.set_index(['frame', 'period', 'team_id', 'team_acronym']))
    return generate_phase_shape_findings(summary, rows, match_id='m1')


class PhaseShapeEvidenceTests(unittest.TestCase):
    def test_distinct_traceable_quartile_examples_stable_under_shuffle(self):
        rows = phase_rows()
        original = rows.copy(deep=True)
        refs = quartile_moments(rows, 'width')
        self.assertEqual(refs, quartile_moments(rows.sample(frac=1, random_state=9), 'width'))
        self.assertEqual([r['label'] for r in refs], ['Narrow example', 'Typical example', 'Wide example'])
        self.assertEqual(len({r['phase_frame_start'] for r in refs}), 3)
        for r in refs:
            source = rows.loc[rows.frame.eq(r['frame'])].iloc[0]
            self.assertEqual(r['metric_value_metres'], source.outfield_width)
            self.assertLessEqual(r['target_error_metres'], 2.75)
            self.assertLess(r['frame'], r['phase_frame_end'])
        pd.testing.assert_frame_equal(rows, original)

    def test_no_invented_examples_with_one_interval_or_missing_values(self):
        rows = phase_rows()
        self.assertEqual(quartile_moments(rows.loc[rows.phase_frame_start.eq(0)], 'width'), ())
        rows.outfield_width = float('nan')
        self.assertEqual(quartile_moments(rows, 'width'), ())

    def test_generator_reports_actual_quartiles_and_interval_samples(self):
        findings = generate(phase_rows())
        self.assertEqual(len(findings), 2)
        width = next(f for f in findings if f.evidence_metrics['dimension'] == 'width')
        self.assertEqual(width.sample_size, 12)
        self.assertEqual(width.evidence_metrics['median_metres'], 31.)
        self.assertEqual(width.evidence_metrics['q25_metres'], 25.5)
        self.assertEqual(width.evidence_metrics['q75_metres'], 36.5)
        self.assertIn('chance creation', width.title)
        self.assertNotIn('create shape', width.title)

    def test_correlated_dimensions_suppressed_independent_dimensions_retained(self):
        correlated = prioritize_findings(make_result(generate(phase_rows())))
        independent = prioritize_findings(make_result(generate(phase_rows(True))))
        self.assertEqual(len(correlated.shortlist), 1)
        self.assertEqual(len(independent.shortlist), 2)
        for pack in independent.evidence_packs:
            self.assertEqual(len(pack.representative_moments), 3)
            self.assertIn('label', pack.representative_moments[0])

    def test_other_phase_not_suppressed(self):
        rows = phase_rows()
        other = rows.copy()
        other.tactical_phase = 'build_up'
        findings = generate(pd.concat([rows, other], ignore_index=True))
        ranked = prioritize_findings(make_result(findings))
        self.assertEqual(len(ranked.shortlist), 2)

    def test_same_frame_interval_in_distinct_periods_is_not_collapsed(self):
        rows = phase_rows().loc[lambda x: x.phase_frame_start.isin([0, 500, 1100])].copy()
        rows['period'] = rows.phase_frame_start.map({0: 1, 500: 2, 1100: 3})
        rows['frame'] = rows.frame % 100
        rows['phase_frame_start'] = 0
        rows['phase_frame_end'] = 10
        refs = quartile_moments(rows, 'width')
        self.assertEqual({ref['period'] for ref in refs}, {1, 2, 3})


if __name__ == '__main__':
    unittest.main()
