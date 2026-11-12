# SceneGraph AI — Full-Stack Production Intelligence Platform

**Python Programming Experiential Learning · Five-member team · AI & Data Engineering**

A **working, full-stack multi-user web application** for converting Fountain screenplays into verified records, analyzing scene relationships, detecting annotated continuity inconsistencies, optimizing single-crew filming schedules and measuring the results. It has a custom cinematic HTML/CSS/JavaScript frontend; **no Streamlit**.

## Architecture at a glance

```
 GitHub Pages (static docs/ files)            Render Web Service (FastAPI/Python)
 +-----------------------------+             +----------------------------------+
 | index.html / styles.css     | --HTTPS-->   | Authentication + private API     |
 | app.js / config.js          |   Bearer    | Fountain parser & normalization |
 | Auth, interactive graph,    |   token     | Graph / continuity / scheduler  |
 | timeline, metrics, exports  |             | Baseline / benchmarks / PDF     |
 +-----------------------------+             +-----------------+----------------+
                                                           |
                                              private SQL connection
                                                           |
                                           Managed PostgreSQL (e.g. Supabase)
                                           Users, sessions, projects, scenes,
                                           locations, cast, annotations, audit
```

Locally, FastAPI also serves the same frontend and stores records in an SQLite file. In a hosted deployment, set `DATABASE_URL` to a managed **PostgreSQL** database so records survive backend restarts. The frontend itself never receives the database password or database connection string.

## Features that actually work

- Email/password signup, sign-in, sign-out, password hashing (PBKDF2-SHA256), revocable expiring sessions, per-account project isolation.
- Real SQL storage through SQLAlchemy for users, projects, locations, actors, scene/cast relationships, annotations, scheduling settings, schedule results and audit events.
- Import `.fountain` or `.txt` UTF-8 screenplay; parsing and structured validation; editable cast, scene metadata and durations.
- Create and switch between projects; edit records; delete projects (with confirmation).
- Interactive source-linked scene knowledge graph; manually annotated prop continuity checks in **story order**.
- Feasible single-crew schedule with actor/location constraints and 30-minute time slots; priority-aware optimization via SciPy MILP, optional Google OR-Tools CP-SAT (install separately), transparent fallback behavior.
- Change actor/location availability and replan; metrics and solver status; stale output invalidation.
- Synthetic benchmark experiments with fixed seeds; same hard constraints for greedy and optimized methods.
- Authenticated JSON, CSV and PDF exports based on current persisted project data.
- Integration tests (login, data isolation, import, graph, schedule, replanning, storage and export) plus GitHub Actions test workflow.

**Important technical honesty:** The parser is rule-based; continuity warnings require human annotations. We do *not* claim generic story understanding or unsupported ML prediction accuracy. A scheduled scene is a production planning estimate and not a safety guarantee.

## First run on Windows (no public deployment needed)

1. Install Python 3.11+ and extract the complete ZIP.
2. Open the `SceneGraph_Production` folder in VS Code → Terminal → New Terminal.
3. Run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

4. Open **http://127.0.0.1:8000/**. Click **Create an account**, use your own email address and a strong password, and sign in.
5. A 12-scene **sample production** appears for each new account. The database is persisted in `scenegraph.db` (not tracked by Git).
6. Go to **Production planner → Generate optimized schedule**. Then block an actor on a scheduled day and replan.

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

**If your browser says "site can't be reached":** check that the terminal is still running, you are in the project folder, you used port 8000, and dependencies installed in the **same** Python environment. `http://127.0.0.1:8000` only works on the same computer.

## Publish a working public website with GitHub Pages

> **GitHub Pages alone cannot run Python or a database.** It publishes your static frontend, while Render (or another Python hosting service) runs FastAPI and PostgreSQL persists the data. See [DEPLOY_GITHUB_PAGES.md](documentation/DEPLOY_GITHUB_PAGES.md) for the full step-by-step setup.

**Deployment summary:**

1. Push the entire project (including hidden `.github/` files and `docs/`) to a GitHub repository. Never commit `.env`, `scenegraph.db`, or any password.
2. Create a persistent managed PostgreSQL database (Supabase **Session Pooler** works with IPv4-only hosting). Copy the connection URI privately.
3. Deploy a **Python Web Service** on Render using this repo. Set `DATABASE_URL` privately and `CORS_ORIGINS=https://YOUR_USERNAME.github.io`. Start with `uvicorn app:app --host 0.0.0.0 --port $PORT`.
4. Check that `https://YOUR-API.onrender.com/api/health` reports `ok: true`.
5. Edit `docs/config.js` to set `window.SCENEGRAPH_API_BASE = "https://YOUR-API.onrender.com";` (an HTTPS URL, **not** a secret).
6. GitHub repository → Settings → Pages → Deploy from a branch → `main` → `/docs` → Save. Visit the generated GitHub Pages URL and register an account.
7. Test from **a second browser**. With the backend URL set in `config.js`, friends can open the same public link. Their productions are saved to the managed database under separate accounts.

**Status of this ZIP:** the full application is built and can be run locally. **No GitHub repository, public backend, DNS name, or online database has been provisioned for you**—you still have to deploy it with your accounts, URLs, and credentials.

## Repository layout

```
SceneGraph_Production/
├─ app.py                        FastAPI routes + authentication + API downloads
├─ models.py                     SQLAlchemy SQL schema (SQLite/PostgreSQL)
├─ project_service.py            Owner-scoped CRUD + integration/orchestration
├─ core/                         Parser, graph, continuity, MILP scheduling, metrics
├─ docs/                         GitHub Pages static website (index, CSS, JS, config)
├─ data/                         Sample original screenplay and continuity fixtures
├─ tests/                        Automated tests + optional browser smoke script
├─ documentation/                Deployment, architecture, algorithms, team work
├─ .github/workflows/tests.yml   GitHub Actions CI tests
├─ requirements.txt              Python runtime packages
├─ requirements-dev.txt          Runtime + tests
├─ render.yaml                   Render web-service blueprint
└─ .env.example                  Example environment variables (NOT secrets)
```

## Verify the backend

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

FastAPI publishes an interactive REST API reference at `http://127.0.0.1:8000/docs` for developers. The application frontend is at `/`; the repository's **filesystem** folder `docs/` contains files for GitHub Pages.

## Five-member role ownership

| Member | Role | Working source |
|---|---|---|
| 1 | Data engineering and Fountain parser | `core/parser.py`, `core/normalizer.py`, `models.py` |
| 2 | Graph modeling and continuity analysis | `core/graph_engine.py`, `core/continuity.py` |
| 3 | Scheduling and optimization | `core/scheduler.py`, `core/constraints.py`, `core/baseline.py` |
| 4 | Analytics and reproducibility | `core/analytics.py`, `core/experiments.py`, `core/synthetic_data.py` |
| 5 | UI, API, integration, deployment | `docs/`, `app.py`, `project_service.py`, `tests/` |

Every student should understand the full flow and submit the complete repo link and files to GitHub/GCR as their faculty requires. Assign actual team identities in the submission report; the code includes no fabricated authorship or contribution history.

## Known boundaries before real public use

This is a deployable educational application, **not an audited enterprise SaaS service**. It needs a configured managed PostgreSQL service, HTTPS (provided by the host), backups, migrations for future schema changes, stronger distributed rate limiting, password recovery/email verification, and production monitoring for broader public use. The temporary free databases of some hosts have expiry/data-retention limits. The development ZIP does **not** include an online database, credentials, or any invented live URL. Preserve secrets only in hosting environment variables.

Fountain script format: https://fountain.io/syntax/ · GitHub Pages docs: https://docs.github.com/en/pages · Render FastAPI: https://render.com/docs/deploy-fastapi · Supabase Postgres connections: https://supabase.com/docs/guides/database/connecting-to-postgres
#   S c e n e G r a p h - A I  
 