"""Print temporal coverage facts for dynamic-event shot sequences."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.analysis import audit_shot_sequence_timing


result = audit_shot_sequence_timing(project_root / "opendata" / "data" / "matches")
for name, table in result.items():
    print(f"\n[{name}]")
    print(table.to_csv(index=False))
