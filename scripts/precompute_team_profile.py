"""Precompute compact provider/team profile artifacts from local match data."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analysis import TeamProfileArtifactStore, precompute_team_profile
from src.api.http_server import skillcorner_team_resolver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="skillcorner_open_data", choices=["skillcorner_open_data"])
    parser.add_argument("--team-id", action="append", required=True, help="Provider team ID; repeat for multiple teams")
    parser.add_argument("--matches-root", default="opendata/data/matches")
    parser.add_argument("--cache-root", default="artifacts/team_profiles")
    options = parser.parse_args()

    store = TeamProfileArtifactStore(options.cache_root)
    resolver = skillcorner_team_resolver(Path(options.matches_root))
    for team_id in options.team_id:
        requested = int(team_id) if team_id.isdigit() else team_id
        result, path = precompute_team_profile(options.provider, requested, resolver, store)
        print(
            f"team_id={team_id} valid_matches={len(result.matches_included)} "
            f"excluded_matches={len(result.matches_excluded)} artifact={path}"
        )
        for row in result.matches_excluded.itertuples(index=False):
            print(f"  excluded match_id={row.match_id}: {row.reason}")


if __name__ == "__main__":
    main()
