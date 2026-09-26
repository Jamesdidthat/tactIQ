"""Cached football-data.org client for current fixtures and recent results.

The API token is read only from the backend environment and is never included
in product responses.  football-data.org is an event/result feed; it is not a
continuous tracking provider and must not be treated as one.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from threading import RLock
import time
from typing import Any, Callable, Mapping

import httpx


DEFAULT_BASE_URL = "https://api.football-data.org/v4"


class FootballDataConfigurationError(RuntimeError):
    """Raised when the backend token has not been configured."""


class FootballDataRequestError(RuntimeError):
    """Raised when football-data.org rejects or cannot fulfil a request."""


@dataclass(frozen=True)
class FootballDataSettings:
    api_key: str | None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 15.0
    fixture_ttl_seconds: float = 300.0
    history_ttl_seconds: float = 21600.0
    reference_ttl_seconds: float = 86400.0

    @classmethod
    def from_environment(cls) -> "FootballDataSettings":
        return cls(
            api_key=os.getenv("TACTIQ_FOOTBALL_DATA_KEY") or None,
            base_url=os.getenv("TACTIQ_FOOTBALL_DATA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(os.getenv("TACTIQ_FOOTBALL_DATA_TIMEOUT_SECONDS", "15")),
            fixture_ttl_seconds=float(os.getenv("TACTIQ_FOOTBALL_DATA_FIXTURE_TTL_SECONDS", "300")),
            history_ttl_seconds=float(os.getenv("TACTIQ_FOOTBALL_DATA_HISTORY_TTL_SECONDS", "21600")),
            reference_ttl_seconds=float(os.getenv("TACTIQ_FOOTBALL_DATA_REFERENCE_TTL_SECONDS", "86400")),
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


def serialize_team(raw: Mapping[str, Any] | None, *, winner: bool | None = None) -> dict[str, Any]:
    raw = raw or {}
    return {
        "team_id": raw.get("id"),
        "name": raw.get("name") or raw.get("shortName"),
        "short_name": raw.get("shortName"),
        "tla": raw.get("tla"),
        "logo_url": raw.get("crest"),
        "winner": winner,
    }


_LIVE_STATUSES = {"IN_PLAY", "PAUSED", "LIVE"}
_STATUS_SHORT = {
    "SCHEDULED": "NS",
    "TIMED": "NS",
    "IN_PLAY": "LIVE",
    "PAUSED": "HT",
    "FINISHED": "FT",
    "POSTPONED": "PST",
    "SUSPENDED": "SUSP",
    "CANCELLED": "CANC",
    "AWARDED": "AWD",
}


def serialize_fixture(raw: Mapping[str, Any]) -> dict[str, Any]:
    competition = raw.get("competition") or {}
    season = raw.get("season") or {}
    score = raw.get("score") or {}
    full_time = score.get("fullTime") or {}
    half_time = score.get("halfTime") or {}
    winner = score.get("winner")
    status = str(raw.get("status") or "")
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}
    return {
        "fixture_id": raw.get("id"),
        "kickoff": raw.get("utcDate"),
        "timezone": "UTC",
        "venue": {"id": None, "name": None, "city": None},
        "referee": ((raw.get("referees") or [{}])[0] or {}).get("name"),
        "status": {
            "long": status.replace("_", " ").title() if status else None,
            "short": _STATUS_SHORT.get(status, status or None),
            "elapsed": raw.get("minute"),
            "extra": raw.get("injuryTime"),
            "is_live": status in _LIVE_STATUSES,
        },
        "competition": {
            "league_id": competition.get("id"),
            "code": competition.get("code"),
            "name": competition.get("name"),
            "country": (competition.get("area") or {}).get("name"),
            "logo_url": competition.get("emblem"),
            "flag_url": (competition.get("area") or {}).get("flag"),
            "season": season.get("startDate", "")[:4] or None,
            "round": f"Matchday {raw.get('matchday')}" if raw.get("matchday") is not None else raw.get("stage"),
        },
        "home_team": serialize_team(home, winner=winner == "HOME_TEAM" if winner else None),
        "away_team": serialize_team(away, winner=winner == "AWAY_TEAM" if winner else None),
        "goals": {"home": full_time.get("home"), "away": full_time.get("away")},
        "score": {
            "halftime": {"home": half_time.get("home"), "away": half_time.get("away")},
            "fulltime": {"home": full_time.get("home"), "away": full_time.get("away")},
            "extratime": dict(score.get("extraTime") or {"home": None, "away": None}),
            "penalty": dict(score.get("penalties") or {"home": None, "away": None}),
        },
    }


class FootballDataClient:
    """Small cached v4 client with a backend-only authentication token."""

    def __init__(
        self,
        settings: FootballDataSettings | None = None,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or FootballDataSettings.from_environment()
        self._client = client
        self._cache = _TtlCache(clock)

    @property
    def configured(self) -> bool:
        return bool(self.settings.api_key)

    def _get(self, endpoint: str, params: Mapping[str, Any] | None, ttl_seconds: float) -> dict[str, Any]:
        if not self.settings.api_key:
            raise FootballDataConfigurationError(
                "football-data.org is not configured. Set TACTIQ_FOOTBALL_DATA_KEY on the backend."
            )
        clean_params = {key: value for key, value in (params or {}).items() if value not in (None, "")}
        cache_key = (endpoint, *sorted(clean_params.items()))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        request = self._client.get if self._client is not None else httpx.get
        try:
            response = request(
                f"{self.settings.base_url}/{endpoint.lstrip('/')}",
                params=clean_params,
                headers={"X-Auth-Token": self.settings.api_key, "Accept": "application/json"},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            detail = ""
            try:
                detail = str(error.response.json().get("message") or "")
            except (ValueError, AttributeError):
                pass
            suffix = f": {detail}" if detail else "."
            raise FootballDataRequestError(f"football-data.org rejected the request{suffix}") from error
        except (httpx.HTTPError, ValueError) as error:
            raise FootballDataRequestError("football-data.org request failed.") from error
        if not isinstance(payload, dict):
            raise FootballDataRequestError("football-data.org returned an invalid response contract.")
        self._cache.set(cache_key, payload, ttl_seconds)
        return payload

    def competitions(self) -> list[dict[str, Any]]:
        payload = self._get("competitions", {}, self.settings.reference_ttl_seconds)
        values = []
        for row in payload.get("competitions") or []:
            season = row.get("currentSeason") or {}
            area = row.get("area") or {}
            values.append({
                "competition_id": row.get("id"),
                "code": row.get("code"),
                "name": row.get("name"),
                "type": row.get("type"),
                "logo_url": row.get("emblem"),
                "country": area.get("name"),
                "country_code": area.get("code"),
                "flag_url": area.get("flag"),
                "current_season": season.get("startDate", "")[:4] or None,
                "season_start": season.get("startDate"),
                "season_end": season.get("endDate"),
                "current_matchday": season.get("currentMatchday"),
            })
        return values

    def competition_matches(
        self,
        code: str,
        *,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            f"competitions/{code}/matches",
            {"status": status, "dateFrom": date_from, "dateTo": date_to},
            self.settings.fixture_ttl_seconds,
        )
        return [serialize_fixture(row) for row in payload.get("matches") or []]

    def competition_teams(self, code: str) -> list[dict[str, Any]]:
        payload = self._get(f"competitions/{code}/teams", {}, self.settings.reference_ttl_seconds)
        return [serialize_team(row) for row in payload.get("teams") or []]

    def match_data(self, match_id: int) -> dict[str, Any]:
        return self._get(f"matches/{match_id}", {}, self.settings.fixture_ttl_seconds)

    def team_data(self, team_id: int) -> dict[str, Any]:
        return self._get(f"teams/{team_id}", {}, self.settings.history_ttl_seconds)

    def team_matches(
        self,
        team_id: int,
        *,
        competitions: str | None = None,
        status: str = "FINISHED",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            f"teams/{team_id}/matches",
            {"competitions": competitions, "status": status, "limit": limit},
            self.settings.history_ttl_seconds,
        )
        return list(payload.get("matches") or [])


__all__ = [
    "FootballDataClient",
    "FootballDataConfigurationError",
    "FootballDataRequestError",
    "FootballDataSettings",
    "serialize_fixture",
    "serialize_team",
]
