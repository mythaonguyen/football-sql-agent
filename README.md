# PitchQuery — Football SQL Agent

AI-powered text-to-SQL app for exploring professional football data.

**Live demo (frontend):** [mythaonguyen.github.io/football-sql-agent](https://mythaonguyen.github.io/football-sql-agent)

## Architecture

| Layer | Host |
|-------|------|
| **Frontend** | GitHub Pages (`docs/`) |
| **API** | Render / Railway / local (`text-to-sql copy/`) |
| **Database** | Supabase (PostgreSQL) |

GitHub Pages serves static HTML/CSS/JS only. The FastAPI backend must run on a separate host.

## Local development

```bash
cd "text-to-sql copy"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Add DATABASE_URL and HUGGINGFACEHUB_API_TOKEN to .env
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## GitHub Pages deployment

1. **Enable Pages** in repo Settings → Pages → Source: **GitHub Actions**
2. Push to `main` or `demo_PitchQuery` — workflow `.github/workflows/pages.yml` deploys `docs/`
3. Site URL: `https://mythaonguyen.github.io/football-sql-agent/`

## Backend deployment (required for live queries)

Deploy `text-to-sql copy/` to [Render](https://render.com) using `render.yaml`, or:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Set environment variables:
- `DATABASE_URL` — Supabase PostgreSQL connection string
- `HUGGINGFACEHUB_API_TOKEN`
- `CORS_ORIGINS` — `https://mythaonguyen.github.io`

Then set your API URL in `docs/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://your-api.onrender.com",
};
```

Commit and push — the Pages workflow will redeploy.

## Project structure

```
text-to-sql copy/   # FastAPI app + Supabase (main app)
text-to-sql/        # Original MySQL version
docs/               # GitHub Pages static site
```

See [text-to-sql copy/README.md](text-to-sql%20copy/README.md) for full app documentation.
