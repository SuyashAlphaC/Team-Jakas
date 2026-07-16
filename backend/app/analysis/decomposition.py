"""Context-aware baseline, residual decomposition, and domain verdicts."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.models import DomainVerdict, Observation, Verdict

# Phase 1 parameters from submission
FORECAST_HORIZON_MIN = 15
SIGMA_GATE = 3.0
SUPPRESS_CONF = 0.78
ALERT_CONF = 0.72
RECON_ERROR_MULT = 2.5

DOMAIN_METRICS = {
    "transaction": ["app_request_rate_per_min", "app_request_rate", "app_error_rate_5xx_pct", "app_error_rate"],
    "security": ["app_auth_failure_rate_pct", "app_auth_failure_rate"],
    "process": ["memory_growth_slope", "memory_utilization_pct", "memory_utilization", "memory_swap_rate_kb_per_sec"],
    "network": ["network_packet_drop_rate_pct", "network_packet_drop", "network_routing_churn_events", "network_routing_churn"],
    "compute": ["compute_cpu_utilization_pct", "compute_cpu", "compute_throttling_duration_ms"],
    "streaming": ["streaming_buffer_stall_rate_pct", "streaming_segment_fetch_latency_ms", "streaming_cdn_rps"],
    "control_plane": ["control_plane_bgp_adjacency_flaps", "control_plane_copp_drop_count", "control_plane_hsrp_state_transitions"],
}

CTX_DOMAIN_MAP = {
    "ingress_multiplier": ["network", "compute"],
    "transaction_multiplier": ["transaction"],
    "identity_multiplier": ["security"],
    "streaming_multiplier": ["streaming"],
}


def _get_metric(obs: Observation, keys: list[str]) -> Optional[float]:
    for k in keys:
        if k in obs.metrics:
            return obs.metrics[k]
        nk = k.replace("_pct", "").replace("_per_min", "")
        for mk, mv in obs.metrics.items():
            if nk in mk or mk in k:
                return mv
    return None


def _robust_zscore(values: list[float], current: float) -> tuple[float, float, float]:
    if len(values) < 2:
        baseline = values[0] if values else current
        scale = max(abs(baseline) * 0.01, 1e-6)
        z = (current - baseline) / scale
        return baseline, scale, z
    arr = np.array(values, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    scale = max(1.4826 * mad, abs(median) * 0.01, 1e-6)
    z = (current - median) / scale
    return median, scale, z


def _context_multiplier(obs: Observation, domain: str) -> float:
    mult = 1.0
    for ctx_key, domains in CTX_DOMAIN_MAP.items():
        full_key = f"ctx_expected_{ctx_key}"
        for ck, cv in obs.context.items():
            if ctx_key.replace("_multiplier", "") in ck or full_key.endswith(ck):
                if domain in domains:
                    mult = max(mult, cv)
    # Also check normalized context keys from dataset
    for ck, cv in obs.context.items():
        if "transaction" in ck and domain == "transaction":
            mult = max(mult, cv)
        if "identity" in ck and domain == "security":
            mult = max(mult, cv)
        if "ingress" in ck and domain in ("network", "compute"):
            mult = max(mult, cv)
        if "streaming" in ck and domain == "streaming":
            mult = max(mult, cv)
    return mult


def _attack_fingerprint(domain: str, obs: Observation, z: float) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    if domain != "security":
        return False, evidence
    auth = _get_metric(obs, DOMAIN_METRICS["security"])
    if auth is not None and auth > 0.15:
        evidence.append(f"auth failure rate {auth:.1%} exceeds 15% threshold")
    if z > SIGMA_GATE:
        evidence.append(f"residual z-score {z:.1f}σ exceeds {SIGMA_GATE}σ gate")
    ctx_id = obs.context.get("identity_multiplier", obs.context.get("ctx_expected_identity_multiplier", 1.0))
    if isinstance(ctx_id, (int, float)) and ctx_id <= 1.0 and auth and auth > 0.1:
        evidence.append("no identity-scoped context event active")
    return len(evidence) >= 2, evidence


def _internal_fault_fingerprint(domain: str, obs: Observation, history: list[Observation], z: float) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    if domain == "process":
        heap = _get_metric(obs, DOMAIN_METRICS["process"])
        if heap is not None and heap > 0.5:
            evidence.append(f"heap growth slope {heap:.2f} MB/min exceeds 0.5 threshold")
        if len(history) >= 2:
            prev_heap = _get_metric(history[-2], DOMAIN_METRICS["process"])
            if heap and prev_heap and heap > prev_heap * 1.5:
                evidence.append("monotonic heap growth detected (PELT-like change point)")
    elif domain == "transaction":
        err = _get_metric(obs, ["app_error_rate_5xx_pct", "app_error_rate"])
        if obs.context.get("transaction_multiplier", 1.0) > 1.0:
            return False, evidence
        if err and err > 5.0:
            evidence.append(f"5xx error rate {err:.1f}% suggests retry/timeout cascade")
    else:
        return False, evidence
    if z > SIGMA_GATE and evidence:
        evidence.append(f"residual {z:.1f}σ with internal degradation pattern")
    return len(evidence) >= 2, evidence


def analyze_observation(
    obs: Observation,
    history: list[Observation],
) -> list[DomainVerdict]:
    verdicts: list[DomainVerdict] = []
    hist_values: dict[str, list[float]] = {d: [] for d in DOMAIN_METRICS}

    for h in history:
        for domain, keys in DOMAIN_METRICS.items():
            v = _get_metric(h, keys)
            if v is not None:
                hist_values[domain].append(v)

    for domain, keys in DOMAIN_METRICS.items():
        observed = _get_metric(obs, keys)
        if observed is None:
            continue

        baseline, scale, z = _robust_zscore(hist_values[domain] or [observed * 0.9], observed)
        ctx_mult = _context_multiplier(obs, domain)
        context_effect = baseline * (ctx_mult - 1.0) if ctx_mult > 1.0 else 0.0
        expected = baseline + context_effect
        residual = observed - expected
        scale = max(scale, abs(expected) * 0.05, abs(baseline) * 0.05, 1e-6)
        adj_z = residual / scale if scale else 0.0

        in_event_scope = ctx_mult > 1.0
        evidence: list[str] = []

        if in_event_scope and (abs(adj_z) <= SIGMA_GATE or observed <= expected * 1.15):
            verdict = Verdict.EXPECTED
            conf = 0.95 if observed <= expected * 1.15 else min(0.98, SUPPRESS_CONF + 0.1 * (1 - abs(adj_z) / SIGMA_GATE))
            reason = (
                f"{domain}: observed {observed:.2g} within context envelope "
                f"(expected ~{expected:.2g}, ctx {ctx_mult:.1f}×). Scheduled event explains surge."
            )
        elif _attack_fingerprint(domain, obs, adj_z)[0]:
            verdict = Verdict.ATTACK
            _, evidence = _attack_fingerprint(domain, obs, adj_z)
            conf = min(0.98, ALERT_CONF + 0.05 * min(abs(adj_z) / SIGMA_GATE, 1.0))
            reason = f"{domain}: ATTACK — {'; '.join(evidence)}"
        elif _internal_fault_fingerprint(domain, obs, history, adj_z)[0]:
            verdict = Verdict.INTERNAL_FAULT
            _, evidence = _internal_fault_fingerprint(domain, obs, history, adj_z)
            conf = min(0.95, ALERT_CONF + 0.03 * min(abs(adj_z) / SIGMA_GATE, 1.0))
            reason = f"{domain}: INTERNAL_FAULT — {'; '.join(evidence)}"
        elif abs(adj_z) > SIGMA_GATE:
            verdict = Verdict.UNEXPLAINED
            conf = ALERT_CONF
            reason = f"{domain}: unexplained residual {adj_z:+.1f}σ with no matching context or fingerprint"
            evidence.append(reason)
        else:
            verdict = Verdict.EXPECTED
            conf = SUPPRESS_CONF
            reason = f"{domain}: within normal bounds ({adj_z:+.1f}σ)"

        verdicts.append(
            DomainVerdict(
                domain=domain,
                verdict=verdict,
                confidence=round(conf, 2),
                baseline=round(baseline, 4),
                observed=round(observed, 4),
                context_effect=round(context_effect, 4),
                residual=round(residual, 4),
                z_score=round(adj_z, 2),
                reason=reason,
                evidence=evidence,
            )
        )
    return verdicts
