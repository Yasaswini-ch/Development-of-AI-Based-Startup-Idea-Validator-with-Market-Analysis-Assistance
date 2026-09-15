# Deployment Guide

This project is deployed on Render as two services from the same GitHub repository.

## Branches

- `staging`: active development and demo testing
- `main`: reviewed stable code only

Deploy and test from `staging` first. Merge to `main` only after the deployed app is
working.

## Backend Service

Render service:

```text
startup-validator-backend
```

Settings:

```text
Runtime: Python
Root Directory: backend
Build Command: pip install -r requirements.txt && python -m spacy download en_core_web_sm
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Branch: staging
```

Environment variables:

```text
GROQ_API_KEY       required
TAVILY_API_KEY     optional
FRONTEND_ORIGIN    frontend Render URL
PYTHON_VERSION     3.12.7
```

## Frontend Service

Render service:

```text
startup-validator-frontend
```

Settings:

```text
Runtime: Static Site
Root Directory: frontend
Build Command: npm install && npm run build
Publish Directory: dist
Branch: staging
```

Environment variables:

```text
VITE_API_URL    backend Render URL
```

## After Creating Services

Render may assign URLs that differ from the placeholder values in `render.yaml`.
After deployment, update:

- backend `FRONTEND_ORIGIN` to the frontend URL
- frontend `VITE_API_URL` to the backend URL

Then redeploy both services.

## Quick Verification

Open:

```text
https://<backend-url>/health
```

Expected response:

```json
{"status":"ok"}
```

Then open the frontend URL, submit a sample idea, and confirm the UI shows sources,
market opportunity, competitors, source agreement, and white-space analysis.
