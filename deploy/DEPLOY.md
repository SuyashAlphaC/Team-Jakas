# Deployment

Production split: **Vercel (frontend)** + **AWS App Runner (backend)**.

## Live URLs

| Service | URL |
|---------|-----|
| **Dashboard** | https://context-aware-observability.vercel.app |
| **API** | https://dz8y3uynzx.us-east-1.awsapprunner.com |
| **Health** | https://dz8y3uynzx.us-east-1.awsapprunner.com/health |

## Architecture

```
Browser → Vercel (static React)
       → AWS App Runner (FastAPI + ML + SQLite + SSE replay)
```

The frontend calls the API using `VITE_API_URL` (set at Vercel build time).

## Prerequisites

- Docker
- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws sts get-caller-identity`)
- [Vercel CLI](https://vercel.com/docs/cli) (`vercel login`)
- Trained ML models in `data/models/` (run `python scripts/train_models.py` locally first)

## Deploy backend (AWS App Runner)

From the project root:

```bash
./deploy/aws/deploy.sh
```

This script:

1. Creates an ECR repository (if needed)
2. Builds the Docker image (includes fixtures + ML models)
3. Pushes to ECR
4. Creates/updates an App Runner service (2 vCPU, 4 GB RAM)
5. Writes the service URL to `deploy/aws/.backend-url`

Typical runtime: **8–15 minutes** on first deploy.

### Redeploy after code changes

```bash
./deploy/aws/deploy.sh
```

## Deploy frontend (Vercel)

After the backend is running:

```bash
./deploy/vercel/deploy.sh
```

Or manually:

```bash
cd frontend
printf '%s' 'https://YOUR-APP-RUNNER-URL' | vercel env add VITE_API_URL production
vercel deploy --prod --yes
```

## Environment variables

### App Runner (backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `OBS_USE_ML` | `true` | Enable ML inference |
| `ALLOWED_ORIGINS` | `*` | CORS origins (comma-separated) |

Set `ALLOWED_ORIGINS` to your Vercel URL for tighter CORS:

```bash
# Example after frontend deploy
ALLOWED_ORIGINS=https://context-aware-observability.vercel.app
```

Update via AWS Console → App Runner → Configuration, or re-run `deploy.sh` with env edits.

### Vercel (frontend)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Full backend URL, e.g. `https://dz8y3uynzx.us-east-1.awsapprunner.com` |

## Costs (approximate)

- **Vercel** — Hobby tier is usually sufficient for demos (static frontend).
- **App Runner** — ~$25–50/month for 2 vCPU / 4 GB always-on; scale down or pause when not demoing.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS errors in browser | Set `ALLOWED_ORIGINS=*` on App Runner or add your Vercel domain |
| Empty dashboard / API errors | Confirm `VITE_API_URL` in Vercel → Settings → Environment Variables, then redeploy |
| Slow first request | App Runner cold start + ML load; wait ~30s after idle |
| Replay timeout | Use speed ≤ 12×; App Runner supports SSE but long idle may disconnect |

## Local development (unchanged)

```bash
docker compose up --build
# Dashboard: http://127.0.0.1:5173
```
