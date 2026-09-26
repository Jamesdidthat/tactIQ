# TactIQ single-match frontend

Run locally from this directory:

```powershell
npm.cmd run dev
```

The interface uses contract-accurate v1 mock responses by default. To run it
against a real local SkillCorner match, start the localhost-only API from the
repository root:

```powershell
python -m src.api.http_server --matches-root opendata/data/matches
```

Then set the frontend development environment:

```powershell
$env:VITE_USE_MOCK = "false"
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
$env:VITE_MATCH_ID = "2017461"
```

The API binds only to loopback and sends CORS headers only for local Vite
origins (`localhost` or `127.0.0.1`).

The client expects these v1 paths:

- `GET /matches/{matchId}/summary`
- `GET /matches/{matchId}/findings`
- `GET /matches/{matchId}/findings/{findingId}`
- `GET /matches/{matchId}/findings/{findingId}/moments/{moment}/frame`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/summary`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/baselines`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/findings`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/tendencies`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/unusual-matches`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/archetypes`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/relationships`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/matches`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/matches/{matchId}/story`
- `GET /event-profiles/{provider}/{teamId}/{competitionId}/{seasonId}/matches/{matchId}/story/explanation`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/summary`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/metrics`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/findings`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/interactions`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/interaction-findings`
- `GET /opponent-comparisons/{targetProvider}/{targetTeam}/{targetCompetition}/{targetSeason}/{opponentProvider}/{opponentTeam}/{opponentCompetition}/{opponentSeason}/review-priorities`
- the same opponent-comparison path ending in `/metrics` or `/findings`

With the real API configured, the Barcelona validation page is:

`http://localhost:5173/teams/217?provider=statsbomb_open_data&competition_id=11&season_id=27`

No authentication, database persistence, or tactical recommendations are included.

The pre-match comparison setup page is available at:

`http://localhost:5173/opponent-comparison`
