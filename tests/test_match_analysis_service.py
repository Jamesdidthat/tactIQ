"""JSON-safe, cached, provider-neutral product service tests."""

import json
import unittest
from unittest.mock import patch

import pandas as pd

from src.api import MatchAnalysisService
from src.data import CanonicalMatchBundle, ProviderCapabilities, validate_canonical_bundle


def make_bundle(provider: str, match_id: str) -> CanonicalMatchBundle:
    teams = pd.DataFrame([
        {"match_id": match_id, "team_id": "h", "team_code": "H"},
        {"match_id": match_id, "team_id": "a", "team_code": "A"},
    ])
    roster = pd.DataFrame([
        {"match_id": match_id, "player_id": "h_gk", "team_id": "h", "position": "Goalkeeper", "position_group": "Other", "is_goalkeeper": True},
        {"match_id": match_id, "player_id": "h_d", "team_id": "h", "position": "Central Defender", "position_group": "Central Defender", "is_goalkeeper": False},
        {"match_id": match_id, "player_id": "h_a", "team_id": "h", "position": "Center Forward", "position_group": "Center Forward", "is_goalkeeper": False},
        {"match_id": match_id, "player_id": "a_gk", "team_id": "a", "position": "Goalkeeper", "position_group": "Other", "is_goalkeeper": True},
        {"match_id": match_id, "player_id": "a_d", "team_id": "a", "position": "Central Defender", "position_group": "Central Defender", "is_goalkeeper": False},
        {"match_id": match_id, "player_id": "a_a", "team_id": "a", "position": "Center Forward", "position_group": "Center Forward", "is_goalkeeper": False},
    ])
    rows, balls = [], []
    for frame in range(1, 31):
        common = {"match_id": match_id, "frame": frame, "period": 1, "elapsed_seconds": frame / 10, "timestamp": f"00:00:0{frame / 10:04.1f}"}
        home_attack_x = 40 if frame >= 28 else 25
        away_attack_x = -40 if frame >= 28 else -25
        for team, acronym, positions in (("h", "H", [("h_gk", "Goalkeeper", "Other", -50, 0), ("h_d", "Central Defender", "Central Defender", -15, -16), ("h_a", "Center Forward", "Center Forward", home_attack_x, 16)]), ("a", "A", [("a_gk", "Goalkeeper", "Other", 50, 0), ("a_d", "Central Defender", "Central Defender", 15, -16), ("a_a", "Center Forward", "Center Forward", away_attack_x, 16)])):
            for player_id, position, group, x, y in positions:
                rows.append({**common, "player_id": player_id, "team_id": team, "team_acronym": acronym, "position": position, "position_group": group, "x": x, "y": y, "is_detected": True})
        balls.append({**common, "ball_x": 0.0, "ball_y": 0.0})
    info = {"id": match_id, "pitch_length": 105.0, "pitch_width": 68.0, "home_team": {"id": "h", "acronym": "H"}, "away_team": {"id": "a", "acronym": "A"}, "home_team_side": ["left_to_right"]}
    bundle = CanonicalMatchBundle(
        provider=provider, match_info=info,
        matches=pd.DataFrame([{"match_id": match_id, "pitch_length_m": 105.0, "pitch_width_m": 68.0}]), teams=teams,
        roster=roster, player_positions=pd.DataFrame(rows), ball_positions=pd.DataFrame(balls),
        attacking_directions=pd.DataFrame([{"match_id": match_id, "period": 1, "team_id": "h", "attacking_x_sign": 1}, {"match_id": match_id, "period": 1, "team_id": "a", "attacking_x_sign": -1}]),
        capabilities=ProviderCapabilities(True, True, True, True, False, False),
    )
    validate_canonical_bundle(bundle)
    return bundle


class MatchAnalysisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.one = make_bundle("provider_one", "one")
        self.two = make_bundle("provider_two", "two")
        self.service = MatchAnalysisService({"one": self.one, "two": self.two})

    def test_responses_are_json_safe_and_deterministic(self) -> None:
        first = self.service.get_ranked_findings("one")
        second = self.service.get_ranked_findings("one")
        self.assertEqual(first, second)
        json.dumps(self.service.get_match_summary("one"))
        json.dumps(first)
        json.dumps(self.service.get_analysis_coverage("one"))
        self.assertTrue(all(item["selection_reason"] for item in first["ranked_findings"]))

    def test_detail_and_representative_frame_are_traceable(self) -> None:
        ranked = self.service.get_ranked_findings("one")["ranked_findings"]
        self.assertTrue(ranked)
        detail = self.service.get_finding_detail("one", ranked[0]["finding_id"])
        frame = self.service.get_representative_pitch_frame("one", ranked[0]["finding_id"])
        json.dumps(detail)
        json.dumps(frame)
        self.assertEqual(frame["schema_version"], "v1")
        self.assertTrue(frame["players"])
        self.assertIn("timestamp", detail["evidence"]["representative_moments"][0])
        self.assertEqual(detail["finding"]["selection_reason"], ranked[0]["selection_reason"])

    def test_explanation_response_is_cached_json_safe_and_evidence_bounded(self) -> None:
        finding_id = self.service.get_ranked_findings("one")["ranked_findings"][0]["finding_id"]
        first = self.service.get_finding_explanation("one", finding_id)
        second = self.service.get_finding_explanation("one", finding_id)
        self.assertEqual(first["schema_version"], "v1")
        self.assertEqual(first["metadata"]["prompt_version"], "tactiq-finding-explanation-v1")
        self.assertEqual(first["metadata"]["source"], "deterministic_fallback")
        self.assertFalse(first["metadata"]["cache_hit"])
        self.assertTrue(second["metadata"]["cache_hit"])
        self.assertEqual(first["explanation"], second["explanation"])
        json.dumps(second, allow_nan=False)

    def test_cached_detail_does_not_rerun_analysis(self) -> None:
        with patch("src.api.match_analysis_service.run_match_analysis", wraps=__import__("src.api.match_analysis_service", fromlist=["run_match_analysis"]).run_match_analysis) as runner:
            service = MatchAnalysisService({"one": self.one})
            finding_id = service.get_ranked_findings("one")["ranked_findings"][0]["finding_id"]
            service.get_finding_detail("one", finding_id)
            self.assertEqual(runner.call_count, 1)

    def test_identifier_requests_reuse_the_resolved_bundle(self) -> None:
        resolver_calls = []

        def resolver(match_id: str):
            resolver_calls.append(match_id)
            return self.one

        service = MatchAnalysisService(resolver)
        finding_id = service.get_ranked_findings("one")["ranked_findings"][0]["finding_id"]
        service.get_finding_detail("one", finding_id)
        service.get_representative_pitch_frame("one", finding_id)
        self.assertEqual(resolver_calls, ["one"])

    def test_same_contract_is_provider_independent(self) -> None:
        one = self.service.get_match_summary("one")
        two = self.service.get_match_summary("two")
        self.assertEqual(set(one), set(two))
        self.assertEqual(one["schema_version"], two["schema_version"])
        self.assertNotEqual(one["match"]["provider"], two["match"]["provider"])

    def test_pitch_frame_uses_roster_number_without_changing_positions(self) -> None:
        from src.api.schemas import serialize_pitch_frame
        self.one.roster['player_number'] = [1, 4, 9, 1, 5, pd.NA]
        before = self.one.player_positions.copy(deep=True)
        payload = serialize_pitch_frame(self.one, frame=1, period=1)
        numbers = {p['player_id']: p.get('player_number') for p in payload['players']}
        self.assertEqual(numbers['h_d'], 4)
        self.assertIsNone(numbers['a_a'])
        pd.testing.assert_frame_equal(before, self.one.player_positions)
        json.dumps(payload, allow_nan=False)

    def test_observed_frame_can_be_requested_without_a_finding(self) -> None:
        with patch("src.api.match_analysis_service.run_match_analysis") as runner:
            frame = self.service.get_pitch_frame("one", frame=7, period=1)
            runner.assert_not_called()
        self.assertEqual(frame["frame"], 7)
        self.assertEqual(frame["period"], 1)
        self.assertTrue(frame["players"])
        json.dumps(frame, allow_nan=False)

    def test_observed_clip_is_bounded_same_period_and_json_safe(self) -> None:
        with patch("src.api.match_analysis_service.run_match_analysis") as runner:
            clip = self.service.get_pitch_clip(
                "one", centre_frame=15, period=1, before_frames=5, after_frames=5, step=2
            )
            runner.assert_not_called()
        self.assertEqual([item["frame"] for item in clip["frames"]], [11, 13, 15, 17, 19])
        self.assertEqual(clip["frames"][clip["focus_index"]]["frame"], 15)
        self.assertAlmostEqual(clip["source_frame_rate_hz"], 10.0)
        self.assertAlmostEqual(clip["playback_frame_rate_hz"], 5.0)
        self.assertTrue(all(item["period"] == 1 for item in clip["frames"]))
        json.dumps(clip, allow_nan=False)

    def test_observed_clip_rejects_unbounded_or_missing_requests(self) -> None:
        with self.assertRaises(ValueError):
            self.service.get_pitch_clip("one", centre_frame=15, period=1, before_frames=101, after_frames=100)
        with self.assertRaises(KeyError):
            self.service.get_pitch_clip("one", centre_frame=999, period=1)

    def test_observed_clip_accepts_provider_independent_time_bounds(self) -> None:
        clip = self.service.get_pitch_clip(
            "one", centre_frame=15, period=1, before_seconds=.4, after_seconds=.6
        )
        self.assertEqual([item["frame"] for item in clip["frames"]], list(range(11, 22)))
        self.assertAlmostEqual(clip["actual_duration_seconds"], 1.0)
        self.assertEqual(clip["requested"]["before_seconds"], .4)

    def test_tracking_match_tactical_profile_is_json_safe(self) -> None:
        payload = self.service.get_tactical_analysis("one")
        self.assertEqual(payload["schema_version"], "tactiq.match-tactical-profile.v1")
        self.assertEqual(len(payload["team_profiles"]), 2)
        self.assertTrue(all(item["tracking_shape"] for item in payload["team_profiles"]))
        self.assertTrue(all(item["evidence"].get("representative_frame") for item in payload["team_profiles"][0]["segments"]))
        self.assertEqual(payload["goals"], [])
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
