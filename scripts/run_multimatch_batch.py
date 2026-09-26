"""Run the compact SkillCorner multi-match pipeline and print batch totals."""

import sys
from pathlib import Path


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.analysis import (
    compare_defensive_shape_by_shot_outcome,
    compare_phase_relative_defensive_shape_by_shot_outcome,
    compare_low_block_line_structure_by_shot_outcome,
    compare_low_block_ball_relative_by_shot_outcome,
    process_skillcorner_matches,
)

result = process_skillcorner_matches(project_root / "opendata" / "data" / "matches")
intervals = result.intervals
processed = result.processing_log["status"].eq("processed").sum()
skipped = result.processing_log["status"].eq("skipped").sum()

print(f"matches_discovered={len(result.processing_log)}")
print(f"matches_processed={processed}")
print(f"matches_skipped={skipped}")
print(f"compact_intervals={len(intervals)}")
print(f"shot_leading_intervals={int(intervals['team_possession_lead_to_shot'].sum())}")
print(f"goal_leading_intervals={int(intervals['team_possession_lead_to_goal'].sum())}")
print(f"unique_teams={intervals['defending_team_id'].nunique()}")

analysis = compare_defensive_shape_by_shot_outcome(intervals, result.processing_log)
for name in (
    "pooled",
    "pooled_median_differences",
    "team_relative",
    "team_relative_median_differences",
    "by_team",
    "by_team_median_differences",
    "skipped_matches",
):
    print(f"\n[{name}]")
    print(analysis[name].to_csv(index=False))

phase_relative_analysis = compare_phase_relative_defensive_shape_by_shot_outcome(intervals)
for name in (
    "pooled_by_phase",
    "pooled_phase_median_differences",
    "per_team_phase",
    "per_team_phase_median_differences",
):
    print(f"\n[phase_relative_{name}]")
    print(phase_relative_analysis[name].to_csv(index=False))

low_block_line_analysis = compare_low_block_line_structure_by_shot_outcome(intervals)
for name in (
    "quality",
    "pooled",
    "pooled_median_differences",
    "per_team",
    "per_team_median_differences",
):
    print(f"\n[low_block_line_{name}]")
    print(low_block_line_analysis[name].to_csv(index=False))

ball_relative_analysis = compare_low_block_ball_relative_by_shot_outcome(intervals)
for name in (
    "quality",
    "pooled",
    "pooled_median_differences",
    "pooled_by_ball_depth_zone",
    "pooled_zone_median_differences",
    "per_team",
    "per_team_median_differences",
):
    print(f"\n[low_block_ball_{name}]")
    print(ball_relative_analysis[name].to_csv(index=False))
