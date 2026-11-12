# Architecture, team ownership and evaluation

## End-to-end workflow

1. **Identity and security:** Register/login; password hashed using random salt and 310,000 PBKDF2-HMAC-SHA256 iterations. Sessions use cryptographic random bearer tokens, with **hashed tokens** stored in the SQL database and a 7-day expiry; server validates token on every private API call. Frontend stores the token in per-tab `sessionStorage` to reduce exposure after a browser session ends. Always use HTTPS in production.
2. **Ingestion:** Fountain screenplay is parsed conservatively, normalization produces scene, character and location IDs. A human can review and edit metadata; the parser does not claim to understand non-speaker cast members.
3. **Persistent SQL schema:** Users → Projects → Scenes / Characters / Locations / SceneCharacter links / ContinuityEvents. Project settings and solver outputs are stored in JSON columns. An audit table records important actions. LoginSessions are a separate table. All project CRUD operations filter by authenticated `owner_id`.
4. **Graph engine:** NetworkX undirected graph with scene, character, location and prop nodes, with typed edges; relationship graph references IDs originating in the real database.
5. **Continuity engine:** Explicit, human-verified ACQUIRE/LOSE/USE/RECOVER prop events checked in screenplay order. Generates warnings rather than alleging automatic screenplay comprehension.
6. **Scheduling:** Candidate placements generated using availability, a single crew and 30-minute slots. Greedy first-fit provides baseline. SciPy HiGHS MILP or optional Google OR-Tools CP-SAT minimize a documented weighted objective under hard scene-once and non-overlap conditions. A feasible result is not always proven optimal.
7. **Replanning:** Actor/location restrictions change; the input signature changes and the prior schedule is marked stale. Export refuses to provide stale CSV/PDF. Replanning compares prior/current assignments.
8. **Analytics:** Fixed seeds, same constraints for baseline and optimizer, metrics include production days, location changes, runtime and moved scenes. Failed baseline cases are not presented as numeric improvements.
9. **Exports:** Authenticated JSON/CSV/PDF bytes generated on demand from persisted user-owned data.

## Owner assignments (five members)

| Member | Engineering ownership | Files to explain in viva |
|---|---|---|
| 1 — Python data engineering | Fountain grammar, entity normalization, SQL persistence | `core/parser.py`, `core/normalizer.py`, `models.py` |
| 2 — Graphs and continuity | NetworkX typed edges; story-order rules | `core/graph_engine.py`, `core/continuity.py` |
| 3 — Operations research | MILP, hard constraints, scheduling, replanning | `core/scheduler.py`, `core/constraints.py`, `core/baseline.py` |
| 4 — Experimental evaluation | Metrics, fixed seeds, baseline comparisons | `core/analytics.py`, `core/synthetic_data.py`, `core/experiments.py` |
| 5 — UI and integration | Static HTML/CSS/JS, FastAPI routes, login and deployment | `docs/`, `app.py`, `project_service.py` |

All five students should run tests and understand the complete pipeline before submission. Contributors should use separate Git branches / pull requests and push their own actual changes. Do not invent contributions in a report.

## Grading / rubric mapping

The shared 8-page SceneGraph team plan requested:

- Fountain import → working; edit and persistence → SQL record modifications.
- Graph → working; manually annotated continuity rules → working.
- Constraint-based scheduling → working; dynamic replanning → working.
- Benchmark comparison → working, with synthetic fixtures and fixed seeds.
- Export → authenticated JSON, CSV and PDF outputs.
- Team ownership → divided across five modules.
- Full public multi-user app → requires an actual hosted Python service and PostgreSQL URL; the ZIP alone is **not** a public site.

The faculty instructions additionally require **at most five members**, a **nonduplicate topic**, individual **GitHub and GCR uploads**, and that all members **understand** the project. Uniqueness and uploads require action by the students. No official marks rubric was provided.

## Test verification

```
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests check authentication, project isolation, Graph and continuity, scheduling, stale outputs, edits, export formats, and static entry points. CI runs with SQLite; PostgreSQL integration still requires a real hosted connection and an independent deployment smoke test. No fabricated production metrics or ML accuracy claims are included.

## Operational boundaries

- Projects are private per account, but passwords cannot be reset by email (no mail service), and self-service account deletion is not implemented.
- Login throttling is in-process and is not a distributed rate limiter; add a WAF or proxy throttle for large public traffic.
- SQL schema is created automatically; subsequent schema updates should be managed by Alembic migrations.
- Online PostgreSQL, TLS, backups, retention, network monitoring and business/legal requirements are supplied by the deploying team/provider.
- One crew, 30-minute slots and a limited day window; daylight labels are metadata, not automatically enforced constraints.
- Current optimizer objective uses location-day grouping as a **proxy**; reported location transitions are a different metric.
- A managed DB may incur usage charges; free-tier availability can change. Preserve independent backups.
