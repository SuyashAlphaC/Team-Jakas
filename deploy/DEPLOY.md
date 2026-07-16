# Aperture — Local Deployment

Run the full stack on localhost with Docker Compose.

## Quick start

```bash
cd context-aware-observability
docker compose up --build
```

| Service | URL |
|---------|-----|
| **Dashboard** | http://127.0.0.1:5173 |
| **API** | http://127.0.0.1:8000 |
| **API docs** | http://127.0.0.1:8000/docs |
| **Grafana** | http://localhost:3001 (admin / `observability`) |
| **Prometheus** | http://localhost:9090 |

Open the dashboard → **Home** → **Start 240-min Replay**.

```bash
# Backfill Prometheus/Grafana histograms from CSV
curl -X POST http://localhost:8000/api/import

# Preflight checks
./scripts/preflight.sh

# Stop stack
docker compose down --remove-orphans
```

## Architecture

```
Browser → http://127.0.0.1:5173 (nginx + React)
       → http://127.0.0.1:8000 (FastAPI + ML + SQLite + SSE replay)
       → Prometheus (9090) + Grafana (3001) — metrics & alerting
```

The frontend proxies API calls through nginx in Docker. For local dev without Docker, Vite proxies `/api` to port 8000.

## Local dev (without Docker)

```bash
# Terminal 1 — backend
cd backend && pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Dashboard: http://127.0.0.1:5173

## Optional: metrics stack only

Grafana and Prometheus are included in `docker compose up`. To inspect metrics and alerting separately:

1. Start the stack (or at least `backend`, `prometheus`, `grafana`)
2. `curl -X POST http://localhost:8000/api/import`
3. Open http://localhost:3001 → **Alerting → Alert rules**

See [grafana/README.md](grafana/README.md) for dashboard and alert rule details.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty dashboard | Confirm backend is up: `curl http://127.0.0.1:8000/health` |
| CORS errors | Use the Docker frontend or Vite dev server (same-origin proxy) |
| Replay stuck | Check `docker compose logs backend` for import/replay errors |
| Grafana empty | Run `curl -X POST http://localhost:8000/api/import` then start replay |
