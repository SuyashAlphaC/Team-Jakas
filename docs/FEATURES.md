# Aperture — Features

Quick reference for judges and contributors. See also [README.md](../README.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

## Detection & reasoning

- **7 monitoring domains** — transaction, security, process, network, compute, streaming, control_plane
- **Context-aware CIS** — suppress expected surges during merch/ingress events (no alert fatigue)
- **4-tier ML + rules** — Prophet, Isolation Forest, PELT, LSTM + Security/InternalFlow/ResourceHealth analyzers
- **Evidence fusion** — cross-domain verdict synthesis with COMBINATION detection
- **Causal dependency graph** — symptom → service → root via `config/topology.yml`
- **240-min deterministic replay** — championship-night CSV with canonical 6-row seed embedded at 20:14–20:19

## Code localization

- **Stack-trace parser** — Python, Java, Go, Node; multi-frame roots for COMBINATION
- **Fixture traces** — `fixtures/stack_traces.json` keyed by UTC timestamp
- **Static fallback** — regex scan of demo services with unified diff patches
- **Deploy/config awareness** — commit, config key, deploy message from `config/deployments.yml`

Demo services:

| File | Bug |
|------|-----|
| `services/identity-svc/auth_handler.py` | Unlimited ASN rate limit → credential stuffing |
| `services/identity-svc/memory_leak.py` | 64KB heap leak per auth |
| `services/payment-svc/retry.py` | MAX_RETRIES=999 retry storm |

## Remediation

- **Graduated ladder** — observe → rate_limit → throttle → restart → isolate → rollback
- **Risk scoring** — blast radius + confidence gates
- **Human approve** — Remediation tab + `POST /api/actions/{id}/advance`
- **Feedback loop** — outcomes recorded for planner escalation on re-run

## Dashboard (React)

| Tab | Feature |
|-----|---------|
| Home | Hero, metrics strip, demo script |
| Live Monitor | Replay controls, decomposition, verdicts |
| Analysis | Fusion panel, ML chips |
| Incidents & RCA | Causal graph, stack-parsed roots |
| Remediation | Action cards + approve |
| Timeline | SSE event log |
| Grafana | Embedded kiosk dashboard |

- Sticky nav with badge counts
- Animated transitions (hero, cards, alerts)
- Header: label accuracy, dataset range, live replay status

## Grafana & metrics (optional, local Docker)

Open **http://localhost:3001** directly or use the embedded **Grafana** tab in the dashboard:

- **Pie charts** — domain utilization share + compute breakdown
- **Histograms** — per-domain CPU/util distribution (240 rows on import)
- **Live time series** — updates each replay minute
- **Unified alerting** — 6 provisioned rules on model verdict metrics
- **Vertical alert bars** — Prometheus annotations + API push
- **Webhook** — `POST /api/alerting/webhook` logs firing alerts

## Operations

- **Deterministic replay sessions** — DB cleared each run; same counts every time
- **Prometheus** — `GET /metrics` on port 8000
- **Audit ledger** — hash-chained SQLite events
- **RCA / remediation exports** — Markdown reports per incident and full log

## Local URLs

| Service | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| Source | https://github.com/SuyashAlphaC/Team-Jakas |

## Key APIs

```
POST /api/import              # Load CSV + backfill histograms
POST /api/replay/start        # Start replay (resets run data)
GET  /api/stream              # SSE events
GET  /api/incidents/{id}/graph
GET  /api/incidents/{id}/report
POST /api/actions/{id}/advance
GET  /api/validation          # Seed label accuracy
GET  /metrics                 # Prometheus
```

## Docs index

| Doc | Contents |
|-----|----------|
| [README.md](../README.md) | Quick start, tabs, API, demo |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, diagrams, data flow |
| [DEMO_5_MINUTES.md](DEMO_5_MINUTES.md) | Judge pitch script |
| [ML_TRAINING.md](ML_TRAINING.md) | Model training pipeline |
| [deploy/grafana/README.md](../deploy/grafana/README.md) | Dashboards + alerting |
| [deploy/DEPLOY.md](../deploy/DEPLOY.md) | Local Docker deployment |
