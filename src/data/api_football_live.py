"""Secure API-Football client and provider-neutral live-match serializers.

API-Football is a live score/statistics source.  It is intentionally kept
separate from :class:`CanonicalMatchBundle`: its incident feed is not
continuous tracking and is not equivalent to StatsBomb's event data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from threading import RLock
import time
from typing import Any, Callable, Mapping

import httpx


DEFAULT_BASE_URL = "https://v3.football.api-sports.io"


class ApiFootballConfigurationError(RuntimeError):
    """Raised when the live provider has not been configured safely."""


class ApiFootballRequestError(RuntimeError):
    """Raised for a failed or invalid upstream response."""


@dataclass(frozen=True)
class ApiFootballSettings:
    api_key: str | None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 15.0
    fixture_list_ttl_seconds: float = 180.0
    fixture_detail_ttl_seconds: float = 300.0
    historical_ttl_seconds: float = 21600.0
    reference_ttl_seconds: float = 86400.0

    @classmethod
    def from_environment(cls) -> "ApiFootballSettings":
        return cls(
            api_key=os.getenv("TACTIQ_API_FOOTBALL_KEY") or None,
            base_url=os.getenv("TACTIQ_API_FOOTBALL_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(os.getenv("TACTIQ_API_FOOTBALL_TIMEOUT_SECONDS", "15")),
            fixture_list_ttl_seconds=float(os.getenv("TACTIQ_API_FOOTBALL_LIST_TTL_SECONDS", "180")),
            fixture_detail_ttl_seconds=float(os.getenv("TACTIQ_API_FOOTBALL_DETAIL_TTL_SECONDS", "300")),
            historical_ttl_seconds=float(os.getenv("TACTIQ_API_FOOTBALL_HISTORICAL_TTL_SECONDS", "21600")),
            reference_ttl_seconds=float(os.getenv("TACTIQ_API_FOOTBALL_REFERENCE_TTL_SECONDS", "86400")),
        )


class _TtlCache:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._values: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: tuple[Any, ...]) -> Any | None:
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if self._clock() >= expires_at:
                del self._values[key]
                return None
            return value

    def set(self, key: tuple[Any, ...], value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._values[key] = (self._clock() + ttl_seconds, value)


def _team(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    return {
        "team_id": value.get("id"),
        "name": value.get("name"),
        "logo_url": value.get("logo"),
        "winner": value.get("winner"),
    }


def _score(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    return {"home": value.get("home"), "away": value.get("away")}


def serialize_live_fixture(raw: Mapping[str, Any]) -> dict[str, Any]:
    fixture = raw.get("fixture") or {}
    status = fixture.get("status") or {}
    league = raw.get("league") or {}
    teams = raw.get("teams") or {}
    score = raw.get("score") or {}
    return {
        "fixture_id": fixture.get("id"),
        "kickoff": fixture.get("date"),
        "timezone": fixture.get("timezone"),
        "venue": {
            "id": (fixture.get("venue") or {}).get("id"),
            "name": (fixture.get("venue") or {}).get("name"),
            "city": (fixture.get("venue") or {}).get("city"),
        },
        "referee": fixture.get("referee"),
        "status": {
            "long": status.get("long"),
            "short": status.get("short"),
            "elapsed": status.get("elapsed"),
            "extra": status.get("extra"),
            "is_live": status.get("short") in {"1H", "HT", "2H", "ET", "BT", "P", "INT", "LIVE"},
        },
        "competition": {
            "league_id": league.get("id"),
            "name": league.get("name"),
            "country": league.get("country"),
            "logo_url": league.get("logo"),
            "flag_url": league.get("flag"),
            "season": league.get("season"),
            "round": league.get("round"),
        },
        "home_team": _team(teams.get("home")),
        "away_team": _team(teams.get("away")),
        "goals": _score(raw.get("goals")),
        "score": {
            "halftime": _score(score.get("halftime")),
            "fulltime": _score(score.get("fulltime")),
            "extratime": _score(score.get("extratime")),
            "penalty": _score(score.get("penalty")),
        },
    }


def _event(raw: Mapping[str, Any]) -> dict[str, Any]:
    event_time = raw.get("time") or {}
    return {
        "elapsed": event_time.get("elapsed"),
        "extra": event_time.get("extra"),
        "team": _team(raw.get("team")),
        "player": dict(raw.get("player") or {}),
        "assist": dict(raw.get("assist") or {}),
        "type": raw.get("type"),
        "detail": raw.get("detail"),
        "comments": raw.get("comments"),
    }


def _statistics(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "team": _team(raw.get("team")),
        "statistics": [
            {"label": item.get("type"), "value": item.get("value")}
            for item in raw.get("statistics") or []
        ],
    }


def _lineup(raw: Mapping[str, Any]) -> dict[str, Any]:
    def players(values: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        return [dict(item.get("player") or {}) for item in values or []]

    return {
        "team": _team(raw.get("team")),
        "formation": raw.get("formation"),
        "coach": dict(raw.get("coach") or {}),
        "starting_xi": players(raw.get("startXI")),
        "substitutes": players(raw.get("substitutes")),
    }


def _player_statistics(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "team": _team(raw.get("team")),
        "players": [
            {"player": dict(item.get("player") or {}), "statistics": list(item.get("statistics") or [])}
            for item in raw.get("players") or []
        ],
    }


class ApiFootballClient:
    """Small cached client whose API key never enters product responses."""

    def __init__(
        self,
        settings: ApiFootballSettings | None = None,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or ApiFootballSettings.from_environment()
        self._client = client
        self._cache = _TtlCache(clock)

    @property
    def configured(self) -> bool:
        return bool(self.settings.api_key)

    def _get(self, endpoint: str, params: Mapping[str, Any], ttl_seconds: float) -> list[dict[str, Any]]:
        if not self.settings.api_key:
            raise ApiFootballConfigurationError(
                "API-Football is not configured. Set TACTIQ_API_FOOTBALL_KEY on the backend."
            )
        clean_params = {key: value for key, value in params.items() if value not in (None, "")}
        cache_key = (endpoint, *sorted(clean_params.items()))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        request = self._client.get if self._client is not None else httpx.get
        try:
            response = request(
                f"{self.settings.base_url}/{endpoint.lstrip('/')}",
                params=clean_params,
                headers={"x-apisports-key": self.settings.api_key, "Accept": "application/json"},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ApiFootballRequestError("API-Football request failed.") from error
        errors = payload.get("errors")
        if errors and errors != [] and errors != {}:
            raise ApiFootballRequestError(f"API-Football rejected the request: {errors}")
        values = payload.get("response")
        if not isinstance(values, list):
            raise ApiFootballRequestError("API-Football returned an invalid response contract.")
        self._cache.set(cache_key, values, ttl_seconds)
        return values

    def fixtures(
        self,
        *,
        live: str | None = None,
        fixture_date: str | date | None = None,
        league: int | None = None,
        season: int | None = None,
        next_count: int | None = None,
        timezone: str = "Africa/Lagos",
    ) -> list[dict[str, Any]]:
        if live and fixture_date:
            raise ValueError("Choose either live fixtures or a fixture date, not both.")
        if isinstance(fixture_date, date):
            fixture_date = fixture_date.isoformat()
        values = self._get(
            "fixtures",
            {"live": live, "date": fixture_date, "league": league, "season": season, "next": next_count, "timezone": timezone},
            self.settings.fixture_list_ttl_seconds,
        )
        return [serialize_live_fixture(item) for item in values]

    def leagues(self, *, current: bool = True) -> list[dict[str, Any]]:
        rows = self._get("leagues", {"current": "true" if current else None}, self.settings.reference_ttl_seconds)
        result = []
        for row in rows:
            league, country = row.get("league") or {}, row.get("country") or {}
            seasons = row.get("seasons") or []
            current_season = next((item for item in seasons if item.get("current")), None)
            if current_season is None and seasons:
                current_season = max(seasons, key=lambda item: int(item.get("year") or 0))
            result.append({
                "league_id": league.get("id"), "name": league.get("name"), "type": league.get("type"),
                "logo_url": league.get("logo"), "country": country.get("name"), "country_code": country.get("code"),
                "flag_url": country.get("flag"), "current_season": (current_season or {}).get("year"),
                "season_start": (current_season or {}).get("start"), "season_end": (current_season or {}).get("end"),
                "coverage": dict((current_season or {}).get("coverage") or {}),
            })
        return sorted(result, key=lambda item: (str(item["country"] or ""), str(item["name"] or ""), int(item["league_id"] or 0)))

    def fixture_snapshot(self, fixture_id: int) -> dict[str, Any]:
        fixture_rows = self._get("fixtures", {"id": fixture_id}, self.settings.fixture_detail_ttl_seconds)
        if len(fixture_rows) != 1:
            raise KeyError(f"Fixture {fixture_id} was not found or was ambiguous.")

        fixture_raw = fixture_rows[0]
        resources: dict[str, list[dict[str, Any]]] = {}
        warnings: list[str] = []
        for name, endpoint in (
            ("events", "fixtures/events"),
            ("statistics", "fixtures/statistics"),
            ("lineups", "fixtures/lineups"),
            ("players", "fixtures/players"),
        ):
            # Fixture-ID and batched-ID responses can embed all four detail
            # blocks.  Reuse them instead of spending four extra quota calls.
            if name in fixture_raw:
                resources[name] = list(fixture_raw.get(name) or [])
                continue
            try:
                resources[name] = self._get(endpoint, {"fixture": fixture_id}, self.settings.fixture_detail_ttl_seconds)
            except ApiFootballRequestError:
                resources[name] = []
                warnings.append(f"{name} are currently unavailable from API-Football.")

        events = [_event(item) for item in resources["events"]]
        statistics = [_statistics(item) for item in resources["statistics"]]
        lineups = [_lineup(item) for item in resources["lineups"]]
        players = [_player_statistics(item) for item in resources["players"]]
        return {
            "schema_version": "tactiq.live-match.v1",
            "provider": "api_football",
            "fixture": serialize_live_fixture(fixture_raw),
            "capabilities": {
                "has_live_fixture_state": True,
                "has_coarse_incident_timeline": bool(events),
                "has_team_match_statistics": bool(statistics),
                "has_lineups": bool(lineups),
                "has_player_match_statistics": bool(players),
                "has_team_branding": True,
                "has_continuous_tracking": False,
                "has_ball_tracking": False,
                "has_360_snapshots": False,
                "has_tactical_phases": False,
                "has_verified_attacking_direction": False,
            },
            "events": events,
            "team_statistics": statistics,
            "lineups": lineups,
            "player_statistics": players,
            "warnings": warnings,
            "analysis_scope": (
                "Live score, match incidents, lineups and provider-supplied statistics only. "
                "This feed does not support tracking-derived shape, off-ball movement or causal tactical claims."
            ),
        }

    def fixture_data(self, fixture_id: int) -> dict[str, Any]:
        """Return one raw enriched fixture for server-side deterministic analysis."""
        rows = self._get("fixtures", {"id": fixture_id}, self.settings.fixture_detail_ttl_seconds)
        if len(rows) != 1:
            raise KeyError(f"Fixture {fixture_id} was not found or was ambiguous.")
        return rows[0]

    def recent_fixture_data(
        self, *, team_id: int, league_id: int, season: int, last: int = 10,
    ) -> list[dict[str, Any]]:
        return self._get(
            "fixtures",
            {"team": team_id, "league": league_id, "season": season, "last": last, "status": "FT-AET-PEN"},
            self.settings.historical_ttl_seconds,
        )

    def fixture_details(self, fixture_ids: list[int]) -> list[dict[str, Any]]:
        unique_ids = list(dict.fromkeys(int(value) for value in fixture_ids))
        if not unique_ids:
            return []
        if len(unique_ids) > 20:
            raise ValueError("API-Football accepts at most 20 fixture IDs per batched detail request.")
        return self._get(
            "fixtures", {"ids": "-".join(map(str, unique_ids))}, self.settings.historical_ttl_seconds,
        )

    def coaches(self, team_id: int) -> list[dict[str, Any]]:
        return self._get("coachs", {"team": team_id}, self.settings.historical_ttl_seconds)


__all__ = [
    "ApiFootballClient",
    "ApiFootballConfigurationError",
    "ApiFootballRequestError",
    "ApiFootballSettings",
    "serialize_live_fixture",
]
