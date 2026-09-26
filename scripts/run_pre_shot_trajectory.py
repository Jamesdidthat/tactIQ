import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
from src.analysis import build_pre_shot_trajectory_analysis
r=build_pre_shot_trajectory_analysis(root/"opendata"/"data"/"matches")
for name,table in r.items(): print(f"\n[{name}]\n{table.to_csv(index=False)}")
