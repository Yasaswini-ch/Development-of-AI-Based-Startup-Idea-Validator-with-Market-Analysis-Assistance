# AI Based Startup Idea Validator

Development of an AI-based startup idea validator with market analysis assistance.

The project lets a founder enter a startup idea, target customer, and problem statement,
and get back an initial validation summary backed by real web search results (via
Tavily). Milestone 1 is in progress — see [`docs/milestone1-plan.md`](docs/milestone1-plan.md)
for the current task breakdown and timeline.

## Architecture

The app is being split into a proper frontend/backend, per
[`docs/architecture.md`](docs/architecture.md):

| Layer      | Tech                                  |
|------------|----------------------------------------|
| Frontend   | React + Tailwind CSS (`frontend/`) |
| Backend    | FastAPI (`backend/`) — exposes `POST /validate` |
| Search agent | Python module calling the Tavily API (`backend/agent/search_agent.py`) |
| Database   | None yet |
| Deployment | [Render](https://render.com) (`render.yaml`) |
| Version control | Git / GitHub |

The original single-file Streamlit prototype (`app.py`) is kept for reference but is
superseded by the `frontend/` + `backend/` split going forward.

## Project Structure

```
.
├── frontend/           # React + Tailwind app (idea submission UI)
├── backend/            # FastAPI app + Tavily search agent
│   ├── main.py           # POST /validate route
│   └── agent/
│       └── search_agent.py
├── docs/
│   ├── architecture.md       # system design, data flow, API contract
│   ├── milestone1-plan.md    # task division + timeline
│   └── frontend-spec.md      # UI design spec
├── app.py               # legacy Streamlit prototype
├── requirements.txt      # Streamlit prototype dependencies
├── render.yaml           # Render deployment config
└── README.md
```

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.10+ and pip
- A [Tavily](https://tavily.com) API key

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in TAVILY_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL should point at the backend, e.g. http://127.0.0.1:8000
npm run dev
```

The frontend will be available at `http://localhost:5173` and calls the backend at the
URL set in `VITE_API_URL`.

### Legacy Streamlit prototype

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Branching Strategy

- **`staging`** — active development branch. All feature work and fixes land here first.
- **`main`** — stable, reviewed branch. Only tested, working code is merged here from `staging`.

Workflow: branch off `staging` for a feature/fix → open a PR into `staging` → once verified,
`staging` is merged into `main` for a stable release.

## Deployment

Deployment is handled via Render, configured in [`render.yaml`](render.yaml).
`render.yaml` currently deploys the legacy Streamlit prototype — updating it for the new
frontend + backend split is part of the Milestone 1 integration/deployment task (see
[`docs/milestone1-plan.md`](docs/milestone1-plan.md)).

## Contributing

1. Create a branch off `staging`.
2. Make your changes and test locally (see Getting Started above).
3. Open a PR into `staging`.
4. Once verified, changes are promoted to `main`.
