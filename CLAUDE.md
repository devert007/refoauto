# RefoAuto - DialogGauge Data Pipeline

Multi-client project for generating JSON from data sources and syncing with DialogGauge API.

## Project Structure

```
refoauto/
├── CLAUDE.md                    # This file (project context)
├── clients_config.json          # All clients config (locations, branches, settings)
├── run.py                       # Universal runner: python run.py [client] script | web
├── config/
│   └── .dg_session.json         # Shared auth session
├── src/
│   ├── shared/                  # Shared modules (models, API client, sync logic)
│   │   ├── api_client.py        # DGApiClient class (auth, requests)
│   │   ├── sync.py              # sync_items, normalize_name, update_references
│   │   ├── utils.py             # load_json, save_json
│   │   └── models/
│   │       └── pydantic_models.py  # Service, ServiceCategory, Practitioner, etc.
│   ├── config_manager.py        # Client configuration manager
│   ├── hortman/                 # Client: Hortman Clinics
│   │   └── CLAUDE.md
│   └── milena/                  # Client: Milena
│       └── CLAUDE.md
├── web/                         # Web UI
│   ├── server.py                # Python HTTP server + JSON API
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
└── .env                         # ACTIVE_CLIENT=hortman|milena
```

## Running

```bash
# CLI scripts
python run.py hortman get_categories --all
python run.py milena sync_with_api --categories-only

# Web UI
python run.py web                # http://localhost:8080
python run.py web --port 3000
```

## Key Architecture

- **Shared modules** (`src/shared/`): Models, API client, sync logic shared by all clients
- **Per-client scripts** (`src/{client}/scripts/`): Client-specific data processing
- **Web UI** (`web/`): Manage clients, upload data, configure mappings, run pipeline
- **Single auth session** (`config/.dg_session.json`): Shared across all clients
- Client scripts import from `src.shared.api_client` and `src.shared.sync`

## Pipeline

1. **Parse** — CSV/JSON input → 4 JSON files (categories, services, practitioners, service_practitioners)
2. **Validate** — structure, FK, spot-check
3. **Sync IDs** — match local names with DialogGauge API, assign correct IDs
4. **Upload** — POST/PUT data to API (categories → services → practitioners → links)
5. **Test** — API validation, content-stats

## Rules

- Prompt for each client is in `src/{client}/docs/PROMPT.md`
- Don't commit credentials (`config/*.json` in .gitignore)
- Always run tests before uploading
- `fix_locations.py` is dry-run by default, needs `--execute` for real changes
- Support ALL configured locations per client, not just the first one
