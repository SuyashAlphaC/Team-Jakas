# Aperture

**Context-aware autonomous observability · Cisco Codathon Track 2 Platinum · Team Jakas**

**Aperture** decomposes telemetry surges into explained vs unexplained residuals, distinguishes attacks from internal faults during legitimate events, performs causal RCA with **stack-trace code localization**, and proposes **risk-aware graded remediation** — with a tabbed live dashboard on localhost.

## What's new (current feature set)

| Area | Highlights |
|------|------------|
| **Tabbed dashboard** | Home, Live Monitor, Analysis, Incidents & RCA, Remediation, Timeline, **Grafana** — sticky nav, animated hero, header/footer |
| **Grafana integration** | Embedded dashboard tab + local stack (histograms, pie charts, live gauges) on **http://localhost:3001** |
| **Stack-trace localization** | Parses Python / Java / Go / Node stack traces → real `file:line` roots with diff patches; falls back to static map |
| **Phase 2 reasoning** | Causal dependency graph, deploy/config awareness, risk-scored remediation planner, verification feedback loop |
| **Deterministic replay** | Each replay clears run-scoped DB state — same incident/action counts every run |
| **Prometheus + Grafana** | Domain CPU histograms, alert gauges, fusion/combination flags — optional at http://localhost:3001 |
| **Grafana alerting** | Model predictions fire provisioned alert rules when running the local Docker stack |

## Quick Start

```bash
# Docker (recommended — backend + frontend + Prometheus + Grafana)
docker compose up --build

# Stop stack
docker compose down --remove-orphans
```

| Service | URL |
|---------|-----|
| **Dashboard** | http://127.0.0.1:5173 |
| **API** | http://127.0.0.1:8000 |
| **Grafana** | http://localhost:3001 (admin / `observability`) |
| **Prometheus** | http://localhost:9090 |

Open the dashboard → **Home** → **Start 240-min Replay**, or use **Live Monitor**.

```bash
# Backfill Grafana histograms from CSV
curl -X POST http://localhost:8000/api/import

# Preflight checks
./scripts/preflight.sh
```

### Local dev (without Docker)

```bash
cd backend && pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Full deployment notes: [`deploy/DEPLOY.md`](deploy/DEPLOY.md)

## Architecture

```
CSV → Replay → CIS + ML → Analyzers → Fusion → Causal Graph
  → Stack-trace / static localization → Risk planner → Verify → Feedback
  → SQLite audit + SSE → Tabbed dashboard
```

### Pipeline tiers

| Tier | Component | Role |
|------|-----------|------|
| 1 | Prophet/STL + CIS | Context-aware baseline forecast |
| 2 | Isolation Forest, LSTM, PELT | Anomaly & change-point detection |
| 3 | Security / InternalFlow / ResourceHealth analyzers | Domain corroboration |
| 4 | Evidence Fusion Engine | Cross-domain verdict synthesis |
| 5 | **Causal graph** | Symptom → service → root via topology |
| 6 | **Stack-trace parser + localization** | `file:line` from production traces or fixture map |
| 7 | **Risk-aware planner** | observe → rate-limit → throttle → restart → rollback |
| 8 | **Verification + feedback** | Post-action outcomes feed planner learning |

Details: [`docs/FEATURES.md`](docs/FEATURES.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Grafana: [`deploy/grafana/README.md`](deploy/grafana/README.md)

## Dashboard tabs

| Tab | Purpose |
|-----|---------|
| **Home** | Hero, feature cards, metrics strip, 5-min demo script |
| **Live Monitor** | Replay controls, alert banner, residual decomposition, domain verdicts |
| **Analysis** | Evidence fusion panel, ML sources, analyzer corroboration |
| **Incidents & RCA** | Incident tabs, causal graph, **stack-parsed** file:line roots, MTTR |
| **Remediation** | Graded action ladder with **Approve** (human-in-the-loop) |
| **Timeline** | Scrollable SSE event log (fusion, incident, action, suppress) |
| **Grafana** | Embedded kiosk dashboard — histograms, pies, alert vertical bars |

### Recommended demo path (5 min)

1. **Home** → Start replay at **6×**
2. **Live Monitor** — watch suppress at 20:15, alerts at 20:16
3. **Incidents & RCA** — open ★ COMBINATION tab; show **Parsed from stack trace** chip + `retry.py:14`, `memory_leak.py:9`
4. **Remediation** — approve rate-limit / restart action
5. **Grafana** tab — live gauges + dotted alert markers at 20:16; **Alerting → Alert rules** for firing state
6. Header — **100% label accuracy** on canonical seed

Full script: [`docs/DEMO_5_MINUTES.md`](docs/DEMO_5_MINUTES.md)

## Code localization

Two-tier localization in `backend/app/localization/`:

1. **Stack-trace parser** (preferred) — parses traces from `fixtures/stack_traces.json`, CSV `stack_trace` column, or embedded evidence; supports Python, Java, Go, Node; emits multi-frame roots for COMBINATION scenarios
2. **Static map fallback** — regex scan of `services/identity-svc/auth_handler.py`, `memory_leak.py`, `payment-svc/retry.py` with curated diff patches

Demo traces are attached to championship window timestamps **20:16–20:19 UTC**.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/import` | Load CSV + backfill Prometheus histograms |
| POST | `/api/replay/start` | Start deterministic replay (clears prior run data) |
| GET | `/api/stream` | SSE live event stream |
| GET | `/api/incidents` | RCA incidents |
| GET | `/api/incidents/{id}/graph` | Causal dependency graph |
| GET | `/api/incidents/{id}/report` | Markdown RCA export |
| GET | `/api/actions` | Remediation actions |
| POST | `/api/actions/{id}/advance` | Approve / advance action state |
| GET | `/api/deployments` | Deploy + config snapshots |
| GET | `/api/feedback` | Remediation outcome history |
| GET | `/api/validation` | Label accuracy vs `dataset_seed.csv` |
| GET | `/api/reports/remediation` | Full remediation audit log |
| POST | `/api/alerting/webhook` | Grafana alert notifications (Docker) |
| GET | `/metrics` | Prometheus scrape (CPU + alert metrics) |

## Demo scenarios

**Full timeline** (`fixtures/dataset.csv`, 240 min, 18:00–21:59 UTC):

- Pre-game · halftime streaming · merch drop · retry storm
- **Canonical attack window (20:14–20:19)** — from `dataset_seed.csv`
- Full-time push · DDoS · BGP/CoPP event · wind-down

**6-row seed** (`fixtures/dataset_seed.csv`) — used for label accuracy scoring:

1. Ingress surge explained (20:14)
2. Transaction surge suppressed (20:15)
3. Security attack + process internal fault (20:16–18) — stack traces in `fixtures/stack_traces.json`
4. Recovery (20:19)

## Deliverables (Platinum checklist)

- [x] Working demo + **tabbed dashboard** with live replay
- [x] RCA report per incident with **stack-trace localization**
- [x] Remediation log with graduation ladder + rollback
- [x] **Grafana** histograms, pies, **unified alerting**, alert annotations (local Docker)
- [x] Architecture + README + 5-min pitch script
- [x] Label validation API (100% on canonical seed)
- [x] Phase 2: causal graph, config/deploy awareness, risk planner, feedback loop

## Safety

- Localhost-only Docker binding
- Non-root container user
- Allowlisted remediation adapters (propose-only patches)
- Hash-chained audit ledger
- Human approval for high-blast-radius actions

## Team

**Jakas** · [GitHub](https://github.com/SuyashAlphaC/Team-Jakas)
