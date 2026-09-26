"""Fetch a local TactIQ v1 endpoint without terminating a long first analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("output")
options = parser.parse_args()
with urlopen(options.url, timeout=600) as response:
    payload = json.load(response)
Path(options.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"{response.status} {options.output}")
