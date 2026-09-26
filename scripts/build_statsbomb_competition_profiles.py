"""Precompute compact event Team Profiles for every team in one competition-season."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import aggregate_event_team_match_metrics, calculate_event_team_match_metrics
from src.data import StatsBombOpenDataAdapter


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="external_data/statsbomb_open_data")
    parser.add_argument("--competition-id", type=int, required=True)
    parser.add_argument("--season-id", type=int, required=True)
    parser.add_argument("--output-dir", default="artifacts/event_profiles")
    parser.add_argument("--hydrate", action="store_true", help="Materialize this season's tracked event/lineup blobs in bounded Git batches.")
    options = parser.parse_args()

    adapter = StatsBombOpenDataAdapter(options.root)
    matches = adapter.matches()
    selected = matches.loc[
        matches.competition_id.eq(options.competition_id)
        & matches.season_id.eq(options.season_id)
    ].sort_values(["match_date", "match_id"], kind="stable")
    if selected.empty:
        raise ValueError("No matches found for the requested competition-season.")

    if options.hydrate:
        match_ids = [int(value) for value in selected.match_id]
        paths = [f"/data/{kind}/{match_id}.json" for kind in ("events", "lineups") for match_id in match_ids]
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={adapter.root.resolve().as_posix()}", "-C", str(adapter.root), "sparse-checkout", "add", "--stdin"],
            input="\n".join(paths) + "\n", capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"StatsBomb batch hydration failed: {completed.stderr.strip()}")
        print(f"hydrated {len(paths)} season assets through the existing sparse checkout", flush=True)

    team_rows: dict[int, list[dict]] = {}
    exclusions: list[dict] = []
    for number, match in enumerate(selected.itertuples(index=False), start=1):
        try:
            bundle = adapter.load_match(int(match.match_id))
            metrics = calculate_event_team_match_metrics(bundle)
            if len(metrics) != 2:
                raise ValueError("match did not produce exactly two team metric rows")
            for row in metrics.to_dict("records"):
                team_rows.setdefault(int(row["team_id"]), []).append(row)
            print(f"[{number}/{len(selected)}] processed {match.match_id}", flush=True)
        except Exception as error:
            exclusions.append({"match_id": int(match.match_id), "reason": str(error)})
            print(f"[{number}/{len(selected)}] skipped {match.match_id}: {error}", flush=True)

    identities: dict[int, str] = {}
    for row in selected.itertuples(index=False):
        identities[int(row.home_team_id)] = str(row.home_team_name)
        identities[int(row.away_team_id)] = str(row.away_team_name)
    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    metadata = selected.iloc[0]
    failed_ids = {row["match_id"] for row in exclusions}
    for team_id, team_name in sorted(identities.items(), key=lambda item: item[1]):
        expected = selected.loc[selected.home_team_id.eq(team_id) | selected.away_team_id.eq(team_id)]
        team_exclusions = [row for row in exclusions if row["match_id"] in set(expected.match_id)]
        profile = aggregate_event_team_match_metrics(
            pd.DataFrame(team_rows.get(team_id, [])), team_id=team_id, team_name=team_name,
            competition_id=options.competition_id, season_id=options.season_id,
            matches_excluded=pd.DataFrame(team_exclusions, columns=["match_id", "reason"]),
        )
        filename = f"statsbomb_{options.competition_id}_{options.season_id}_{team_id}_event_profile_v1.json"
        path = output_dir / filename
        payload = {
            "schema_version": "tactiq.event-team-profile.v1", "provider": "statsbomb_open_data",
            "team": {"team_id": team_id, "team_name": team_name},
            "competition": {"competition_id": options.competition_id, "competition_name": metadata.competition_name},
            "season": {"season_id": options.season_id, "season_name": metadata.season_name},
            "matches_discovered": int(len(expected)), "matches_included": int(len(profile.match_metrics)),
            "matches_excluded": _records(profile.matches_excluded), "coordinate_system": "statsbomb_120x80",
            "definitions": _records(profile.definitions), "match_metrics": _records(profile.match_metrics),
            "aggregate_metrics": _records(profile.aggregate_metrics),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        manifest.append({
            "team_id": team_id, "team_name": team_name, "artifact": str(path),
            "matches_discovered": int(len(expected)), "matches_included": int(len(profile.match_metrics)),
            "matches_excluded": len(team_exclusions),
        })
    manifest_path = output_dir / f"statsbomb_{options.competition_id}_{options.season_id}_manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "tactiq.competition-event-profiles.v1",
        "provider": "statsbomb_open_data", "competition_id": options.competition_id,
        "competition_name": metadata.competition_name, "season_id": options.season_id,
        "season_name": metadata.season_name, "source_matches": len(selected),
        "processed_matches": len(selected) - len(failed_ids), "excluded_matches": exclusions,
        "teams": manifest,
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"manifest={manifest_path} teams={len(manifest)} excluded_matches={len(exclusions)}", flush=True)


if __name__ == "__main__":
    main()
