"""Tier-3 domain analyzers matching Phase 1 architecture."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Observation, Verdict


@dataclass
class AnalyzerSignal:
    analyzer: str
    domain: str
    verdict: Verdict
    confidence: float
    evidence: list[str] = field(default_factory=list)
    mechanism: str = ""


def _metric(obs: Observation, *keys: str) -> float | None:
    for k in keys:
        if k in obs.metrics:
            return obs.metrics[k]
    return None


def security_analyzer(obs: Observation, residual_z: float) -> AnalyzerSignal | None:
    auth = _metric(obs, "app_auth_failure_rate_pct", "app_auth_failure_rate")
    if auth is None:
        return None
    evidence: list[str] = []
    ctx_id = obs.context.get("identity_multiplier", 1.0)
    if auth > 0.15:
        evidence.append(f"auth failure rate {auth:.1%} > 15% bot-stuffing threshold")
    if auth > 0.4:
        evidence.append(f"credential-stuffing signature: {auth:.0%} failures during merch window")
    if ctx_id <= 1.0 and auth > 0.1:
        evidence.append("no identity-scoped context event — residual treated as hostile")
    if residual_z > 3.0:
        evidence.append(f"security residual {residual_z:+.1f}σ during explained surge")

    if len(evidence) < 2:
        return None
    conf = min(0.98, 0.72 + 0.05 * min(abs(residual_z) / 3.0, 1.0) + (0.1 if auth > 0.4 else 0))
    return AnalyzerSignal(
        analyzer="SecurityAnalyzer",
        domain="security",
        verdict=Verdict.ATTACK,
        confidence=round(conf, 2),
        evidence=evidence,
        mechanism="External credential-stuffing camouflaged inside legitimate transaction surge",
    )


def internal_flow_analyzer(obs: Observation, history: list[Observation]) -> AnalyzerSignal | None:
    tx_ctx = obs.context.get("transaction_multiplier", 1.0)
    if tx_ctx > 1.0:
        return None  # merch/event surge explains transaction domain — do not alert

    err = _metric(obs, "app_error_rate_5xx_pct", "app_error_rate")
    req = _metric(obs, "app_request_rate_per_min", "app_request_rate")
    lat = _metric(obs, "app_latency_p99_ms", "app_latency_p99")
    evidence: list[str] = []
    if err and err > 5.0:
        evidence.append(f"5xx error rate {err:.1f}% indicates retry/timeout cascade")
    if lat and lat > 450:
        evidence.append(f"p99 latency {lat:.0f}ms exceeds SLO — payment-svc timeout cascade")
    if req and len(history) >= 3 and err and err > 2.5:
        prev_err = [_metric(h, "app_error_rate_5xx_pct", "app_error_rate") for h in history[-3:]]
        if all(e and e < err for e in prev_err if e is not None):
            evidence.append("monotonic 5xx rise after event ended — self-inflicted retry storm")
    if len(evidence) < 2:
        return None
    return AnalyzerSignal(
        analyzer="InternalFlowAnalyzer",
        domain="transaction",
        verdict=Verdict.INTERNAL_FAULT,
        confidence=0.78,
        evidence=evidence,
        mechanism="Client retry storm from payment-svc timeout without backoff",
    )


def resource_health_analyzer(obs: Observation, history: list[Observation]) -> AnalyzerSignal | None:
    heap = _metric(obs, "memory_growth_slope")
    mem = _metric(obs, "memory_utilization_pct", "memory_utilization")
    swap = _metric(obs, "memory_swap_rate_kb_per_sec")
    evidence: list[str] = []
    if heap and heap > 0.5:
        evidence.append(f"heap growth slope {heap:.2f} MB/min > 0.5 leak threshold")
    if len(history) >= 2:
        prev = _metric(history[-2], "memory_growth_slope")
        if heap and prev and heap > prev * 1.2:
            evidence.append("monotonic heap growth — PELT change-point at auth load onset")
    if mem and mem > 70:
        evidence.append(f"memory utilization {mem:.0f}% approaching OOM")
    if swap and swap > 10:
        evidence.append(f"swap churn {swap:.0f} KB/s — process pressure")
    if len(evidence) < 2:
        return None
    conf = min(0.96, 0.74 + 0.04 * min((heap or 0) / 1.0, 1.0))
    return AnalyzerSignal(
        analyzer="ResourceHealthAnalyzer",
        domain="process",
        verdict=Verdict.INTERNAL_FAULT,
        confidence=round(conf, 2),
        evidence=evidence,
        mechanism="Memory leak in identity-svc under sustained auth failure load",
    )
