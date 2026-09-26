"""Create a concise provider-independent Metrica geometry readiness output."""

from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from src.analysis.metrica_geometry_demo import run_metrica_geometry_demo


result = run_metrica_geometry_demo(
    "external_data/metrica/Sample_Game_1",
    figure_path="artifacts/metrica_sample_game_1_frame_1001.png",
)
print("[invariants]")
for name, value in result["invariants"].items():
    print(f"{name}={value}")
print("\n[team_shape_sample]")
print(result["team_shape"].reset_index().head(4).to_csv(index=False))
print("[line_structure_sample]")
print(result["line_structure"].reset_index().head(4).to_csv(index=False))
print("[local_context_sample]")
print(result["local_context"].head(4).to_csv(index=False))
print("[ball_goal_geometry_sample]")
print(result["ball_goal_geometry"].head(4).to_csv(index=False))
