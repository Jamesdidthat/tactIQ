"""Deterministic ranking and evidence-pack tests."""

import unittest

import pandas as pd

from src.analysis.finding_prioritization import prioritize_findings
from src.analysis.tactical_findings import MatchAnalysisResult, TacticalFinding
from src.data import ProviderCapabilities


def shape_finding(identifier: str, *, metric: str, sample: int, q95: float, median: float, team_id: str = "team1") -> TacticalFinding:
    return TacticalFinding(
        finding_id=identifier, match_id="m1", team_id=team_id, finding_type="team_shape_extreme",
        title=identifier, description="descriptive", sample_size=sample, confidence_level="descriptive_moderate",
        evidence_metrics={"q95_metres": q95, "peak_metres": q95 + 2, "median_metres": median, "threshold_metres": 30, "metric": metric},
        supporting_references=tuple({"frame": index, "period": 1, "timestamp": f"00:00:0{index}.00"} for index in range(1, 5)),
        required_capabilities=("has_continuous_tracking", "has_verified_roles"), limitations=("descriptive",),
    )


def make_result(findings: list[TacticalFinding]) -> MatchAnalysisResult:
    return MatchAnalysisResult(
        findings=findings,
        analysis_coverage=pd.DataFrame([
            {"analysis": "team_shape", "status": "run", "finding_count": len(findings)},
            {"analysis": "phase_shape_analysis", "status": "run", "finding_count": 0},
            {"analysis": "temporal_shot_analysis", "status": "run", "finding_count": 0},
            {"analysis": "local_defensive_context", "status": "run", "finding_count": 0},
        ]),
        warnings=[], metadata={"provider": "test_provider", "allow_assumed_roles": False, "capabilities": ProviderCapabilities(True, True, True, True, False, False)},
    )


def phase_finding(identifier: str, *, phase: str, dimension: str = "width", sample: int = 30, team_id: str = "team1") -> TacticalFinding:
    return TacticalFinding(
        finding_id=identifier, match_id="m1", team_id=team_id, finding_type="phase_shape_variability",
        title=identifier, description="descriptive", sample_size=sample, confidence_level="descriptive_moderate",
        evidence_metrics={"dimension": dimension, "tactical_phase": phase, "possession_status": "in_possession",
            "q25_metres": 25, "median_metres": 35, "q75_metres": 45, "iqr_metres": 20,
            "sample_unit": "phase intervals", "dimensions_materially_distinct": 1},
        supporting_references=({"frame": sample, "period": 1, "timestamp": "00:01:00.00"},),
        required_capabilities=("has_continuous_tracking", "has_verified_roles", "has_tactical_phases"),
        limitations=("descriptive",),
    )


def shot_finding(identifier: str, *, sample: int, confidence: str = "descriptive_moderate") -> TacticalFinding:
    return TacticalFinding(
        finding_id=identifier, match_id="m1", team_id="team1", finding_type="shot_sequence_density",
        title=identifier, description="descriptive", sample_size=sample, confidence_level=confidence,
        evidence_metrics={"median_preceding_events": 8, "window_seconds": 10},
        supporting_references=({"frame": 10, "period": 1, "timestamp": "00:00:10.00"},),
        required_capabilities=("has_continuous_tracking", "has_events"), limitations=("descriptive",),
    )


class FindingPrioritizationTests(unittest.TestCase):
    def test_ranking_is_stable_when_input_order_changes(self) -> None:
        first = shape_finding("m1:team1:shape_extreme:length", metric="length", sample=600, q95=50, median=30)
        second = shape_finding("m1:team2:shape_extreme:length", metric="length", sample=600, q95=45, median=30, team_id="team2")
        left = prioritize_findings(make_result([first, second]))
        right = prioritize_findings(make_result([second, first]))
        self.assertEqual([x.finding_id for x in left.shortlist], [x.finding_id for x in right.shortlist])

    def test_duplicate_team_shape_metrics_are_suppressed(self) -> None:
        length = shape_finding("m1:team1:shape_extreme:length", metric="length", sample=600, q95=50, median=30)
        width = shape_finding("m1:team1:shape_extreme:width", metric="width", sample=600, q95=48, median=30)
        result = prioritize_findings(make_result([length, width]))
        self.assertEqual(len(result.shortlist), 1)
        self.assertEqual(int(result.priorities.suppressed_as_duplicate.sum()), 1)

    def test_low_sample_raw_extreme_is_penalised(self) -> None:
        low_sample = shape_finding("m1:team1:shape_extreme:low", metric="length", sample=3, q95=100, median=20)
        adequate = shape_finding("m1:team2:shape_extreme:adequate", metric="length", sample=600, q95=45, median=30, team_id="team2")
        result = prioritize_findings(make_result([low_sample, adequate]))
        ranked = result.priorities.set_index("finding_id")
        self.assertGreater(ranked.loc[adequate.finding_id, "priority_score"], ranked.loc[low_sample.finding_id, "priority_score"])

    def test_evidence_pack_preserves_capabilities_and_traceable_moments(self) -> None:
        finding = shape_finding("m1:team1:shape_extreme:length", metric="length", sample=600, q95=50, median=30)
        pack = prioritize_findings(make_result([finding])).evidence_packs[0]
        self.assertEqual(pack.capability_provenance["provider"], "test_provider")
        self.assertTrue(pack.capability_provenance["capabilities"]["has_verified_roles"])
        self.assertEqual(len(pack.representative_moments), 3)
        self.assertIn("timestamp", pack.representative_moments[0])
        self.assertEqual(pack.comparator["type"], "team_frame_median")

    def test_diversified_order_and_selection_reasons_are_input_order_independent(self) -> None:
        findings = [
            phase_finding("m1:team1:phase:a", phase="a"),
            phase_finding("m1:team1:phase:b", phase="b", sample=25),
            shape_finding("m1:team2:shape:length", metric="length", sample=600, q95=48, median=30, team_id="team2"),
            shot_finding("m1:team1:shot", sample=600),
        ]
        left = prioritize_findings(make_result(findings), shortlist_size=4)
        right = prioritize_findings(make_result(list(reversed(findings))), shortlist_size=4)
        self.assertEqual([item.finding_id for item in left.shortlist], [item.finding_id for item in right.shortlist])
        self.assertEqual(left.selection_reasons, right.selection_reasons)
        self.assertIn("top_phase_shape", left.selection_reasons.values())
        self.assertIn("top_team_shape_extreme", left.selection_reasons.values())
        self.assertIn("top_shot_sequence", left.selection_reasons.values())
        self.assertIn("priority_fill", left.selection_reasons.values())

    def test_family_caps_limit_multi_family_shortlist(self) -> None:
        phases = [phase_finding(f"m1:team1:phase:{index}", phase=str(index), sample=30-index) for index in range(4)]
        shapes = [shape_finding(f"m1:team{index}:shape:length", metric="length", sample=600, q95=48-index, median=30, team_id=f"team{index}") for index in range(2, 5)]
        result = prioritize_findings(make_result(phases + shapes), shortlist_size=7, family_caps={"phase_shape": 2, "team_shape_extreme": 2})
        selected = result.priorities.set_index("finding_id").loc[[item.finding_id for item in result.shortlist]]
        self.assertEqual(selected.finding_family.value_counts().to_dict(), {"phase_shape": 2, "team_shape_extreme": 2})
        self.assertEqual(len(result.priorities), len(phases + shapes))
        alternate = prioritize_findings(make_result(phases + shapes), shortlist_size=7, family_caps={"phase_shape": 1, "team_shape_extreme": 1})
        pd.testing.assert_series_equal(
            result.priorities.set_index("finding_id").priority_score.sort_index(),
            alternate.priorities.set_index("finding_id").priority_score.sort_index(),
        )

    def test_minimum_quality_gate_does_not_promote_weak_family(self) -> None:
        strong = phase_finding("m1:team1:phase:a", phase="a")
        weak = shot_finding("m1:team1:weak-shot", sample=3, confidence="descriptive_low")
        result = prioritize_findings(make_result([strong, weak]), shortlist_size=2)
        self.assertEqual([item.finding_id for item in result.shortlist], [strong.finding_id])
        self.assertIn(weak.finding_id, set(result.priorities.finding_id))
        self.assertNotIn(weak.finding_id, result.selection_reasons)

    def test_single_family_fallback_can_fill_beyond_cap(self) -> None:
        findings = [phase_finding(f"m1:team1:phase:{index}", phase=str(index), sample=30-index) for index in range(5)]
        result = prioritize_findings(make_result(findings), shortlist_size=4, family_caps={"phase_shape": 2})
        self.assertEqual(len(result.shortlist), 4)
        reasons = list(result.selection_reasons.values())
        self.assertEqual(reasons.count("top_phase_shape"), 1)
        self.assertEqual(reasons.count("priority_fill"), 1)
        self.assertEqual(reasons.count("single_family_fallback"), 2)

    def test_family_caps_require_positive_integers(self) -> None:
        result = make_result([phase_finding("m1:team1:phase:a", phase="a")])
        for invalid in (0, -1, 1.5, True):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "positive integer"):
                prioritize_findings(result, family_caps={"phase_shape": invalid})


if __name__ == "__main__":
    unittest.main()
