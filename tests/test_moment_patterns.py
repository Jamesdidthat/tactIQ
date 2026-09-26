"""Boundary, provenance, and multi-label tests for event-only moment patterns."""

import unittest
from types import SimpleNamespace

from src.analysis import RepresentativeMoment, build_moment_patterns, classify_moment_patterns


def moment(
    event_id: str,
    event_type: str,
    family: str,
    *,
    start=(90.0, 40.0),
    end=(105.0, 40.0),
    play_pattern="Regular Play",
    shot_type="Open Play",
    xg=None,
    median_xg=None,
    match_id=10,
) -> RepresentativeMoment:
    values = {
        "xg": xg, "start_coordinates": start, "end_coordinates": end,
        "play_pattern": play_pattern, "shot_type": shot_type, "shot_outcome": None,
    }
    if median_xg is not None:
        values["team_season_shot_xg_distribution"] = {
            "q25": median_xg / 2, "median": median_xg, "q75": median_xg * 1.5, "shot_count": 50,
        }
    return RepresentativeMoment(
        match_id=match_id, team_id=1, team_name="A", opponent_id=2, opponent_name="B",
        match_date="2016-01-01", minute=10, second=0, period=1, event_id=event_id,
        event_type=event_type, metric=f"{family}_per90", family=family,
        description="Example.", relevant_values=values, score_state="drawing",
        score_state_verified=True, score_state_team_id=1, score_state_team_name="A",
        source_provenance={"provider": "statsbomb_open_data"},
        video_availability_status="unavailable_in_statsbomb_open_data",
        reason_selected="typical_match_example", evidence_side="attacking_production",
    )


def defensive_detail(*, same_possession=True, progressive=True):
    focal = SimpleNamespace(possession_id=7, team_id=1, relation_to_focal="focal")
    end = (80.0, 40.0) if progressive else (65.0, 40.0)
    following = SimpleNamespace(
        relation_to_focal="next", possession_id=7 if same_possession else 8,
        team_id=1, event_type="Pass", start_coordinates=(60.0, 40.0), end_coordinates=end,
    )
    return SimpleNamespace(focal_event=focal, sequence_events=(focal, following))


class MomentPatternTests(unittest.TestCase):
    def test_entry_boundaries_are_deterministic(self):
        at_lower = moment("lower", "Pass", "penalty_area_entries", end=(105.0, 18.0))
        at_upper = moment("upper", "Pass", "penalty_area_entries", end=(105.0, 62.0))
        outside = moment("wide", "Pass", "penalty_area_entries", end=(105.0, 17.999))
        self.assertIn("central_pass_entry", classify_moment_patterns(at_lower))
        self.assertIn("central_pass_entry", classify_moment_patterns(at_upper))
        self.assertIn("wide_pass_entry", classify_moment_patterns(outside))

    def test_action_is_exclusive_but_explicit_origin_is_multi_label(self):
        entry = moment(
            "set-wide", "Pass", "final_third_entries", end=(82.0, 70.0),
            play_pattern="From Corner",
        )
        keys = classify_moment_patterns(entry)
        self.assertEqual(set(keys), {"wide_pass_entry", "set_play_origin_entry"})
        self.assertNotIn("central_pass_entry", keys)
        self.assertNotIn("carry_entry", keys)

    def test_missing_entry_coordinates_are_not_inferred(self):
        entry = moment("missing", "Pass", "penalty_area_entries", end=None)
        result = build_moment_patterns("p1", [entry])
        self.assertEqual(result.assignments[0].pattern_keys, ())
        self.assertTrue(any("unclassified" in item for item in result.limitations))

    def test_shot_origin_location_and_relative_xg_groups(self):
        counter = moment(
            "counter", "Shot", "shots", start=(108.0, 24.0),
            play_pattern="From Counter", xg=.20, median_xg=.20,
        )
        keys = classify_moment_patterns(counter)
        self.assertIn("explicit_counter_attack_shot", keys)
        self.assertNotIn("open_play_shot", keys)
        self.assertNotIn("set_play_shot", keys)
        self.assertIn("central_shot_location", keys)
        self.assertIn("higher_xg_shot", keys)

        set_play = moment("set", "Shot", "shots", play_pattern="From Corner", xg=.05, median_xg=.10)
        set_keys = classify_moment_patterns(set_play)
        self.assertIn("set_play_shot", set_keys)
        self.assertIn("lower_xg_shot", set_keys)

    def test_counter_requires_exact_provider_provenance(self):
        generic = moment("regular", "Shot", "counter_attacks", play_pattern="Regular Play")
        keys = classify_moment_patterns(generic)
        self.assertNotIn("explicit_counter_attack_shot", keys)
        self.assertIn("open_play_shot", keys)
        entry = moment("counter-entry", "Carry", "final_third_entries", play_pattern="From Counter")
        self.assertEqual(
            set(classify_moment_patterns(entry)),
            {"carry_entry", "explicit_counter_entry"},
        )

    def test_shot_location_boundary_is_inclusive_and_not_a_true_angle_claim(self):
        central = moment("central", "Shot", "shots", start=(108.0, 56.0))
        wide = moment("wide-shot", "Shot", "shots", start=(108.0, 56.001))
        self.assertIn("central_shot_location", classify_moment_patterns(central))
        self.assertIn("wide_angle_shot_location", classify_moment_patterns(wide))

    def test_defensive_high_zone_boundary_and_same_possession_progression(self):
        regain = moment("regain", "Ball Recovery", "high_regains", start=(80.0, 40.0))
        keys = classify_moment_patterns(regain, defensive_detail())
        self.assertEqual(set(keys), {"recovery", "high_zone_regain", "immediate_same_possession_progression"})
        crossed = classify_moment_patterns(regain, defensive_detail(same_possession=False))
        self.assertNotIn("immediate_same_possession_progression", crossed)

    def test_summary_is_stable_and_preserves_overlapping_share_denominator(self):
        moments = [
            moment("a", "Pass", "penalty_area_entries", end=(105.0, 10.0), play_pattern="From Corner", match_id=10),
            moment("b", "Carry", "penalty_area_entries", end=(105.0, 40.0), match_id=11),
        ]
        first = build_moment_patterns("priority", moments)
        second = build_moment_patterns("priority", moments)
        self.assertEqual(first, second)
        wide = next(item for item in first.patterns if item.pattern_key == "wide_pass_entry")
        self.assertEqual(wide.moment_count, 1)
        self.assertEqual(wide.eligible_moment_count, 2)
        self.assertEqual(wide.share_of_eligible_moments, .5)
        self.assertEqual(wide.representative_moment_ids, ("a",))


if __name__ == "__main__":
    unittest.main()
