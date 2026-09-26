import json
import unittest

from src.analysis import TeamProfileIdentity
from src.api import TeamProfileService
from tests.test_finding_prioritization import make_result
from tests.test_match_analysis_service import make_bundle


class TeamProfileServiceTests(unittest.TestCase):
    def setUp(self):
        self.bundles = [make_bundle("provider_one", "one"), make_bundle("provider_one", "two")]
        self.calls = 0
        def resolver(team_id):
            self.calls += 1
            return TeamProfileIdentity("club", "Test Club", {"provider_one": "h"}), self.bundles
        self.service = TeamProfileService(resolver)

    def test_all_product_views_are_json_safe_and_cached(self):
        outputs = [self.service.summary("club"), self.service.metrics("club"), self.service.finding_families("club"), self.service.matches("club"), self.service.deviations("club")]
        for output in outputs:
            self.assertEqual(output["schema_version"], "v1")
            json.dumps(output, allow_nan=False)
        shape = self.service.shape_style("club")
        self.assertEqual(shape["schema_version"], "tactiq.football-shape-profile.v1")
        self.assertTrue(shape["available"])
        json.dumps(shape, allow_nan=False)
        self.assertEqual(self.calls, 1)
        self.assertEqual(outputs[0]["analysed_match_count"], 2)
        self.assertEqual(outputs[0]["profile_evidence_band"], "insufficient")
        self.assertEqual(outputs[0]["profile_baseline_label"], "two-match provisional baseline")
        metric_rows = outputs[1]["metric_baselines"]
        self.assertTrue(all(row["contributing_matches"] == 2 for row in metric_rows))
        self.assertEqual({row["unit"] for row in metric_rows if row["metric_family"] == "shot_counts"}, set())

    def test_deviations_are_ranked_and_link_to_match_analysis(self):
        rows = self.service.deviations("club")["match_deviations"]
        magnitudes = [row["absolute_deviation"] for row in rows]
        self.assertEqual(magnitudes, sorted(magnitudes, reverse=True))
        self.assertTrue(all(row["match_analysis_path"].startswith("/?match=") for row in rows))
        self.assertTrue(all("finding=nan" not in row["match_analysis_path"] for row in rows))
        self.assertTrue(all(row["link_label"] in {"View match", "View evidence"} for row in rows))


if __name__ == "__main__":
    unittest.main()
