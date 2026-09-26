# TactIQ

TactIQ is a football tactical-intelligence research MVP. It turns event and
tracking data into evidence-backed, football-readable team profiles, match
stories, pre-match briefings, tactical findings, and representative pitch
moments.

The repository contains:

- a provider-independent Python analysis engine;
- adapters for SkillCorner Open Data, StatsBomb Open Data, and Metrica samples;
- integrations for current fixture and match information from API-Football and
  football-data.org;
- a local JSON HTTP API;
- a React and TypeScript analyst interface;
- deterministic evidence, ranking, explanation-fallback, and QA layers.

## Local setup

Requirements: Python 3.13+, Node.js, and npm.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Copy `.env.example` to `.env` and add only the provider keys you want to use.
Never put provider keys in `VITE_*` variables because those are exposed to the
browser.

## Data

Downloaded provider data is intentionally excluded from Git. Place local data
in these paths when the corresponding workflows are needed:

- `opendata/data/matches/` for SkillCorner Open Data matches;
- `external_data/statsbomb_open_data/` for StatsBomb Open Data;
- `external_data/metrica/` for Metrica sample data.

The UI can still use live fixture integrations without those research datasets.

## Run

From the repository root, start the local API:

```powershell
$env:TACTIQ_API_FOOTBALL_KEY = "your-key"
$env:TACTIQ_FOOTBALL_DATA_KEY = "your-key"
python -m src.api.http_server --matches-root opendata/data/matches
```

In another terminal:

```powershell
cd frontend
$env:VITE_USE_MOCK = "false"
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open `http://127.0.0.1:5173/`.

The API binds to loopback, and development CORS is limited to local Vite
origins. See [frontend/README.md](frontend/README.md) for API routes and more
frontend details.

## Tests

The test suite uses Python's standard-library test runner:

```powershell
python -m unittest discover -s tests -v
```

Some integration and product-validation workflows require the external data
described above. Generated artifacts, provider datasets, browser caches, logs,
virtual environments, and real credentials are intentionally not versioned.

## Current scope

TactIQ is an evidence-first research product, not a prediction or tactical
recommendation engine. Its visible football explanations remain grounded in
deterministic metrics and preserve their limitations and provenance.
