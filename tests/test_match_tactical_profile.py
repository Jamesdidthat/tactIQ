"""Deterministic match-versus-normal and goal-investigation tests."""

from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.analysis import aggregate_event_team_match_metrics, build_event_team_season_profile, build_match_tactical_profile
from src.analysis.event_team_profile import calculate_event_team_match_metrics
from src.api import EventProfileService
from src.data import StatsBombOpenDataAdapter
from tests.test_match_analysis_service import make_bundle
from tests.test_statsbomb_adapter import write_fixture


class MatchTacticalProfileTests(unittest.TestCase):
    def test_event_match_profiles_both_teams_and_every_goal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            result = build_match_tactical_profile(bundle)
        self.assertEqual(result.schema_version, "tactiq.match-tactical-profile.v1")
        self.assertEqual(len(result.team_profiles), 2)
        self.assertTrue(all(item.segments for item in result.team_profiles))
        self.assertEqual(len(result.goals), 1)
        goal = result.goals[0]
        self.assertEqual(goal.scoring_team_name, "Alpha")
        self.assertEqual(goal.conceding_team_name, "Beta")
        self.assertEqual(goal.passes, 1)
        self.assertEqual(goal.shot_xg, .25)
        self.assertTrue(goal.preceding_actions)
        self.assertFalse(any(item.category == "individual_defensive_error" for item in goal.contributors))
        self.assertIsNone(goal.tracking_context)

    def test_low_probability_finish_is_a_proxy_not_proof_of_brilliance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            bundle.events.loc[bundle.events.event_id.eq("event-2"), "shot_xg"] = .04
            result = build_match_tactical_profile(bundle)
        goal = result.goals[0]
        contributor = next(item for item in goal.contributors if item.category == "exceptional_individual_execution")
        self.assertIn("low-probability", contributor.observation)
        self.assertIn("does not prove", contributor.scope)
        self.assertTrue(any("not proof of brilliance" in item for item in goal.limitations))

    def test_tracking_match_uses_shape_but_does_not_invent_goals(self) -> None:
        result = build_match_tactical_profile(make_bundle("tracking_provider", "one"))
        self.assertEqual(len(result.team_profiles), 2)
        self.assertTrue(all(item.tracking_shape is not None for item in result.team_profiles))
        self.assertTrue(all(item.tracking_shape["sampling_method"] == "one observed tracking frame per elapsed second" for item in result.team_profiles))
        self.assertFalse(result.goals)
        self.assertIn("no supported goal events", result.analysis_coverage["goal_analysis"])

    def test_explicit_own_goal_is_included_without_blame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            own = bundle.events.iloc[1].copy()
            own.update({"event_id": "own-1", "event_index": 3, "elapsed_seconds": 3.0, "minute": 0, "second": 3, "team_id": 20, "event_type": "Own Goal Against", "is_shot": False, "shot_outcome": None, "shot_xg": None})
            beneficiary = own.copy()
            beneficiary.update({"event_id": "own-2", "event_index": 4, "team_id": 10, "event_type": "Own Goal For"})
            bundle.events = pd.concat([bundle.events, own.to_frame().T, beneficiary.to_frame().T], ignore_index=True)
            result = build_match_tactical_profile(bundle)
        self.assertEqual(len(result.goals), 2)
        analysed = result.goals[1]
        self.assertEqual(analysed.scoring_team_name, "Alpha")
        unusual = next(item for item in analysed.contributors if item.category == "unusual_event")
        self.assertIn("no blame", unusual.scope)
        self.assertEqual(analysed.event_id, "own-2")

    def test_broad_season_mechanism_is_context_not_a_recurring_goal_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            bundle.events.loc[bundle.events.event_id.eq("event-2"), "play_pattern"] = "From Counter"
            current = calculate_event_team_match_metrics(bundle).loc[lambda frame: frame.team_id.eq(10)].copy()
            rows = []
            for index in range(6):
                row = current.copy(); row["match_id"] = 100 + index; rows.append(row)
            season = aggregate_event_team_match_metrics(
                pd.concat(rows, ignore_index=True), team_id=10, team_name="Alpha",
                competition_id=1, season_id=1,
            )
            result = build_match_tactical_profile(bundle, event_team_profiles={10: season})
        goal = result.goals[0]
        self.assertTrue(any(item.category == "historical_mechanism_context" for item in goal.contributors))
        self.assertFalse(any(item.category in {"recurring_structural_pattern", "opponent_recurring_attacking_strength"} for item in goal.contributors))
        self.assertIn("does not establish", next(item.observation for item in goal.contributors if item.category == "historical_mechanism_context"))

    def test_short_windows_and_provider_scope_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least five"):
            build_match_tactical_profile(make_bundle("tracking_provider", "one"), window_minutes=4)

    def test_event_profile_service_returns_cached_json_safe_tactical_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            profiles = {
                "10": build_event_team_season_profile([bundle], team_id=10, competition_id=1, season_id=1),
                "20": build_event_team_season_profile([bundle], team_id=20, competition_id=1, season_id=1),
            }
            loads = []
            service = EventProfileService(
                lambda provider, team, competition, season: profiles[str(team)],
                event_bundle_resolver=lambda provider, match: loads.append(match) or bundle,
            )
            first = service.match_tactical_analysis("statsbomb_open_data", 10, 1, 1, 100)
            second = service.match_tactical_analysis("statsbomb_open_data", 10, 1, 1, 100)
        self.assertEqual(first, second)
        self.assertEqual(loads, [100])
        self.assertEqual(len(first["team_profiles"]), 2)
        self.assertEqual(len(first["goals"]), 1)

    def test_match_is_compared_with_adequately_covered_season_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_fixture(root)
            bundle = StatsBombOpenDataAdapter(root).load_match(100)
            current = calculate_event_team_match_metrics(bundle).loc[lambda frame: frame.team_id.eq(10)].copy()
            rows = []
            for index, xg in enumerate([current.xg_per90.iloc[0], 90, 100, 110, 120, 130]):
                row = current.copy(); row["match_id"] = 100 + index; row["xg_per90"] = xg; rows.append(row)
            season = aggregate_event_team_match_metrics(pd.concat(rows, ignore_index=True), team_id=10, team_name="Alpha", competition_id=1, season_id=1)
            result = build_match_tactical_profile(bundle, event_team_profiles={10: season})
        alpha = next(item for item in result.team_profiles if item.team_id == 10)
        self.assertTrue(any(item.metric == "xg_per90" for item in alpha.style_deviations))
        xg = next(item for item in alpha.style_deviations if item.metric == "xg_per90")
        self.assertEqual(xg.contributing_matches, 5)


if __name__ == "__main__":
    unittest.main()
