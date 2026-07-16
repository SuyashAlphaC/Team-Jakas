"""Prometheus metrics — domain CPU/utilization and model alert state."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.analysis.decomposition import DOMAIN_METRICS, _get_metric
from app.analysis.fusion import FusionResult
from app.models import DomainVerdict, Observation, Verdict

# Histogram: distribution of domain utilization across telemetry entries
DOMAIN_CPU_HISTOGRAM = Histogram(
    "observability_domain_cpu_usage_pct",
    "Domain utilization (0–100) per telemetry entry — CPU for compute, normalized stress index for others",
    ["domain"],
    buckets=(5, 10, 25, 40, 55, 60, 70, 75, 80, 85, 90, 95, 98, 100),
)

# Gauge: latest value per domain (pie charts / live panels)
DOMAIN_CPU_CURRENT = Gauge(
    "observability_domain_cpu_current_pct",
    "Latest domain utilization percentage",
    ["domain"],
)

# Compute sub-metrics for compute-domain pie breakdown
COMPUTE_COMPONENT = Gauge(
    "observability_compute_component_pct",
    "Compute domain sub-metric share (normalized 0–100)",
    ["component"],
)

TELEMETRY_ENTRIES = Counter(
    "observability_telemetry_entries_total",
    "Total telemetry rows exported to metrics",
)

REPLAY_MINUTE = Gauge(
    "observability_replay_minute_index",
    "Current replay progress (minute index)",
)

# ── Model alert metrics (consumed by Grafana unified alerting) ──

DOMAIN_ALERT = Gauge(
    "observability_domain_alert_active",
    "1 when the model predicts an alert verdict for this domain",
    ["domain", "verdict"],
)

DOMAIN_Z_SCORE = Gauge(
    "observability_domain_z_score",
    "Latest residual z-score per domain from CIS decomposition",
    ["domain"],
)

DOMAIN_ALERT_CONFIDENCE = Gauge(
    "observability_domain_alert_confidence",
    "Model confidence (0–1) for the current domain verdict",
    ["domain"],
)

FUSION_ALERT_ACTIVE = Gauge(
    "observability_fusion_alert_active",
    "1 when fusion reports any attack, internal_fault, or unexplained domain",
)

FUSION_COMBINATION = Gauge(
    "observability_fusion_combination",
    "1 during simultaneous attack + internal_fault (combination scenario)",
)

MODEL_ALERTS_FIRED = Counter(
    "observability_model_alerts_fired_total",
    "Count of model alert predictions per replay minute",
    ["domain", "verdict"],
)

INCIDENTS_CREATED = Counter(
    "observability_incidents_created_total",
    "Incidents opened when attack or internal_fault is detected",
    ["kind"],
)

COMBINATION_FIRED = Counter(
    "observability_combination_fired_total",
    "COMBINATION scenario (attack + internal_fault) detections",
)

_ALERT_VERDICTS = frozenset({"attack", "internal_fault", "unexplained"})
_VERDICT_LABELS = ("attack", "internal_fault", "unexplained")

# Normalization ceilings from championship dataset (240-min fixture)
_NORM = {
    "app_request_rate_per_min": 6_000_000.0,
    "compute_throttling_duration_ms": 250.0,
    "compute_context_switches_per_sec": 25_000.0,
    "network_ingress_throughput_bps": 100_000_000_000.0,
    "control_plane_copp_drop_count": 500.0,
    "streaming_cdn_rps": 500_000.0,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _normalize(metric_key: str, value: float) -> float:
    if metric_key.endswith("_pct") or "failure_rate" in metric_key:
        return _clamp(value * 100.0 if value <= 1.0 else value)
    if metric_key in _NORM:
        return _clamp(100.0 * value / _NORM[metric_key])
    if "latency" in metric_key:
        return _clamp(value / 10.0)  # 1000ms → 100%
    if "slope" in metric_key or "growth" in metric_key:
        return _clamp(value * 100.0)
    if "swap" in metric_key:
        return _clamp(value / 2.0)
    if "churn" in metric_key or "flaps" in metric_key or "transitions" in metric_key:
        return _clamp(value * 10.0)
    return _clamp(value)


def domain_utilization_pct(obs: Observation, domain: str) -> float:
    """Map each domain's primary telemetry to a 0–100 utilization scale."""
    keys = DOMAIN_METRICS.get(domain, [])
    val = _get_metric(obs, keys)
    if val is None:
        return 0.0
    primary = keys[0]
    if domain == "compute":
        return _clamp(float(val))
    return _normalize(primary, float(val))


def compute_component_breakdown(obs: Observation) -> dict[str, float]:
    """Compute-domain pie slices: utilization, throttling, context switches."""
    cpu = _get_metric(obs, ["compute_cpu_utilization_pct"]) or 0.0
    throttle = _get_metric(obs, ["compute_throttling_duration_ms"]) or 0.0
    ctx_sw = _get_metric(obs, ["compute_context_switches_per_sec"]) or 0.0
    return {
        "cpu_utilization": _clamp(float(cpu)),
        "cpu_throttling": _normalize("compute_throttling_duration_ms", float(throttle)),
        "context_switches": _normalize("compute_context_switches_per_sec", float(ctx_sw)),
    }


def record_observation(obs: Observation, minute_index: int | None = None) -> None:
    """Record one telemetry entry into histograms and current gauges."""
    for domain in DOMAIN_METRICS:
        pct = domain_utilization_pct(obs, domain)
        DOMAIN_CPU_HISTOGRAM.labels(domain=domain).observe(pct)
        DOMAIN_CPU_CURRENT.labels(domain=domain).set(pct)

    for component, pct in compute_component_breakdown(obs).items():
        COMPUTE_COMPONENT.labels(component=component).set(pct)

    TELEMETRY_ENTRIES.inc()
    if minute_index is not None:
        REPLAY_MINUTE.set(minute_index)


def record_decomposition(verdicts: list[DomainVerdict]) -> None:
    """Boost current gauge for alerting domains based on residual severity."""
    for v in verdicts:
        if v.domain not in DOMAIN_METRICS:
            continue
        if v.verdict.value in _ALERT_VERDICTS:
            stress = _clamp(50.0 + abs(v.z_score) * 12.0)
            DOMAIN_CPU_CURRENT.labels(domain=v.domain).set(stress)


def record_live_tick(obs: Observation, minute_index: int) -> None:
    """Update live gauges during replay without re-accumulating histogram totals."""
    for domain in DOMAIN_METRICS:
        pct = domain_utilization_pct(obs, domain)
        DOMAIN_CPU_CURRENT.labels(domain=domain).set(pct)

    for component, pct in compute_component_breakdown(obs).items():
        COMPUTE_COMPONENT.labels(component=component).set(pct)

    REPLAY_MINUTE.set(minute_index)


def reset_alert_metrics() -> None:
    """Clear alert gauges at replay start."""
    for domain in DOMAIN_METRICS:
        DOMAIN_Z_SCORE.labels(domain=domain).set(0.0)
        DOMAIN_ALERT_CONFIDENCE.labels(domain=domain).set(0.0)
        for verdict in _VERDICT_LABELS:
            DOMAIN_ALERT.labels(domain=domain, verdict=verdict).set(0.0)
    FUSION_ALERT_ACTIVE.set(0.0)
    FUSION_COMBINATION.set(0.0)


def reset_replay_metrics() -> None:
    """Reset alert gauges and replay progress for a fresh run."""
    reset_alert_metrics()
    REPLAY_MINUTE.set(0)


def record_fusion(fusion: FusionResult, *, incident_created: bool = False) -> None:
    """Export model verdicts to Prometheus for Grafana alerting."""
    for v in fusion.domain_verdicts:
        if v.domain not in DOMAIN_METRICS:
            continue
        DOMAIN_Z_SCORE.labels(domain=v.domain).set(float(v.z_score))
        DOMAIN_ALERT_CONFIDENCE.labels(domain=v.domain).set(float(v.confidence))
        for verdict in _VERDICT_LABELS:
            DOMAIN_ALERT.labels(domain=v.domain, verdict=verdict).set(
                1.0 if v.verdict.value == verdict else 0.0
            )
        if v.verdict.value in _ALERT_VERDICTS:
            MODEL_ALERTS_FIRED.labels(domain=v.domain, verdict=v.verdict.value).inc()

    any_alert = any(v.verdict.value in _ALERT_VERDICTS for v in fusion.domain_verdicts)
    FUSION_ALERT_ACTIVE.set(1.0 if any_alert else 0.0)
    FUSION_COMBINATION.set(1.0 if fusion.combination else 0.0)
    if fusion.combination:
        COMBINATION_FIRED.inc()

    if incident_created:
        if fusion.combination:
            kind = "combination"
        elif any(v.verdict == Verdict.ATTACK for v in fusion.domain_verdicts):
            kind = "attack"
        else:
            kind = "internal_fault"
        INCIDENTS_CREATED.labels(kind=kind).inc()


def backfill_from_observations(observations: list[Observation]) -> int:
    """Load entire dataset into histograms (for Grafana distribution panels)."""
    for i, obs in enumerate(observations):
        record_observation(obs, minute_index=i + 1)
    return len(observations)


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
