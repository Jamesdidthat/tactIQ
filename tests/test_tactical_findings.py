"""Finding contract and provider-capability orchestration tests."""

from pathlib import Path
import unittest

from src.analysis.tactical_findings import TacticalFinding, run_match_analysis
from src.data import load_metrica_sample_game, load_skillcorner_match


ROOT = Path(__file__).resolve().parents[1]
METRICA = ROOT / "external_data" / "metrica" / "Sample_Game_1"
SKILLCORNER = ROOT / "opendata" / "data" / "matches" / "2017461"


class TacticalFindingContractTests(unittest.TestCase):
    def test_rejects_non_positive_sample_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample_size"):
            TacticalFinding(
                finding_id="x", match_id="m", team_id="t", finding_type="test", title="title", description="description",
                evidence_metrics={"value": 1}, sample_size=0, confidence_level="descriptive_low",
                supporting_references=(), required_capabilities=("has_continuous_tracking",), limitations=(),
            )


@unittest.skipUnless(METRICA.is_dir() and SKILLCORNER.is_dir(), "local provider sample files are unavailable")
class MatchAnalysisOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metrica = load_metrica_sample_game(METRICA, frame_stride=1000)
        cls.skillcorner = load_skillcorner_match(SKILLCORNER)

    def test_metrica_without_verified_roles_emits_no_role_dependent_findings(self) -> None:
        result = run_match_analysis(self.metrica)
        coverage = result.analysis_coverage.set_index("analysis")
        self.assertEqual(result.findings, [])
        self.assertEqual(coverage.loc["team_shape", "status"], "skipped")
        self.assertIn("has_verified_roles", coverage.loc["team_shape", "reason"])

    def test_skillcorner_runs_deterministic_supported_modules_only(self) -> None:
        result = run_match_analysis(self.skillcorner)
        coverage = result.analysis_coverage.set_index("analysis")
        self.assertEqual(coverage.loc["team_shape", "status"], "run")
        self.assertEqual(coverage.loc["phase_shape_analysis", "status"], "run")
        self.assertTrue(result.findings)
        for finding in result.findings:
            self.assertTrue(set(finding.required_capabilities).issubset({
                "has_continuous_tracking", "has_ball_tracking", "has_verified_roles",
                "has_attacking_direction", "has_events", "has_tactical_phases",
            }))

    def test_assumed_metrica_roles_stay_blocked_without_orchestrator_opt_in(self) -> None:
        development_bundle = load_metrica_sample_game(METRICA, frame_stride=1000, allow_assumed_roles=True)
        result = run_match_analysis(development_bundle)
        self.assertEqual(result.analysis_coverage.set_index("analysis").loc["team_shape", "status"], "skipped")
        self.assertFalse(any(f.finding_type == "team_shape_extreme" for f in result.findings))


if __name__ == "__main__":
    unittest.main()
