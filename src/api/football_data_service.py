"""Product service for current-season football-data.org fixtures and form."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

from src.data.football_data_live import FootballDataClient, serialize_fixture, serialize_team


POPULAR_COMPETITION_ORDER = ("PL", "CL", "PD", "BL1", "SA", "FL1", "ELC", "DED", "PPL")


class FootballDataService:
    def __init__(self, client: FootballDataClient | None = None) -> None:
        self.client = client or FootballDataClient()

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "v1",
            "provider": "football_data_org",
            "configured": self.client.configured,
            "mode": "current_fixtures_teams_and_results",
            "capability_note": (
                "Provides current competition schedules, results, team identity and recent scorelines. "
                "The free feed does not provide continuous tracking or detailed tactical match statistics."
            ),
        }

    def competitions(self) -> dict[str, Any]:
        order = {code: index for index, code in enumerate(POPULAR_COMPETITION_ORDER)}
        rows = sorted(
            self.client.competitions(),
            key=lambda row: (order.get(str(row.get("code")), 999), str(row.get("country") or ""), str(row.get("name") or "")),
        )
        return {
            "schema_version": "v1",
            "provider": "football_data_org",
            "competition_count": len(rows),
            "competitions": rows,
            "popular_competition_codes": list(POPULAR_COMPETITION_ORDER),
            "cache_note": "Competition reference data is cached on the TactIQ backend.",
        }

    def fixtures(
        self,
        code: str,
        *,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        fixtures = self.client.competition_matches(
            code.upper(), status=status, date_from=date_from, date_to=date_to,
        )
        fixtures.sort(key=lambda row: str(row.get("kickoff") or ""))
        return {
            "schema_version": "v1",
            "provider": "football_data_org",
            "competition_code": code.upper(),
            "query": {"status": status, "date_from": date_from, "date_to": date_to},
            "fixture_count": len(fixtures),
            "fixtures": fixtures,
            "cache_note": "Current-season schedules and results are cached on the TactIQ backend.",
        }

    def teams(self, code: str) -> dict[str, Any]:
        teams = sorted(self.client.competition_teams(code.upper()), key=lambda row: str(row.get("name") or ""))
        return {
            "schema_version": "v1",
            "provider": "football_data_org",
            "competition_code": code.upper(),
            "team_count": len(teams),
            "teams": teams,
        }

    def matchup_preview(self, match_id: int, *, recent_match_count: int = 5) -> dict[str, Any]:
        raw_match = self.client.match_data(match_id)
        fixture = serialize_fixture(raw_match)
        competition_code = str((raw_match.get("competition") or {}).get("code") or "")
        kickoff = str(raw_match.get("utcDate") or "")
        team_rows = [raw_match.get("homeTeam") or {}, raw_match.get("awayTeam") or {}]
        profiles = []
        for raw_team in team_rows:
            team_id = int(raw_team["id"])
            team_data = self.client.team_data(team_id)
            manager = self._manager(team_data)
            rows = self.client.team_matches(
                team_id, competitions=competition_code or None, status="FINISHED", limit=30,
            )
            rows = [row for row in rows if int(row.get("id") or -1) != match_id and str(row.get("utcDate") or "") < kickoff]
            manager_start = manager.get("start_date")
            if manager_start:
                rows = [row for row in rows if str(row.get("utcDate") or "")[:10] >= str(manager_start)]
            rows = sorted(rows, key=lambda row: str(row.get("utcDate") or ""), reverse=True)[:recent_match_count]
            profiles.append(self._team_profile(raw_team, manager, rows))

        return {
            "schema_version": "tactiq.current-matchup-preview.v1",
            "provider": "football_data_org",
            "fixture": fixture,
            "sample_definition": {
                "requested_recent_matches": recent_match_count,
                "competition_only": True,
                "current_manager_tenure_only": all(profile["manager"]["verified"] for profile in profiles),
                "unit_of_evidence": "completed_match",
            },
            "teams": profiles,
            "matchup_read": self._matchup_read(profiles),
            "basic_stats_note": (
                "This free-data preview uses results and goals from the listed matches. "
                "Possession, shots, passing and tracking-derived shape are unavailable from this source."
            ),
            "limitations": [
                "Five recent matches are a form snapshot, not a stable tactical identity.",
                "Scorelines alone cannot establish how possession, pressing, chance creation or team shape worked.",
                "The preview is descriptive and does not predict the result or prescribe a tactical plan.",
                "Manager-tenure filtering is used only when football-data.org supplies a current contract start date.",
            ],
            "request_efficiency": "Team, fixture and recent-result responses are cached to respect the free provider quota.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _manager(team_data: Mapping[str, Any]) -> dict[str, Any]:
        coach = team_data.get("coach") or {}
        contract = coach.get("contract") or {}
        name = coach.get("name") or "Manager unavailable"
        return {
            "manager_id": coach.get("id"),
            "name": name,
            "photo_url": None,
            "start_date": contract.get("start"),
            "verified": bool(coach.get("id") or (name and name != "Manager unavailable")),
        }

    @staticmethod
    def _team_profile(team_raw: Mapping[str, Any], manager: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        team_id = int(team_raw["id"])
        matches: list[dict[str, Any]] = []
        goals_for: list[int] = []
        goals_against: list[int] = []
        results = Counter()
        clean_sheets = 0
        scoring_matches = 0
        for row in rows:
            home = row.get("homeTeam") or {}
            away = row.get("awayTeam") or {}
            full_time = ((row.get("score") or {}).get("fullTime") or {})
            is_home = int(home.get("id") or -1) == team_id
            opponent_raw = away if is_home else home
            scored = int((full_time.get("home") if is_home else full_time.get("away")) or 0)
            conceded = int((full_time.get("away") if is_home else full_time.get("home")) or 0)
            result = "D" if scored == conceded else ("W" if scored > conceded else "L")
            results[result] += 1
            goals_for.append(scored)
            goals_against.append(conceded)
            clean_sheets += int(conceded == 0)
            scoring_matches += int(scored > 0)
            matches.append({
                "fixture_id": row.get("id"),
                "date": str(row.get("utcDate") or "")[:10],
                "opponent": serialize_team(opponent_raw),
                "venue": "Home" if is_home else "Away",
                "result": result,
                "goals_for": scored,
                "goals_against": conceded,
                "formation": None,
                "statistics_available": False,
            })
        count = len(matches)
        average = lambda values: round(sum(values) / len(values), 1) if values else None
        averages = {
            "possession": None,
            "goals_for": average(goals_for),
            "goals_against": average(goals_against),
            "shots": None,
            "shots_on_target": None,
            "shots_faced": None,
            "shots_inside_box": None,
            "pass_accuracy": None,
            "corners": None,
            "clean_sheet_rate": round(clean_sheets / count * 100, 1) if count else None,
            "scoring_match_rate": round(scoring_matches / count * 100, 1) if count else None,
        }
        name = team_raw.get("name") or team_raw.get("shortName") or "The team"
        control_text = "The result feed does not show who controlled the ball or how either side built attacks."
        attack_text = "There are not enough completed matches before this fixture to describe recent scoring output."
        defence_text = "There are not enough completed matches before this fixture to describe recent defensive results."
        if count:
            attack_text = (
                f"{name} scored {sum(goals_for)} goals across these {count} matches "
                f"and found the net in {scoring_matches} of them."
            )
            defence_text = (
                f"They conceded {sum(goals_against)} goals across the sample and kept "
                f"{clean_sheets} clean sheet{'s' if clean_sheets != 1 else ''}."
            )
        return {
            "team": serialize_team(team_raw),
            "manager": dict(manager),
            "matches_in_sample": count,
            "form": "".join(match["result"] for match in matches),
            "record": {"wins": results["W"], "draws": results["D"], "losses": results["L"]},
            "most_common_formation": None,
            "averages": averages,
            "recent_matches": matches,
            "football_read": {
                "control": control_text,
                "attacking_output": attack_text,
                "defensive_exposure": defence_text,
            },
        }

    @staticmethod
    def _matchup_read(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(profiles) != 2 or any(profile["matches_in_sample"] == 0 for profile in profiles):
            return []
        home, away = profiles
        observations: list[dict[str, Any]] = []
        for attack, defence in ((home, away), (away, home)):
            scored = attack["averages"].get("goals_for")
            conceded = defence["averages"].get("goals_against")
            if scored is None or conceded is None:
                continue
            observations.append({
                "title": f"Review {attack['team']['name']}'s recent scoring against {defence['team']['name']}'s recent results",
                "explanation": (
                    f"{attack['team']['name']} have scored {scored:.1f} goals per match in this sample, while "
                    f"{defence['team']['name']} have conceded {conceded:.1f}. This frames what to inspect in the "
                    "listed matches; scorelines alone do not reveal the tactical mechanism."
                ),
                "evidence": {"recent_goals_per_match": scored, "opponent_recent_goals_conceded_per_match": conceded},
            })
        return observations


__all__ = ["FootballDataService", "POPULAR_COMPETITION_ORDER"]
