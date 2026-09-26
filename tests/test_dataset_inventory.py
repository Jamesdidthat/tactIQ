import json
from pathlib import Path
import tempfile
import unittest

from src.analysis import build_dataset_inventory


def write_skillcorner_match(root: Path, match_id: int, tracking_period: int, phase_period: int) -> None:
    directory = root / str(match_id)
    directory.mkdir(parents=True)
    metadata = {
        "id": match_id,
        "competition_edition": {"competition": {"name": "Test League"}, "season": {"name": "2026"}},
        "home_team": {"id": 1, "name": "Home", "acronym": "H"},
        "away_team": {"id": 2, "name": "Away", "acronym": "A"},
        "home_team_side": ["left_to_right"],
        "players": [
            {"id": 10, "team_id": 1, "player_role": {"name": "Goalkeeper"}},
            {"id": 20, "team_id": 2, "player_role": {"name": "Goalkeeper"}},
        ],
    }
    (directory / f"{match_id}_match.json").write_text(json.dumps(metadata), encoding="utf-8")
    tracking = {"frame": 1, "period": tracking_period, "timestamp": "00:00:00.00", "player_data": [{"player_id": 10}], "ball_data": {"x": 0, "y": 0}}
    (directory / f"{match_id}_tracking_extrapolated.jsonl").write_text(json.dumps(tracking) + "\n", encoding="utf-8")
    (directory / f"{match_id}_phases_of_play.csv").write_text("match_id,period,frame_start,frame_end\n" + f"{match_id},{phase_period},1,2\n", encoding="utf-8")
    (directory / f"{match_id}_dynamic_events.csv").write_text("match_id,event_id\n", encoding="utf-8")


class DatasetInventoryTests(unittest.TestCase):
    def test_team_counts_capabilities_and_profile_preflight_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skillcorner = root / "skillcorner"
            skillcorner.mkdir()
            write_skillcorner_match(skillcorner, 1, 1, 1)
            write_skillcorner_match(skillcorner, 2, 1, 2)
            result = build_dataset_inventory(
                skillcorner_root=skillcorner, metrica_root=root / "missing"
            )
            home = result.teams.loc[result.teams.team_id.eq(1)].iloc[0]
            self.assertEqual(home.matches_available, 2)
            self.assertEqual(home.matches_canonical_adapter_ready, 2)
            self.assertEqual(home.matches_team_profile_ready, 1)
            self.assertTrue(home.has_continuous_tracking)
            self.assertTrue(home.has_events)
            invalid = result.match_teams.loc[result.match_teams.match_id.eq(2)]
            self.assertTrue(invalid.canonical_adapter_ready.all())
            self.assertFalse(invalid.team_profile_ready.any())
            self.assertTrue(invalid.exclusion_reason.str.contains("periods disagree").all())


if __name__ == "__main__":
    unittest.main()
