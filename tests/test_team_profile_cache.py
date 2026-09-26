"""Compact Team Profile precomputation and cache behavior."""

import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.analysis import TeamProfileArtifactStore, TeamProfileIdentity, precompute_team_profile
from src.api import TeamProfileService
from tests.test_match_analysis_service import make_bundle


class TeamProfileCacheTests(unittest.TestCase):
    def resolver(self, calls=None):
        def resolve(team_id):
            if calls is not None:
                calls.append(team_id)
            identity = TeamProfileIdentity("club", "Test Club", {"provider_one": "h"})
            excluded = [{"match_id": "bad", "provider": "provider_one", "reason": "canonical preflight failed"}]
            return identity, iter([make_bundle("provider_one", "one"), make_bundle("provider_one", "two")]), excluded
        return resolve

    def test_precompute_persists_compact_inputs_exclusions_and_reconstructs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TeamProfileArtifactStore(directory)
            result, path = precompute_team_profile("provider_one", "club", self.resolver(), store)
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(len(payload["matches"]), 2)
            self.assertEqual(len(payload["exclusions"]), 1)
            self.assertIn("has_continuous_tracking", payload["matches"][0]["capabilities"])
            self.assertIn("profile_metrics", payload["matches"][0])
            self.assertNotIn("player_positions", path.read_text(encoding="utf-8"))

            reconstructed = store.load("provider_one", "club")
            self.assertIsNotNone(reconstructed)
            original = result.aggregate_patterns.drop(columns="match_ids").astype(object).where(pd.notna(result.aggregate_patterns.drop(columns="match_ids")), "<missing>")
            restored = reconstructed.aggregate_patterns.drop(columns="match_ids").astype(object).where(pd.notna(reconstructed.aggregate_patterns.drop(columns="match_ids")), "<missing>")
            pd.testing.assert_frame_equal(
                original,
                restored,
                check_dtype=False,
            )
            self.assertEqual(reconstructed.matches_excluded.reason.tolist(), ["canonical preflight failed"])

    def test_service_reuses_valid_cache_without_calling_live_resolver(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TeamProfileArtifactStore(directory)
            precompute_team_profile("provider_one", "club", self.resolver(), store)
            calls = []
            service = TeamProfileService(
                self.resolver(calls), artifact_store=store, provider="provider_one"
            )
            first = service.summary("club")
            second = service.metrics("club")
            self.assertEqual(first["analysed_match_count"], 2)
            self.assertTrue(second["metric_baselines"])
            self.assertEqual(calls, [])

            catalog = service.catalog()
            self.assertEqual(len(catalog["profiles"]), 1)
            self.assertEqual(catalog["profiles"][0]["team_name"], "Test Club")
            self.assertEqual(catalog["profiles"][0]["analysed_match_count"], 2)
            self.assertEqual(catalog["profiles"][0]["excluded_match_count"], 1)
            self.assertTrue(catalog["profiles"][0]["has_continuous_tracking"])

    def test_schema_or_profile_version_mismatch_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TeamProfileArtifactStore(directory)
            _, path = precompute_team_profile("provider_one", "club", self.resolver(), store)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["profile_version"] = "obsolete"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIsNone(store.load("provider_one", "club"))

            current = TeamProfileArtifactStore(directory)
            precompute_team_profile("provider_one", "club", self.resolver(), current)
            incompatible = TeamProfileArtifactStore(directory, schema_version="future-schema")
            self.assertIsNone(incompatible.load("provider_one", "club"))


if __name__ == "__main__":
    unittest.main()
