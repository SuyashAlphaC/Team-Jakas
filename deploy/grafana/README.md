# Grafana — Domain CPU & Telemetry Dashboards

Pre-provisioned dashboard with **histograms** and **pie charts** per monitoring domain.

## Quick start

```bash
docker compose up --build
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3001 | admin / `observability` (anonymous view enabled) |
| Prometheus | http://localhost:9090 | — |
| Metrics | http://localhost:8000/metrics | — |

## Load telemetry into metrics

Histograms populate when CSV is imported (240 rows backfilled):

```bash
curl -X POST http://localhost:8000/api/import
```

During replay, gauges update live each minute. **Dotted vertical bars** on the live time-series panel mark each model alert (attack, internal_fault, unexplained, combination, incident).

Annotations come from:
1. **Prometheus queries** on `observability_model_alerts_fired_total` (provisioned in dashboard JSON)
2. **Grafana API** pushes from the backend during replay (`app/metrics/grafana_annotations.py`)
3. **Alert rule links** to panel 9 (Grafana Alerts annotation layer)

## Grafana alerting (model predictions)

When the fusion engine predicts **attack**, **internal_fault**, **unexplained**, or **combination**, metrics are exported to Prometheus and Grafana unified alerting fires automatically.

| Grafana rule | Triggers when |
|--------------|---------------|
| Model — Security Attack Detected | `observability_domain_alert_active{verdict="attack"} == 1` |
| Model — Internal Fault Detected | `verdict="internal_fault"` active |
| Model — Unexplained Residual | `verdict="unexplained"` active |
| Model — COMBINATION | `observability_fusion_combination == 1` |
| Model — Incident Opened | `increase(observability_incidents_created_total[2m]) > 0` |
| Model — Any Alert Active | `observability_fusion_alert_active == 1` |

**View firing alerts:** Grafana → **Alerting** → **Alert rules** (folder: Observability)

**Webhook:** Alerts also POST to `POST /api/alerting/webhook` on the backend (logged in container stdout).

Rules provision from `deploy/grafana/provisioning/alerting/rules.yml` on `docker compose up`.

## Dashboard: Domain CPU & Telemetry Utilization

**Path:** Observability folder → `Domain CPU & Telemetry Utilization`

| Panel | Type | What it shows |
|-------|------|---------------|
| Domain CPU / Utilization Share | **Pie (donut)** | Average utilization % per domain across all telemetry entries |
| Compute Domain Breakdown | **Pie** | CPU utilization vs throttling vs context switches |
| Per-domain panels (×7) | **Histogram (bar)** | Distribution of utilization per domain (compute, transaction, security, process, network, streaming, control_plane) |
| Live Domain Utilization | **Time series** | Current values during replay |

## Metrics reference

| Prometheus metric | Labels | Description |
|-------------------|--------|-------------|
| `observability_domain_cpu_usage_pct` | `domain`, `le` | Histogram — one observation per CSV row per domain |
| `observability_domain_cpu_current_pct` | `domain` | Gauge — latest value (pie + live chart) |
| `observability_compute_component_pct` | `component` | Compute sub-metric breakdown |
| `observability_telemetry_entries_total` | — | Rows exported |
| `observability_replay_minute_index` | — | Replay progress |
| `observability_domain_alert_active` | `domain`, `verdict` | 1 when model predicts alert |
| `observability_domain_z_score` | `domain` | Latest residual z-score |
| `observability_fusion_combination` | — | 1 during attack+internal_fault |
| `observability_fusion_alert_active` | — | 1 when any alert domain |
| `observability_model_alerts_fired_total` | `domain`, `verdict` | Counter per alert minute |
| `observability_incidents_created_total` | `kind` | Incidents opened |

### Domain mapping

| Domain | Source metric | Scale |
|--------|---------------|-------|
| **compute** | `compute_cpu_utilization_pct` | Direct 0–100% |
| **transaction** | `app_request_rate_per_min` | Normalized to 0–100 |
| **security** | `app_auth_failure_rate_pct` | ×100 |
| **process** | `memory_utilization_pct` | Direct |
| **network** | `network_packet_drop_rate_pct` | ×100 |
| **streaming** | `streaming_buffer_stall_rate_pct` | Direct |
| **control_plane** | `control_plane_copp_drop_count` | Normalized |

## Demo flow

1. `POST /api/import` — fills histograms from 240-min dataset
2. Open Grafana → pie charts show domain share; histograms show CPU/util distribution
3. Start replay on main dashboard — live time series + compute pie update each minute
4. Jump to 20:16 — compute histogram shifts right; security/process pies grow
