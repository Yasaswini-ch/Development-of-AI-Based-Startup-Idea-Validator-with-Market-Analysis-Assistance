# Deployment Guide

This project is deployed on Render as two web services and one PostgreSQL database,
all declared in `render.yaml` and built from the same GitHub repository.

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
GEMINI_API_KEY     recommended - the last two models in the LLM fallback chain,
                   the chat advisor's default, and competitor price/breadth refinement
TAVILY_API_KEY     optional - falls back to DuckDuckGo/Wikipedia/Hacker News
FRONTEND_ORIGIN    frontend Render URL
PYTHON_VERSION     3.12.7

# Database and accounts - see "Database (PostgreSQL on Render)" below
DATABASE_URL           set automatically from the Blueprint database
AUTH_SECRET_KEY        generated automatically by the Blueprint (generateValue)
ADMIN_EMAILS           optional - comma-separated emails to promote to admin
REQUIRE_PERSISTENT_DB  optional - set to 1 to refuse to start without Postgres
GOOGLE_OAUTH_CLIENT_ID optional - enables "Sign in with Google"; see "Google sign-in" below

# Optional - email delivery of reports (SendGrid HTTP API). Without these,
# /validate still accepts an email and returns 202/jobId past the threshold
# below, it just never actually sends the email.
SENDGRID_API_KEY                  optional
SENDGRID_FROM_EMAIL               optional - must be a verified sender in SendGrid
VALIDATE_ASYNC_THRESHOLD_SECONDS  optional
```

See `backend/.env.example` for the full list, including LLM model overrides, the
local Ollama tier, and database pool sizing.

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
VITE_API_URL           backend Render URL
VITE_GOOGLE_CLIENT_ID  optional - same value as the backend's GOOGLE_OAUTH_CLIENT_ID
```

`VITE_*` values are baked in at build time, so changing one needs a frontend redeploy,
not just a restart.

## Database (PostgreSQL on Render)

Accounts, validation sessions, background jobs, the response cache and the admin
event log are stored in PostgreSQL in production. Without it, the backend falls back
to a local SQLite file, which Render's free tier **wipes on every redeploy or
restart**, taking every account, saved validation and admin flag with it.

### Provisioning: the Blueprint-sync gotcha

`render.yaml` declares the database (`startup-validator-db`) and links it to the
backend with:

```yaml
- key: DATABASE_URL
  fromDatabase:
    name: startup-validator-db
    property: connectionString
```

**Declaring it in `render.yaml` does not create it.** Render only reads `render.yaml`
when the repository is connected as a **Blueprint** and that Blueprint is synced.
Services that were originally created by hand in the dashboard ignore the file. We hit
exactly this: the database was declared in `render.yaml` for a while, but no database
existed and `DATABASE_URL` was never set, so the backend silently ran on SQLite until a
manual Blueprint sync.

Steps:

1. In the Render dashboard, open **Blueprints** and connect this repository (or open
   the existing Blueprint).
2. Click **Manual Sync** (or **Apply**) and confirm that `startup-validator-db` appears
   in the list of resources to create.
3. After the sync finishes, open the backend service → **Environment** and confirm that
   `DATABASE_URL` is present and linked to the database.
4. Redeploy the backend if it did not redeploy on its own.
5. Verify with `GET /health` (see Quick Verification below): it must report
   `"database": "postgresql"`.

To make a missing database fail loudly instead of silently falling back to SQLite, set
`REQUIRE_PERSISTENT_DB=1` on the backend. Startup then fails with a clear error when
`DATABASE_URL` is missing.

### Free-tier expiry (30 days)

> ⚠️ Render's **free PostgreSQL databases expire 30 days after they are created**.
> Render gives a short grace period to upgrade; after that the database and all of its
> data are deleted. Note the creation date in the Render dashboard, and before any demo
> or defense either upgrade to a paid plan or recreate the database (and re-sync the
> Blueprint) well ahead of time. Recreating it starts with an empty database, so every
> account must sign up again and admins are re-promoted through `ADMIN_EMAILS`.

### Admin access (`ADMIN_EMAILS`)

The admin-only **Platform health** dashboard is gated by `users.is_admin`. There is no
sign-up option or endpoint that grants it. On Render there is no shell or SQL console
on the free tier, so promote admins with an environment variable:

1. Sign up in the app with the account that should be an admin.
2. On the backend service, set `ADMIN_EMAILS` to that email (comma-separate several).
   Matching is case-insensitive.
3. Save. The backend redeploys and promotes matching accounts on startup. Accounts
   created after the deploy are also promoted the first time their admin status is
   checked, so the order of "sign up" and "set the variable" doesn't matter.
4. Sign out and back in (or reload). **Platform health** now appears in the account
   menu.

`ADMIN_EMAILS` is not declared in `render.yaml`, so add it by hand in the dashboard.
Removing an email from the list does **not** demote an existing admin; do that with
SQL (`UPDATE users SET is_admin = false WHERE email = '...'`).

## Google sign-in (optional)

Without these two variables the Google button simply doesn't render and email/password
sign-in works as before.

1. In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services →
   Credentials, create an **OAuth client ID** of type *Web application*.
2. Under **Authorized JavaScript origins**, add the frontend URL (for example
   `https://startup-validator-frontend.onrender.com`) and `http://localhost:5173` for
   local development. No redirect URI is needed; the button uses Google Identity
   Services' popup flow and returns an ID token directly.
3. Set the client ID as `GOOGLE_OAUTH_CLIENT_ID` on the backend and
   `VITE_GOOGLE_CLIENT_ID` on the frontend (both are declared in `render.yaml` with
   `sync: false`, so Render shows an empty field for each). Redeploy the frontend.
4. Check: the landing page (signed out) and the account page both show "Sign in with
   Google", and signing in returns you to the app signed in. A 401 "Google sign-in is not configured on this
   server." means the backend variable is missing; an origin error inside Google's
   popup means step 2 is missing the URL you're on.

Signing in with Google uses the same account as an existing email/password sign-up with
that email. See
[doc 23 §8](docs/23_AFFINITY_FIVE_PILLAR_EVIDENCE_STRATEGY_AND_GOOGLE_SSO.md#8-platform-layer-google-sign-in).

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
{"status": "ok", "service": "Affinity API", "database": "postgresql"}
```

`"database": "sqlite"` on a deployed instance means `DATABASE_URL` is missing and data
will not survive the next redeploy. Fix it using the steps above before relying on
accounts.

Then open the frontend URL, submit a sample idea, and confirm the UI shows sources,
market opportunity (including any TAM/SAM/SOM tiers), competitors, confidence,
white-space analysis, SWOT, MVP, and GTM sections. A deep-mode run should also show the
Voice of the Market quotes and Market Viability & Dynamics scorecard (Market & Rivals tab), the
Strategic Wedge Blueprints (Gaps & Exposure tab), and the Delivery Roadmap and Commercial
Economics blocks (Build & Ship tab); quotes and blueprints can legitimately be empty for ideas
with thin source coverage. Send a `/chat` follow-up and verify
the advisor replies. Sign up, open the account menu, and check that **Dashboard**
loads. If your email is in `ADMIN_EMAILS`, check that **Platform health** loads too.

`backend/scripts/render_deployment_check.py` runs a scripted version of these checks
against a live deployment.
