# SceneGraph AI — Publish with GitHub Pages + Python backend + PostgreSQL

## Why three parts?

GitHub Pages hosts only static HTML, CSS and JavaScript. A working multi-user app must also have a Python server and persistent database. Our architecture uses the **same repository** for both frontend source (`docs/`) and backend source (`app.py`, `models.py`, `core/`), deployed on different hosting services.

```
Your browser (HTTPS GitHub Pages)
      │  calls /api/* using HTTPS
      ▼
FastAPI Python backend (Render web service)
      │  DATABASE_URL (never public)
      ▼
PostgreSQL (Supabase Session Pooler or managed Postgres)
```

## 1. Upload the repository

1. Create a GitHub repository called **SceneGraph-AI** (or any name).
2. Upload the contents of this extracted folder, including `docs`, `.github`, `core`, Python scripts, documentation, and requirements.
3. **Do not commit** `.env`, `scenegraph.db`, session tokens, production passwords or database credentials.
4. Recommended `git` commands (from the extracted project folder):

```bash
git init
git add .
git commit -m "SceneGraph AI full-stack application"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/SceneGraph-AI.git
git push -u origin main
```

You must create the remote repository in GitHub first; replace `YOUR_USERNAME` with your own username.

## 2. Create managed PostgreSQL

- Supabase → New Project → choose region and a strong database password.
- Click **Connect** → **Session Pooler**. This is the safer choice for hosting providers limited to IPv4. Copy the complete PostgreSQL URI. Do not guess the host; copy it exactly from the dashboard.
- Keep the connection string **private** and store it only in the backend hosting service's `DATABASE_URL` environment variable. Never paste it in `docs/config.js`.
- For Supabase external connections, session pooler normally uses port 5432. Avoid the transaction pooler on 6543 for this straightforward long-running SQLAlchemy application unless you configure its special restrictions.
- Alternatively choose a paid managed PostgreSQL provider of your choice. Some free PostgreSQL plans, including Render's free PostgreSQL, expire after a limited period. Keep backups of real work.

## 3. Deploy the backend to Render

- Create a new **Web Service** from the same GitHub repository.
- Language/runtime: Python 3.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Add these private environment settings:

| Key | Value |
|---|---|
| `DATABASE_URL` | The full PostgreSQL connection URI from step 2 |
| `CORS_ORIGINS` | `https://YOUR_USERNAME.github.io` |

Do **not** put `/SceneGraph-AI/` in `CORS_ORIGINS`. CORS accepts only the website **origin** (scheme + hostname + optional port), not a path. Do not use `*` in production.

- Deploy and copy your new backend URL. Open `https://YOUR_SERVICE.onrender.com/api/health`: it must say `"ok":true`. If the server fails to boot, check Render Logs and verify the database URI and Python packages.
- The backend initializes its SQL tables on startup. Database records persist in PostgreSQL instead of a volatile hosting filesystem.

## 4. Connect the frontend

Edit **`docs/config.js`** in your repository:

```javascript
window.SCENEGRAPH_API_BASE = "https://YOUR_SERVICE.onrender.com";
```

This is a **public API base address** and is fine to put in GitHub. It is not a database URI or password.

If you leave it blank, visitors on GitHub Pages will see a connection setup field, but that choice is saved **only in their own browser**, so it won't make your shared link work for everyone. For a real public link, edit `config.js` and commit the change.

## 5. Turn on GitHub Pages

- GitHub repository → **Settings → Pages**.
- **Source:** Deploy from a branch.
- **Branch:** `main`; **Folder:** `/docs`.
- Save. The link will look like `https://YOUR_USERNAME.github.io/SceneGraph-AI/`.
- Open the site. Click Create an account → sign in → import an original screenplay → generate a schedule.
- Have a friend open the same public URL in another browser to verify that `config.js` is correctly configured for everyone.

If the frontend loads but login fails with a CORS error, check `CORS_ORIGINS` on Render and redeploy. If you see a 404 for `styles.css`, confirm Pages publishes from `/docs` and that the files are present.

## 6. Final independent verification

- [ ] `https://YOUR_SERVICE.onrender.com/api/health` responds successfully.
- [ ] GitHub Pages home loads with fonts/styles/JS (no broken asset paths).
- [ ] A new user can register with a strong password and log in again.
- [ ] New accounts receive their own sample project; users cannot see each other's projects.
- [ ] Import/persist a real screenplay and refresh the page to confirm it is still saved.
- [ ] Edit cast and locations, generate a schedule, change availability and replan.
- [ ] Graph and continuity pages show correct data.
- [ ] JSON/CSV/PDF exports download and outdated CSV/PDF are blocked.
- [ ] Second browser/teammate can access the exact same shared site link.
- [ ] All five students can explain their module and submit required files to GitHub/GCR.

## Troubleshooting

| Symptom | Likely cause / action |
|---|---|
| `net::ERR_CONNECTION_REFUSED` on localhost | Python server is not running |
| GitHub Pages loads but 'API connection' prompt shows | `docs/config.js` still has an empty URL |
| Failed to fetch / CORS error | `CORS_ORIGINS` needs your exact GitHub Pages origin; backend may be asleep |
| Database connection error on Render | Incorrect `DATABASE_URL`, password encoding or wrong Supabase connection mode |
| Changes disappear after Render restarts | Using local SQLite instead of persistent managed PostgreSQL |
| Logged out after a new browser session | Sessions are stored in `sessionStorage`; sign in again (intentional) |
| CSV export unavailable | Generate or regenerate a feasible schedule |
| Browser unable to reach API over HTTP | GitHub Pages uses HTTPS; backend must also use HTTPS |

Official references: https://docs.github.com/en/pages ; https://render.com/docs/deploy-fastapi ; https://supabase.com/docs/guides/database/connecting-to-postgres
