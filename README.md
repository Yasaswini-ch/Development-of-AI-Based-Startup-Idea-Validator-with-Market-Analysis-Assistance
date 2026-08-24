# AI Based Startup Idea Validator

Development of an AI-based startup idea validator with market analysis assistance.

The project lets a founder enter a startup idea, target customer, and problem statement,
and get back an initial validation summary. It is an early-stage build — the current
version captures and displays input; AI-driven scoring and market analysis are planned
next (see [Roadmap](#roadmap)).

## Current Architecture

The app is currently a single Streamlit service — there is no separate backend or
database yet.

| Layer      | Tech                                  |
|------------|----------------------------------------|
| Frontend   | [Streamlit](https://streamlit.io) (`app.py`) |
| Backend    | None yet — logic runs inline in the Streamlit process |
| Database   | None yet |
| Deployment | [Render](https://render.com) (`render.yaml`) |
| Version control | Git / GitHub |

## Project Structure

```
.
├── app.py            # Streamlit app: UI + form handling + validation display
├── requirements.txt  # Python dependencies
├── render.yaml        # Render deployment config
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.9+
- pip

### Local setup

```bash
git clone https://github.com/<your-org>/<repo>.git
cd "AI Based Startup Idea Validator"
pip install -r requirements.txt
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

## Branching Strategy

- **`staging`** — active development branch. All feature work and fixes land here first.
- **`main`** — stable, reviewed branch. Only tested, working code is merged here from `staging`.

Workflow: branch off `staging` for a feature/fix → open a PR into `staging` → once verified,
`staging` is merged into `main` for a stable release.

## Deployment

Deployment is handled via Render, configured in [`render.yaml`](render.yaml).

**Current service:**

| Service | Type | Branch | Build | Start |
|---|---|---|---|---|
| `startup-validator-staging` | web (Python) | `staging` | `pip install -r requirements.txt` | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |

Render auto-deploys on every push to the `staging` branch. A separate `main`-tracking
service can be added once the app is ready for stable releases.

## Roadmap

The project is planned to grow from a single Streamlit script into a proper
frontend/backend split:

- **Backend** — introduce a FastAPI service to hold business logic (idea validation,
  market analysis, AI/LLM calls) behind a REST API, instead of embedding it in the
  Streamlit script.
- **Database** — add a managed Postgres instance (via Render) with SQLAlchemy/SQLModel
  models and Alembic migrations, to persist submitted ideas and validation results.
- **Frontend** — Streamlit remains the UI but becomes a thin client calling the backend
  API rather than doing the work itself.
- **Deployment** — split into two Render services (`frontend`, `backend`) plus a managed
  Postgres service, wired together via environment variables.
- **AI integration** — connect an LLM/market-data API to generate real scores,
  competitor insights, and recommendations (currently placeholder metrics in the UI).

## Contributing

1. Create a branch off `staging`.
2. Make your changes and test locally with `streamlit run app.py`.
3. Open a PR into `staging`.
4. Once verified, changes are promoted to `main`.
