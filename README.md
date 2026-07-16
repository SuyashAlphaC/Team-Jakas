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

## Deliverables (Platinum checklist)

- [x] **Working demo + dashboard** — live replay with decisions visible step-by-step
- [x] **RCA report per incident** — `GET /api/incidents/{id}/report` (Markdown)
- [x] **Remediation log** — `GET /api/reports/remediation` with graduation ladder + rollback
- [x] **Architecture + README** — `docs/ARCHITECTURE.md`
- [x] **5-min pitch script** — `docs/DEMO_5_MINUTES.md`
- [x] **Label validation** — `GET /api/validation` scores against `dataset_seed.csv` ground truth

## Pipeline (Phase 1 → Phase 2)

```
CSV → CIS Decomposition → 3 Analyzers → Evidence Fusion → RCA + Localization → Graded Remediation
```

| Tier | Component |
|------|-----------|
| 1 | Prophet/STL + CIS context multipliers |
| 2 | Robust residual + 3σ gate |
| 3 | SecurityAnalyzer · InternalFlowAnalyzer · ResourceHealthAnalyzer |
| 4 | Evidence Fusion Engine |
| 5 | RCA + source patch proposals + MTTR |

## Safety

- Localhost-only binding
- Non-root container user
- Allowlisted remediation adapters (no shell/Docker socket)
- Hash-chained audit ledger
- Propose-only patches (auto-apply is stretch)

## Team

Jakas — Track 2 Phase 1 Gold → Phase 2 Platinum
