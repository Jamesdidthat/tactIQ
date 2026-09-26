"""Product-facing live football service backed by API-Football."""

from __future__ import annotations

from datetime import date
from collections import Counter
from typing import Any, Mapping

from src.data.api_football_live import ApiFootballClient, serialize_live_fixture


class LiveFootballService:
    def __init__(self, client: ApiFootballClient | None = None) -> None:
        self.client = client or ApiFootballClient()

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "v1",
            "provider": "api_football",
            "configured": self.client.configured,
            "mode": "live_scores_and_statistics",
            "capability_note": (
                "Provides fixtures, score state, incidents, lineups and match statistics where competition coverage allows. "
                "It does not provide continuous tracking."
            ),
        }

    def fixtures(
        self,
        *,
        live: str | None = None,
        fixture_date: str | None = None,
        league: int | None = None,
        season: int | None = None,
        next_count: int | None = None,
    ) -> dict[str, Any]:
        if not live and not fixture_date:
            fixture_date = date.today().isoformat()
        values = self.client.fixtures(
            live=live,
            fixture_date=fixture_date,
            league=league,
            season=season,
            next_count=next_count,
        )
        return {
            "schema_version": "v1",
            "provider": "api_football",
            "query": {"live": live, "date": fixture_date, "league": league, "season": season, "next": next_count},
            "fixture_count": len(values),
            "fixtures": values,
            "cache_note": "Responses are cached on the TactIQ backend to protect the provider quota.",
        }

    def leagues(self) -> dict[str, Any]:
        values = self.client.leagues(current=True)
        return {"schema_version": "v1", "provider": "api_football", "league_count": len(values), "leagues": values, "cache_note": "Competition reference data is cached for 24 hours."}

    def fixture(self, fixture_id: int) -> dict[str, Any]:
        return self.client.fixture_snapshot(fixture_id)

    def matchup_preview(self, fixture_id: int, *, recent_match_count: int = 5) -> dict[str, Any]:
        """Build a football-first recent-form preview without predictive claims."""
        fixture_raw = self.client.fixture_data(fixture_id)
        fixture = serialize_live_fixture(fixture_raw)
        league_id = fixture["competition"]["league_id"]
        season = fixture["competition"]["season"]
        if league_id is None or season is None:
            raise ValueError("The selected fixture has no league-season identity.")

        teams = [fixture["home_team"], fixture["away_team"]]
        managers = {int(team["team_id"]): self._current_manager(int(team["team_id"])) for team in teams}
        recent_lists: dict[int, list[dict[str, Any]]] = {}
        for team in teams:
            team_id = int(team["team_id"])
            candidates = self.client.recent_fixture_data(
                team_id=team_id, league_id=int(league_id), season=int(season), last=max(10, recent_match_count),
            )
            manager_start = managers[team_id].get("start_date")
            if manager_start:
                candidates = [row for row in candidates if str((row.get("fixture") or {}).get("date") or "")[:10] >= manager_start]
            recent_lists[team_id] = sorted(
                candidates, key=lambda row: str((row.get("fixture") or {}).get("date") or ""), reverse=True,
            )[:recent_match_count]

        ids = [int((row.get("fixture") or {})["id"]) for rows in recent_lists.values() for row in rows]
        detailed = {int((row.get("fixture") or {})["id"]): row for row in self.client.fixture_details(ids)}
        profiles = []
        for team in teams:
            team_id = int(team["team_id"])
            rows = [detailed.get(int((row.get("fixture") or {})["id"]), row) for row in recent_lists[team_id]]
            profiles.append(self._recent_team_profile(team, managers[team_id], rows))

        return {
            "schema_version": "tactiq.api-football-matchup-preview.v1",
            "provider": "api_football",
            "fixture": fixture,
            "sample_definition": {
                "requested_recent_matches": recent_match_count,
                "competition_only": True,
                "current_manager_tenure_only": True,
                "unit_of_evidence": "completed_match",
            },
            "teams": profiles,
            "matchup_read": self._matchup_read(profiles),
            "basic_stats_note": "Averages use only the listed completed matches with available provider statistics.",
            "limitations": [
                "This is a small recent-match sample, not a stable long-term team identity.",
                "API-Football match statistics do not reveal off-ball positioning, defensive-line height or player movement.",
                "The preview describes recent evidence and does not predict the result or prescribe a tactical plan.",
                "Manager-tenure filtering is applied only when the provider supplies a verifiable current-tenure start date.",
            ],
            "request_efficiency": "Historical match IDs are batched into one enriched fixture request and cached for six hours.",
        }

    def _current_manager(self, team_id: int) -> dict[str, Any]:
        rows = self.client.coaches(team_id)
        if not rows:
            return {"manager_id": None, "name": "Manager unavailable", "photo_url": None, "start_date": None, "verified": False}
        selected = next((row for row in rows if (row.get("team") or {}).get("id") == team_id), rows[0])
        career = [item for item in selected.get("career") or [] if (item.get("team") or {}).get("id") == team_id]
        current = next((item for item in career if not item.get("end")), None)
        if current is None and career:
            current = max(career, key=lambda item: str(item.get("start") or ""))
        return {
            "manager_id": selected.get("id"),
            "name": selected.get("name") or "Manager unavailable",
            "photo_url": selected.get("photo"),
            "start_date": (current or {}).get("start"),
            "verified": current is not None,
        }

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _team_stats(cls, row: Mapping[str, Any], team_id: int) -> dict[str, float | None]:
        block = next((item for item in row.get("statistics") or [] if (item.get("team") or {}).get("id") == team_id), None)
        values = {item.get("type"): item.get("value") for item in (block or {}).get("statistics") or []}
        names = {
            "possession": "Ball Possession", "shots": "Total Shots", "shots_on_target": "Shots on Goal",
            "shots_inside_box": "Shots insidebox", "shots_outside_box": "Shots outsidebox",
            "passes": "Total passes", "accurate_passes": "Passes accurate", "pass_accuracy": "Passes %",
            "corners": "Corner Kicks", "fouls": "Fouls", "saves": "Goalkeeper Saves",
        }
        return {key: cls._number(values.get(label)) for key, label in names.items()}

    @staticmethod
    def _average(values: list[float | None]) -> float | None:
        clean = [value for value in values if value is not None]
        return round(sum(clean) / len(clean), 1) if clean else None

    @classmethod
    def _recent_team_profile(cls, team: Mapping[str, Any], manager: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        team_id = int(team["team_id"])
        matches, metric_values, formations = [], {}, []
        for row in rows:
            fixture = row.get("fixture") or {}; sides = row.get("teams") or {}; goals = row.get("goals") or {}
            is_home = (sides.get("home") or {}).get("id") == team_id
            opponent = sides.get("away") if is_home else sides.get("home")
            scored = goals.get("home") if is_home else goals.get("away"); conceded = goals.get("away") if is_home else goals.get("home")
            result = "D" if scored == conceded else ("W" if (scored or 0) > (conceded or 0) else "L")
            own = cls._team_stats(row, team_id)
            opponent_stats = cls._team_stats(row, int((opponent or {}).get("id") or -1))
            lineup = next((item for item in row.get("lineups") or [] if (item.get("team") or {}).get("id") == team_id), None)
            formation = (lineup or {}).get("formation")
            if formation: formations.append(formation)
            enriched = {**own, "shots_faced": opponent_stats.get("shots"), "shots_on_target_faced": opponent_stats.get("shots_on_target")}
            for key, value in enriched.items(): metric_values.setdefault(key, []).append(value)
            metric_values.setdefault("goals_for", []).append(cls._number(scored)); metric_values.setdefault("goals_against", []).append(cls._number(conceded))
            matches.append({
                "fixture_id": fixture.get("id"), "date": str(fixture.get("date") or "")[:10],
                "opponent": {"team_id": (opponent or {}).get("id"), "name": (opponent or {}).get("name"), "logo_url": (opponent or {}).get("logo")},
                "venue": "Home" if is_home else "Away", "result": result, "goals_for": scored, "goals_against": conceded,
                "formation": formation, "statistics_available": any(value is not None for value in own.values()),
            })
        averages = {key: cls._average(values) for key, values in metric_values.items()}
        record = Counter(match["result"] for match in matches)
        common_formation = Counter(formations).most_common(1)[0][0] if formations else None
        control = averages.get("possession")
        control_text = "They have usually shared control fairly evenly."
        if control is not None and control >= 55: control_text = "They have usually spent more of these matches controlling the ball."
        elif control is not None and control <= 45: control_text = "They have usually played with less of the ball and relied more on moments without sustained possession."
        attack_text = "Their recent attacking output cannot be described reliably from the available statistics."
        if averages.get("shots") is not None:
            attack_text = f"They have averaged {averages['shots']:.1f} shots and {averages.get('shots_on_target') or 0:.1f} on target across this sample."
        defence_text = "Recent defensive exposure is unavailable."
        if averages.get("shots_faced") is not None:
            defence_text = f"Opponents have averaged {averages['shots_faced']:.1f} shots against them, with {averages.get('goals_against') or 0:.1f} goals conceded per match."
        return {
            "team": dict(team), "manager": dict(manager), "matches_in_sample": len(matches),
            "form": "".join(match["result"] for match in matches),
            "record": {"wins": record["W"], "draws": record["D"], "losses": record["L"]},
            "most_common_formation": common_formation, "averages": averages, "recent_matches": matches,
            "football_read": {"control": control_text, "attacking_output": attack_text, "defensive_exposure": defence_text},
        }

    @staticmethod
    def _matchup_read(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(profiles) != 2: return []
        home, away = profiles; observations = []
        def add(title: str, explanation: str, evidence: dict[str, Any]): observations.append({"title": title, "explanation": explanation, "evidence": evidence})
        hp, ap = home["averages"].get("possession"), away["averages"].get("possession")
        if hp is not None and ap is not None:
            if abs(hp - ap) >= 7:
                higher, lower = (home, away) if hp > ap else (away, home)
                add("The recent control profiles look different", f"{higher['team']['name']} have recently played with considerably more of the ball than {lower['team']['name']}. The match itself may differ, but this is a useful contrast to watch.", {str(home['team']['team_id']): hp, str(away['team']['team_id']): ap, "unit": "percent possession"})
            else: add("Both teams have had a similar share of the ball", "Their recent possession levels are close enough that neither side enters this comparison with an obvious control advantage from this sample.", {str(home['team']['team_id']): hp, str(away['team']['team_id']): ap, "unit": "percent possession"})
        hs, ass = home["averages"].get("shots"), away["averages"].get("shots")
        if hs is not None and ass is not None:
            higher, lower = (home, away) if hs >= ass else (away, home)
            add("Compare how often each side turns attacks into shots", f"{higher['team']['name']} have produced the higher recent shot volume. Review whether that comes from sustained pressure or isolated attacking moments in the listed matches.", {str(home['team']['team_id']): hs, str(away['team']['team_id']): ass, "unit": "shots per match"})
        for attack, defence in ((home, away), (away, home)):
            produced, faced = attack["averages"].get("shots"), defence["averages"].get("shots_faced")
            if produced is not None and faced is not None:
                add(f"{attack['team']['name']} attack against {defence['team']['name']} recent defensive exposure", f"{attack['team']['name']} have averaged {produced:.1f} shots while {defence['team']['name']} have faced {faced:.1f}. These figures frame a review question; they do not predict how many chances this match will contain.", {"shots_produced": produced, "shots_faced": faced})
        return observations[:4]


__all__ = ["LiveFootballService"]
