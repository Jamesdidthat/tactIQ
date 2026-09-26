"""Deterministic pre-match briefing contract and product-service tests."""

import json
from pathlib import Path
import shutil
import tempfile
from threading import Thread
import unittest
from urllib.request import urlopen

from http.server import ThreadingHTTPServer

import pandas as pd

from src.analysis import (
    PreMatchReviewResult,
    build_pre_match_briefing,
    compare_event_team_profiles,
)
from src.api.event_profile_service import (
    artifact_event_profile_resolver, event_profile_artifact_catalog,
    load_event_profile_artifact,
)
from src.api.http_server import LocalAnalysisHandler
from src.api.opponent_comparison_service import OpponentComparisonService
from src.data import StatsBombOpenDataAdapter


IDENTITY = (
    "statsbomb_open_data", 217, 11, 27,
    "statsbomb_open_data", 220, 11, 27,
)


class PreMatchBriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artifacts = Path(__file__).resolve().parents[1] / "artifacts"
        profile_dir = artifacts / "event_profiles" / "statsbomb_11_27"
        cls.profiles = {
            "217": load_event_profile_artifact(profile_dir / "statsbomb_11_27_217_event_profile_v1.json"),
            "220": load_event_profile_artifact(profile_dir / "statsbomb_11_27_220_event_profile_v1.json"),
        }
        cls.service = OpponentComparisonService(artifact_event_profile_resolver(artifacts))
        adapter = StatsBombOpenDataAdapter(
            Path(__file__).resolve().parents[1] / "external_data" / "statsbomb_open_data"
        )
        bundle_cache = {}

        def bundle_resolver(provider, match_id):
            if provider != "statsbomb_open_data":
                raise KeyError(provider)
            if int(match_id) not in bundle_cache:
                bundle_cache[int(match_id)] = adapter.load_match(int(match_id))
            return bundle_cache[int(match_id)]

        cls.evidence_service = OpponentComparisonService(
            artifact_event_profile_resolver(artifacts), bundle_resolver,
        )

    def test_service_preserves_selected_priority_identity_rank_and_order(self):
        selected = self.service.review_priorities(*IDENTITY)["review_priorities"]
        payload = self.service.pre_match_briefing(*IDENTITY)
        briefing = payload["briefing"]
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(
            [item["priority_id"] for item in briefing["review_priorities"]],
            [item["priority_id"] for item in selected],
        )
        self.assertEqual(
            [item["rank"] for item in briefing["review_priorities"]],
            list(range(1, len(selected) + 1)),
        )
        self.assertEqual(len(briefing["evidence_pack_links"]), len(selected))
        self.assertTrue(all(
            "%3A" in item["evidence_pack_link"]
            for item in briefing["review_priorities"]
        ))
        json.dumps(payload, allow_nan=False)

    def test_directional_summary_uses_attack_and_defensive_exposure(self):
        briefing = self.service.pre_match_briefing(*IDENTITY)["briefing"]
        directional = next(
            item for item in briefing["review_priorities"]
            if item["primary_source_role"] == "directional_matchup_interaction"
        )
        self.assertIn("attacking median", directional["evidence_summary"])
        self.assertIn("defensive-exposure median", directional["evidence_summary"])
        self.assertNotIn("should", directional["evidence_summary"].lower())
        self.assertNotIn("will", directional["evidence_summary"].lower())

    def test_empty_shortlist_has_explicit_cautious_state(self):
        comparison = compare_event_team_profiles(self.profiles["217"], self.profiles["220"])
        review = PreMatchReviewResult(
            target=comparison.target,
            opponent=comparison.opponent,
            priorities=[],
            candidate_audit=pd.DataFrame(),
            configuration={"maximum_priorities": 5},
        )
        briefing = build_pre_match_briefing(review, comparison, identity=IDENTITY)
        self.assertEqual(briefing.review_priorities, ())
        self.assertEqual(briefing.evidence_pack_links, {})
        self.assertIn("No matchup themes qualified", briefing.briefing_summary)
        self.assertIn("does not mean", briefing.briefing_summary)

    def test_briefing_is_compact_and_does_not_embed_evidence_packs(self):
        briefing = self.service.pre_match_briefing(*IDENTITY)["briefing"]
        self.assertNotIn("representative_moments", briefing)
        self.assertNotIn("technical_provenance", briefing)
        self.assertEqual(briefing["video_availability"]["status"], "unavailable")
        self.assertFalse(briefing["data_capabilities"]["continuous_tracking_used"])

    def test_barcelona_real_madrid_briefing_resolves_through_http_route(self):
        class BriefingHandler(LocalAnalysisHandler):
            opponent_comparison_service = self.service
            event_profile_catalog = event_profile_artifact_catalog(
                Path(__file__).resolve().parents[1] / "artifacts"
            )

        server = ThreadingHTTPServer(("127.0.0.1", 0), BriefingHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = (
                f"http://127.0.0.1:{server.server_port}/opponent-comparisons/"
                "statsbomb_open_data/217/11/27/statsbomb_open_data/220/11/27/briefing"
            )
            with urlopen(url, timeout=30) as response:
                status = response.status
                payload = json.load(response)
            self.assertEqual(status, 200)
            self.assertEqual(payload["schema_version"], "v1")
            self.assertEqual(
                [item["priority_id"] for item in payload["briefing"]["review_priorities"]],
                [item["priority_id"] for item in self.service.review_priorities(*IDENTITY)["review_priorities"]],
            )
            with urlopen(f"http://127.0.0.1:{server.server_port}/event-profile-catalog", timeout=30) as response:
                catalog_status = response.status
                catalog = json.load(response)
            self.assertEqual(catalog_status, 200)
            self.assertTrue(any(item["team_name"] == "Barcelona" for item in catalog["profiles"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_barcelona_levante_progressive_carry_pack_has_faithful_moments(self):
        identity = (
            "statsbomb_open_data", 217, 11, 27,
            "statsbomb_open_data", 221, 11, 27,
        )
        priorities = self.evidence_service.review_priorities(*identity)["review_priorities"]
        selected = next(
            item for item in priorities
            if item["priority_id"].endswith(":progressive_carries_per90")
        )
        payload = self.evidence_service.review_priority_evidence_pack(
            *identity, priority_id=selected["priority_id"],
        )
        pack = payload["evidence_pack"]
        self.assertEqual(len(pack["representative_moments"]), 8)
        self.assertTrue(all(item["event_type"] == "Carry" for item in pack["representative_moments"]))
        self.assertTrue(all(
            "progressive_carry_definition" in item["relevant_values"]
            for item in pack["representative_moments"]
        ))
        self.assertEqual(len({
            (item["source_provenance"]["provider"], item["event_id"])
            for item in pack["representative_moments"]
        }), 8)


class EventProfileArtifactResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1]
            / "artifacts" / "event_profiles" / "statsbomb_11_27"
            / "statsbomb_11_27_217_event_profile_v1.json"
        )

    def test_nested_artifact_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            nested = Path(directory) / "provider" / "competition"
            nested.mkdir(parents=True)
            shutil.copy2(self.source, nested / self.source.name)
            profile = artifact_event_profile_resolver(directory)("statsbomb_open_data", 217, 11, 27)
            self.assertEqual(profile.team_id, 217)

    def test_root_level_artifact_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            shutil.copy2(self.source, Path(directory) / self.source.name)
            profile = artifact_event_profile_resolver(directory)("statsbomb_open_data", 217, 11, 27)
            self.assertEqual(profile.team_name, "Barcelona")

    def test_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            resolver = artifact_event_profile_resolver(directory)
            with self.assertRaisesRegex(KeyError, "Event profile not found"):
                resolver("statsbomb_open_data", 217, 11, 27)

    def test_duplicate_identity_is_rejected_as_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in (root / "a", root / "b"):
                folder.mkdir()
                shutil.copy2(self.source, folder / self.source.name)
            conflicting = json.loads((root / "b" / self.source.name).read_text(encoding="utf-8"))
            conflicting["team"]["team_name"] = "Conflicting Barcelona"
            (root / "b" / self.source.name).write_text(
                json.dumps(conflicting), encoding="utf-8",
            )
            resolver = artifact_event_profile_resolver(root)
            with self.assertRaisesRegex(ValueError, "Ambiguous event profile artifacts"):
                resolver("statsbomb_open_data", 217, 11, 27)

    def test_identical_duplicate_aliases_are_reconciled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in (root / "a", root / "b"):
                folder.mkdir()
                shutil.copy2(self.source, folder / self.source.name)
            profile = artifact_event_profile_resolver(root)("statsbomb_open_data", 217, 11, 27)
            self.assertEqual(profile.team_id, 217)

    def test_catalog_is_human_readable_deterministic_and_deduplicated(self):
        artifacts = Path(__file__).resolve().parents[1] / "artifacts"
        first = event_profile_artifact_catalog(artifacts)
        second = event_profile_artifact_catalog(artifacts)
        self.assertEqual(first, second)
        identities = [
            (item["provider"], str(item["team_id"]), str(item["competition_id"]), str(item["season_id"]))
            for item in first["profiles"]
        ]
        self.assertEqual(len(identities), len(set(identities)))
        barcelona = next(item for item in first["profiles"] if str(item["team_id"]) == "217")
        self.assertEqual(barcelona["team_name"], "Barcelona")
        self.assertTrue(barcelona["competition_name"])
        self.assertTrue(barcelona["season_name"])
        self.assertGreaterEqual(barcelona["analysed_match_count"], 20)


if __name__ == "__main__":
    unittest.main()
