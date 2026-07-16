# Context-Aware Autonomous Observability

**Cisco Codathon Track 2 — Platinum Demo**

Context-aware observability platform that decomposes telemetry surges into explained vs unexplained residuals, distinguishes attacks from internal faults during legitimate events, performs RCA with code localization, and proposes graded safe remediation actions.

## Quick Start

```bash
# Option A: Docker (recommended)
docker compose up --build

# Option B: Local dev
cd backend && pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

Open **http://127.0.0.1:5173** and click **Replay Championship Night** (240-minute timeline).

### Grafana — CPU histograms & pie charts per domain

| Service | URL |
|---------|-----|
| **Grafana** | http://localhost:3001 (admin / `observability`) |
| **Prometheus** | http://localhost:9090 |
| **Metrics scrape** | http://localhost:8000/metrics |

Dashboard: **Observability → Domain CPU & Telemetry Utilization**

- **Pie charts** — average domain utilization share + compute sub-metric breakdown
- **Histograms** — CPU/utilization distribution per telemetry entry for each of 7 domains
- **Live time series** — updates during replay

On startup, click **Replay** or call `POST /api/import` to backfill histograms from 240 CSV rows. See [`deploy/grafana/README.md`](deploy/grafana/README.md).

Regenerate the expanded fixture:

```bash
python scripts/generate_dataset.py   # → fixtures/dataset.csv (240 rows)
```

The canonical 6-row judge seed is preserved in `fixtures/dataset_seed.csv`.

Run full verification:

```bash
chmod +x scripts/preflight.sh
./scripts/preflight.sh
```

## Production deployment

| Service | URL |
|---------|-----|
| **Dashboard (Vercel)** | https://context-aware-observability.vercel.app |
| **API (AWS App Runner)** | https://dz8y3uynzx.us-east-1.awsapprunner.com |

Redeploy instructions: [`deploy/DEPLOY.md`](deploy/DEPLOY.md)

```bash
./deploy/aws/deploy.sh      # backend → ECR + App Runner
./deploy/vercel/deploy.sh   # frontend → Vercel (sets VITE_API_URL)
```

## Architecture

```
CSV Seed → Replay Engine → CIS Decomposition → Domain Verdicts
    → Evidence Fusion → RCA Engine → Code Localization → Remediation SM
    → SQLite Audit Ledger + SSE Dashboard
```

### Pipeline Tiers (Phase 1 baseline)

| Tier | Component | Role |
|------|-----------|------|
| 1 | Prophet/STL + CIS | Context-aware baseline forecast |
| 2 | Isolation Forest, LSTM, PELT | Anomaly & change-point detection |
| 3 | AttackClassifier, InternalFaultDetector | Domain analyzers |
| 4 | Evidence Fusion Engine | Cross-domain verdict synthesis |
| 5 | LLM Explainability | Optional narrative (not required for demo) |

### Key Parameters

- Forecast horizon: 15 min
- Residual gate: 3σ
- Suppress confidence: 0.78 (context-explained surge)
- Alert confidence: 0.72
- Act confidence: 0.85

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/import` | Load championship-night CSV (`dataset.csv`, 240 min) |
| POST | `/api/replay/start` | Start deterministic replay |
| GET | `/api/stream` | SSE live event stream |
| GET | `/api/incidents` | RCA incidents |
| GET | `/api/actions` | Remediation actions |
| POST | `/api/actions/{id}/advance` | Approve/execute action |
| GET | `/api/audit` | Hash-chained audit ledger |
| GET | `/metrics` | Prometheus scrape (domain CPU histograms + gauges) |

## Demo Scenarios

**Full timeline** (`fixtures/dataset.csv`, 18:00–21:59 UTC, 240 minutes):

- Pre-game baseline · halftime streaming surge · mini merch drop · retry storm
- **Canonical attack window (20:14–20:19)** — embedded verbatim from `dataset_seed.csv`
- Full-time push · DDoS during peak · BGP/CoPP operational event · streaming degradation · wind-down

**Canonical 6-row seed** (`fixtures/dataset_seed.csv` — used for label accuracy scoring):

1. **Ingress event (20:14)** — network surge explained by `ctx_expected_ingress_multiplier`
2. **Transaction event (20:15)** — checkout surge suppressed (5× context multiplier)
3. **Security alert (20:16–18)** — credential stuffing during merch drop; attack fingerprint
4. **Process alert** — memory leak in identity-svc; code localization to `memory_leak.py`
5. **Recovery (20:19)** — security clears; process still degraded → restart proposed

## Dashboard Guide

Open **http://127.0.0.1:5173**, click **Replay Championship Night**, and use speed **6×** for a walkthrough-friendly pace. Each CSV row is **one minute** of telemetry; all panels update together for the **current replay minute** (the last row processed).

### Per-minute pipeline

```
Telemetry → Residual decomposition → Domain verdicts → Evidence fusion → Incidents → Remediation actions
```

### Header and controls

| Element | What it shows |
|---------|----------------|
| **Label accuracy** | Score against the canonical 6-row seed (`dataset_seed.csv`), not the full 240-row timeline |
| **Dataset line** | Row count, UTC time range, current replay timestamp, and progress (`142/240`) |
| **Replay button** | Runs the full championship-night CSV through the pipeline |
| **Speed slider** | Replay rate (default 6×); attack/combination minutes pause longer for RCA export |
| **Export RCA (selected)** | Markdown root-cause report for the incident tab you have selected |
| **Export Remediation Log** | Full audit trail of all proposed actions across the replay |

### Alert banner (top strip)

A one-glance view of **non-normal domains on the current minute**.

| Badge | Meaning |
|-------|---------|
| `attack` | Security anomaly — credential stuffing or hostile traffic |
| `internal fault` | Internal degradation — memory leak, retry storm, etc. |
| `unexplained` | Residual spike that scheduled context and rules cannot explain |

Each chip shows the **domain**, **σ (sigma)**, and **confidence %**.

### Stats row

| Stat | Meaning |
|------|---------|
| **Incidents** | Times the system opened an RCA incident (attack, internal fault, or both) |
| **Remediation actions** | Total proposed fixes across all incidents |
| **Key (attack/combination)** | High-value incidents — real attack or attack + internal fault together |

### Explained + Unexplained Residual

Per-domain **math view**: did observed telemetry fit the forecast?

| Domain | Monitors |
|--------|----------|
| **transaction** | Request rate, 5xx errors |
| **security** | Auth failure rate |
| **process** | Memory growth, heap, swap |
| **network** | Packet drops, routing churn |
| **compute** | CPU, throttling |
| **streaming** | CDN RPS, stall rate, segment latency |
| **control_plane** | BGP flaps, CoPP drops, HSRP transitions |

Each row shows **residual** (observed minus baseline and context effect) and **σ**. Green **expected** means the surge is explained; purple **unexplained** or orange **internal fault** means something still does not fit.

### Evidence Fusion Engine

The **decision layer** — how ML and rule analyzers combine into one story for this minute.

| Part | Meaning |
|------|---------|
| **Headline** | Overall outcome — e.g. SUPPRESS, Internal Fault, COMBINATION |
| **COMBINATION badge** | Attack and internal fault during the same legitimate event (canonical win scenario) |
| **alert / unexplained chips** | Domains currently flagged |
| **ML evidence chips** | Models that contributed — Prophet, Isolation Forest, PELT, LSTM |
| **Analyzer blocks** | Tier-3 rule corroboration (SecurityAnalyzer, InternalFlowAnalyzer, ResourceHealthAnalyzer) with bullet evidence |

**0 analyzer corroborations** means detection came from the ML/residual pipeline before stricter rule thresholds fired on that minute.

### Domain Verdicts

Same domains as the residual panel, with a **plain-English reason** per domain. Alerts sort to the top. Use this panel to read **why** each domain got its verdict (e.g. “attack cleared — auth failure rate back to baseline”).

### Live Timeline

Chronological **event log** during replay (newest at top).

| Event type | Meaning |
|------------|---------|
| **tick** | Advanced to the next CSV row |
| **fusion** | Fusion engine summary for that minute |
| **unexplained** | Unexplained residual on one or more domains |
| **suppress** | Surge fully explained by context — no incident |
| **incident** | RCA incident opened (exportable) |
| **action** | Remediation action proposed |

### Incidents

Every **RCA package** opened when the pipeline finds attack or internal fault. Each tab is one incident at a timestamp.

- **★** marks key incidents (attack or combination)
- **Export this RCA** — per-incident Markdown report: symptoms, root cause, code file/line, MTTR

On the 240-row replay you will see many incidents from ML noise in early minutes; the **★** tabs are the narrative that matters.

### Remediation Ladder

**Graded response plan** — what the system would do, least invasive first.

| Grade | Typical use |
|-------|-------------|
| **observe** | Correlate before acting (especially on combination incidents) |
| **rate_limit** | WAF/throttle hostile auth traffic |
| **throttle** | Circuit breaker on retry storms (payment-svc) |
| **restart** | Rolling restart for memory leak (identity-svc) |
| **scale fans** | Scale checkout during legitimate merch surge |

Each card shows **target**, **reason**, example **command**, and **Approve** for human-in-the-loop actions. The panel deduplicates similar actions; use **Export Remediation Log** for the full audit trail.

### Recommended demo path (5 minutes)

1. Replay at **6×** — watch the alert banner and fusion panel during **20:14–20:19**
2. Click the **20:16 ★** incident tab
3. **Export this RCA** — show code localization and MTTR
4. Point to **Remediation Ladder** — rate-limit attack + restart leak
5. Mention **100% label accuracy** on the canonical seed in the header

## Deliverables (Platinum checklist)

- [x] **Working demo + dashboard** — live replay with decisions visible step-by-step
- [x] **RCA report per incident** — `GET /api/incidents/{id}/report` (Markdown)
- [x] **Remediation log** — `GET /api/reports/remediation` with graduation ladder + rollback
- [x] **Architecture + README** — `docs/ARCHITECTURE.md`
- [x] **5-min pitch script** — `docs/DEMO_5_MINUTES.md`
- [x] **Label validation** — `GET /api/validation` scores against `dataset_seed.csv` ground truth

## Pipeline (Phase 1 → Phase 2)

```
CSV → CIS Decomposition → Analyzers → Fusion → Causal Graph → RCA + Code/Config → Risk Planner → Verify → Feedback
```

| Tier | Component |
|------|-----------|
| 1 | Prophet/STL + CIS context multipliers |
| 2 | Robust residual + 3σ gate + ML overlay |
| 3 | SecurityAnalyzer · InternalFlowAnalyzer · ResourceHealthAnalyzer |
| 4 | Evidence Fusion Engine |
| 5 | **Causal dependency graph** — symptom → service → root via topology |
| 6 | **Code/config awareness** — file:line, config keys, deploy metadata |
| 7 | **Risk-aware planner** — observe → rate-limit → throttle → restart → isolate → rollback |
| 8 | **Verification + feedback loop** — recovery checks recorded in audit ledger |

### Phase 2 APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /api/incidents/{id}/graph` | Causal dependency graph for an incident |
| `GET /api/deployments` | Service deployment + config snapshots |
| `GET /api/feedback` | Remediation outcome history for planner learning |

Config: `config/topology.yml`, `config/deployments.yml`, `config/remediation-policies.yml`

## Safety

- Localhost-only binding
- Non-root container user
- Allowlisted remediation adapters (no shell/Docker socket)
- Hash-chained audit ledger
- Propose-only patches (auto-apply is stretch)

## Team

Jakas
