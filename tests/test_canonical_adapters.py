"""Integration checks that provider adapters share the same core contract."""

from pathlib import Path
import unittest

from src.data import (
    load_metrica_sample_game,
    load_skillcorner_match,
    supported_analyses,
    validate_canonical_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
METRICA = ROOT / "external_data" / "metrica" / "Sample_Game_1"
SKILLCORNER = ROOT / "opendata" / "data" / "matches" / "2017461"


@unittest.skipUnless(METRICA.is_dir() and SKILLCORNER.is_dir(), "local provider sample files are unavailable")
class CanonicalAdapterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metrica = load_metrica_sample_game(METRICA, frame_stride=1000)
        cls.skillcorner = load_skillcorner_match(SKILLCORNER)

    def test_both_providers_satisfy_common_core_contract(self) -> None:
        for bundle in (self.metrica, self.skillcorner):
            validate_canonical_bundle(bundle)
            self.assertEqual(len(bundle.matches), 1)
            self.assertFalse(bundle.player_positions.empty)
            self.assertFalse(bundle.ball_positions.empty)
            self.assertFalse(bundle.attacking_directions.empty)

    def test_capabilities_expose_provider_difference(self) -> None:
        self.assertTrue(self.skillcorner.capabilities.has_verified_roles)
        self.assertTrue(self.skillcorner.capabilities.has_events)
        self.assertTrue(self.skillcorner.capabilities.has_tactical_phases)
        self.assertFalse(self.metrica.capabilities.has_verified_roles)
        self.assertFalse(self.metrica.capabilities.has_events)
        self.assertFalse(self.metrica.capabilities.has_tactical_phases)

    def test_metrica_blocks_role_dependent_analyses_without_development_opt_in(self) -> None:
        support = supported_analyses(self.metrica).set_index("analysis")
        self.assertTrue(support.loc["pitch_visualization", "supported"])
        self.assertFalse(support.loc["team_shape", "supported"])
        self.assertIn("has_verified_roles", support.loc["team_shape", "reason"])

    def test_metrica_assumed_role_map_requires_explicit_opt_in(self) -> None:
        development_bundle = load_metrica_sample_game(
            METRICA, frame_stride=1000, allow_assumed_roles=True
        )
        self.assertTrue(development_bundle.capabilities.has_assumed_roles)
        self.assertFalse(
            supported_analyses(development_bundle)
            .set_index("analysis").loc["team_shape", "supported"]
        )
        self.assertTrue(
            supported_analyses(development_bundle, allow_assumed_roles=True)
            .set_index("analysis").loc["team_shape", "supported"]
        )


if __name__ == "__main__":
    unittest.main()
