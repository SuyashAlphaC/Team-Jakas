# Aperture — Architecture

## Overview

Platinum demo: **Phase 1 detection** + **Phase 2 reasoning** + **local Docker stack** + **tabbed dashboard**.

```
CSV + stack_traces.json
  → Replay Engine (session reset each run)
  → CIS Decomposition + ML overlay
  → Tier-3 Analyzers
  → Evidence Fusion
  → Causal Graph
  → Stack-trace parser → Code/config localization
  → Risk-aware Remediation Planner
  → Verification + Feedback loop
  → SQLite audit + SSE
  → React tabbed UI + optional Grafana metrics/alerts (localhost:3001)
```

## System diagram

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│ CSV + Stack │───▶│ Replay Engine│───▶│ CIS + ML Layer  │
│   Traces    │    │ (reset/run)  │    └────────┬────────┘
└─────────────┘    └──────────────┘             │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
             ┌─────────────┐            ┌─────────────┐              ┌─────────────┐
             │ Transaction │            │  Security   │              │   Process   │
             │  Verdict    │            │  Verdict    │              │   Verdict   │
             └──────┬──────┘            └──────┬──────┘              └──────┬──────┘
                    └──────────────────────────┼──────────────────────────────┘
                                               ▼
                                      ┌─────────────────┐
                                      │ Evidence Fusion │
                                      └────────┬────────┘
                                               ▼
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
           ┌────────────────┐        ┌─────────────────┐        ┌─────────────────┐
           │ Causal Graph   │        │ Stack-trace     │        │ Prometheus      │
           │ (topology)     │        │ Localization    │        │ alert metrics   │
           └───────┬────────┘        └────────┬────────┘        └────────┬────────┘
                   └──────────────────────────┼──────────────────────────┘
                                              ▼
                                     ┌─────────────────┐
                                     │ Risk Planner +  │
                                     │ Feedback loop   │
                                     └────────┬────────┘
                                              ▼
                                     ┌─────────────────┐
                                     │ SQLite + Audit  │
                                     │ SSE + Dashboard │
                                     └─────────────────┘
```

## Phase 2 modules

| Module | Path | Role |
|--------|------|------|
| Causal graph | `backend/app/causal/graph.py` | Symptom → service → root via topology + propagation rules |
| Config awareness | `backend/app/config/awareness.py` | Roots enriched with deploy metadata + config snapshots |
| Stack-trace parser | `backend/app/localization/stacktrace.py` | Python / Java / Go / Node frame extraction |
| Localization | `backend/app/localization/scanner.py` | Stack-first roots + static map fallback + diff patches |
| Stack trace fixtures | `fixtures/stack_traces.json` | Timestamp-keyed traces for demo window |
| Risk planner | `backend/app/remediation/risk_planner.py` | Blast-radius scored action ladder |
| Feedback loop | `backend/app/remediation/feedback.py` | Post-action verification + outcome recording |
| Grafana annotations | `backend/app/metrics/grafana_annotations.py` | Push vertical-line markers during replay |
| Alert metrics | `backend/app/metrics/exporter.py` | Prometheus gauges/counters for Grafana alerting |

Config files: `config/topology.yml`, `config/deployments.yml`, `config/remediation-policies.yml`

## Ingestion (`backend/app/ingestion/`)

- **csv_adapter.py** — schema sniffing, `ctx_expected_*` context columns, `target_*` labels, optional `stack_trace` column
- **stack_traces.py** — merges `fixtures/stack_traces.json` into observation labels by timestamp

## Analysis (`backend/app/analysis/`)

- **decomposition.py** — CIS: `expected = baseline + context_effect`; 3σ gate; attack/internal fingerprints
- **analyzers.py** — SecurityAnalyzer, InternalFlowAnalyzer, ResourceHealthAnalyzer
- **fusion.py** — cross-domain synthesis, COMBINATION detection, warm-up suppression

## ML (`backend/app/ml/`)

- Prophet + CIS baselines, Isolation Forest, PELT change-points, LSTM auth autoencoder
- Controlled by `OBS_USE_ML=true` (default in Docker)

## Localization flow

1. Incident opens on `attack` or `internal_fault` verdict
2. `rank_roots()` checks `obs.labels["stack_trace"]` and evidence for embedded traces
3. **Parser** extracts frames under `services/` → `RootCauseCandidate` per file with `file:line`, function, diff patch
4. **Fallback** — `LOCALIZATION_MAP` regex-scans `services/*.py` when no trace available
5. **Deploy enrich** — `enrich_root_with_deployment()` attaches commit, config key values from `config/deployments.yml`

Supported trace formats:

| Language | Example frame |
|----------|---------------|
| Python | `File "services/payment-svc/retry.py", line 14, in process_payment` |
| Java | `at com.foo.Bar.method(Retry.java:14)` |
| Go | `services/identity-svc/memory_leak.go:9 +0x4a` |
| Node | `at fn (/app/services/payment-svc/retry.js:14:11)` |

## RCA (`backend/app/rca/`)

- Symptom collapse, ranked roots (multi-frame from stack on COMBINATION)
- Causal graph nodes/edges + reasoning chain
- Combination synthetic root when attack + internal_fault concurrent
- Deterministic incident IDs: `inc-{source_row:04d}`

## Remediation (`backend/app/remediation/`)

- Grades: observe → rate_limit → throttle → restart → isolate → rollback
- Confidence gates: 0.72 alert · 0.78 suppress · 0.85 act · 0.90 human approval
- Deterministic action IDs per incident/grade/target
- `POST /api/actions/{id}/advance` — approve advances PROPOSED → EXECUTING → VERIFYING → SUCCEEDED

## Storage (`backend/app/storage/`)

- SQLite WAL, hash-chained audit ledger
- **`reset_for_replay()`** — clears incidents, actions, feedback, replay events at each replay start (deterministic counts)

## Metrics & Grafana (`deploy/grafana/`)

| Component | Role |
|-----------|------|
| Prometheus | Scrapes `/metrics` every 5s |
| Histograms | `observability_domain_cpu_usage_pct` — backfilled on `/api/import` |
| Live gauges | `observability_domain_cpu_current_pct` — updated each replay minute |
| Alert gauges | `observability_domain_alert_active{domain,verdict}` — fusion-driven |
| Alert rules | Provisioned in `deploy/grafana/provisioning/alerting/rules.yml` |
| Annotations | Dashboard JSON layers + backend API push for dotted vertical bars |

Grafana host port **3001** (container 3000). Embedded in the **Grafana** dashboard tab via iframe.

## Frontend (`frontend/src/`)

Modular React 19 + TypeScript + Vite:

| Module | Role |
|--------|------|
| `hooks/useObservability.ts` | State, SSE replay, API refresh, approve flow |
| `components/Layout.tsx` | Header, sticky nav, footer |
| `pages/HomePage.tsx` | Landing hero + demo script |
| `pages/MonitorPage.tsx` | Live decomposition + verdicts |
| `pages/AnalysisPage.tsx` | Fusion panel |
| `pages/IncidentsPage.tsx` | RCA + causal graph + stack-parsed roots |
| `pages/RemediationPage.tsx` | Action ladder + approve |
| `pages/TimelinePage.tsx` | Event stream |
| `pages/GrafanaPage.tsx` | Embedded Grafana kiosk iframe |

## Deployment topology

**Docker Compose** (local full stack — the only supported deployment):

| Service | Port | Notes |
|---------|------|-------|
| backend | 8000 | FastAPI + metrics |
| frontend | 5173 | nginx → API proxy |
| prometheus | 9090 | Metrics scrape |
| grafana | 3001 | Dashboards + alerting |

Run: `docker compose up --build` — see [deploy/DEPLOY.md](../deploy/DEPLOY.md).

## Determinism

- Each replay calls `storage.reset_for_replay()` — no cross-run incident accumulation
- Replay uses `record_live_tick()` for gauges (histograms not double-counted per run)
- Canonical seed scoring via `GET /api/validation` remains independent of full 240-row noise

## API summary

See [README.md](../README.md#api-endpoints) for the full endpoint table including Phase 2 and alerting routes.
