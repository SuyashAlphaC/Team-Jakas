# Architecture

## Overview

The Platinum demo implements the Phase 1 Gold design as a runnable local stack:

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  CSV Seed   │───▶│ Replay Engine│───▶│ CIS Decomposer  │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
             ┌─────────────┐            ┌─────────────┐              ┌─────────────┐
             │ Transaction │            │  Security   │              │   Process   │
             │  Verdict    │            │  Verdict    │              │   Verdict   │
             └──────┬──────┘            └──────┬──────┘              └──────┬──────┘
                    └────────────────────────────┼────────────────────────────┘
                                                 ▼
                                        ┌─────────────────┐
                                        │ Evidence Fusion │
                                        └────────┬────────┘
                                                 ▼
                                        ┌─────────────────┐
                                        │   RCA Engine    │
                                        │ + Localization  │
                                        └────────┬────────┘
                                                 ▼
                                        ┌─────────────────┐
                                        │ Remediation SM  │
                                        │ (graded actions)│
                                        └────────┬────────┘
                                                 ▼
                                        ┌─────────────────┐
                                        │ SQLite + Audit  │
                                        │ SSE Dashboard   │
                                        └─────────────────┘
```

## Components

### Ingestion (`backend/app/ingestion/`)
- CSV adapter with schema sniffing
- Context column detection (`ctx_expected_*`)
- Label passthrough (`target_*`)

### Analysis (`backend/app/analysis/`)
- **decomposition.py** — CIS context multipliers: `expected = baseline + context_effect`
- **analyzers.py** — Tier-3 parallel analyzers (Phase 1 Figure 1):
  - `SecurityAnalyzer` — auth failure rate, no identity context, residual during surge
  - `InternalFlowAnalyzer` — retry storm (suppressed during merch event)
  - `ResourceHealthAnalyzer` — heap growth / PELT-like monotonic leak
- **fusion.py** — Evidence Fusion Engine merges analyzer signals + post-calibration (event-end recovery, attack cleared)

### Localization (`backend/app/localization/`)
- Reads real source files under `services/` and emits line-numbered diff patches
- Maps to `auth_handler.py`, `memory_leak.py`, `retry.py` with config keys and commits

### Reports (`backend/app/reports/`)
- Jinja2 RCA markdown per incident (Platinum deliverable #2)
- Remediation log with graduation ladder (deliverable #3)

### RCA (`backend/app/rca/`)
- Symptom storm collapse to ranked root candidates
- Service topology from `config/topology.yml`
- Code localization fixtures mapping to `services/payment-svc/retry.py` and `services/identity-svc/memory_leak.py`
- Combination root cause when attack + internal fault concurrent

### Remediation (`backend/app/remediation/`)
- Graded action ladder: observe → rate_limit → throttle → restart → isolate
- Confidence gates: 0.72 alert, 0.78 suppress, 0.85 act, 0.90 human approval
- Human-in-loop for high-blast-radius actions
- Rollback commands stored per action

### Storage (`backend/app/storage/`)
- SQLite WAL mode
- Hash-chained audit ledger (prev_hash → entry_hash)
- Incident and action persistence

### Frontend (`frontend/`)
- React 19 + TypeScript + Vite
- SSE timeline for live replay
- Domain verdict badges, RCA panel, remediation approval UI
- MTTR display (detect + RCA latency)

## Deployment

Docker Compose with two services:
- `backend`: FastAPI on 127.0.0.1:8000
- `frontend`: nginx serving React build, proxying /api to backend

## Deterministic Ladder

For the 3–7 row secret seed, Prophet/LSTM are skipped in favor of deterministic robust statistics. This ensures reproducible demo behavior across machines without GPU or large training windows.
