"""ML-enhanced baseline, residual, and anomaly scoring."""

from __future__ import annotations

from typing import Optional

import numpy as np
import ruptures as rpt

from app.analysis.decomposition import (
    ALERT_CONF,
    DOMAIN_METRICS,
    SIGMA_GATE,
    SUPPRESS_CONF,
    _context_multiplier,
    _get_metric,
    analyze_observation,
)
from app.config_paths import USE_ML
from app.ml.cis import cis
from app.ml.registry import registry
from app.models import DomainVerdict, Observation, Verdict

METRIC_TO_DOMAIN = {
    "app_request_rate_per_min": "transaction",
    "app_auth_failure_rate_pct": "security",
    "memory_growth_slope": "process",
    "compute_cpu_utilization_pct": "compute",
}


def _ensure_registry() -> bool:
    if registry.ready:
        return True
    if registry.manifest_path().exists():
        return registry.load()
    return False


def _pelt_change_point(values: list[float], threshold: float) -> bool:
    if len(values) < 8:
        return False
    arr = np.array(values, dtype=float).reshape(-1, 1)
    algo = rpt.Pelt(model="rbf", min_size=3, jump=1).fit(arr)
    try:
        bkps = algo.predict(pen=1.0)
        return len(bkps) > 1
    except Exception:
        return values[-1] > threshold and values[-1] > values[0] * 2


def analyze_with_ml(
    obs: Observation,
    history: list[Observation],
) -> tuple[list[DomainVerdict], dict]:
    """Run ML models when trained; merge with rule-based decomposition."""
    ml_meta: dict = {"ml_active": False, "sources": []}

    if not USE_ML or not _ensure_registry():
        return analyze_observation(obs, history), ml_meta

    ml_meta["ml_active"] = True
    verdicts = analyze_observation(obs, history)
    ctx_vec = cis.enrich(obs.context)
    ctx = ctx_vec.as_dict()

    # Prophet baselines (Tier 1)
    for metric, domain in METRIC_TO_DOMAIN.items():
        pred = registry.prophet_predict(metric, obs.timestamp, ctx)
        observed = obs.metrics.get(metric)
        if pred is None or observed is None:
            continue
        ctx_mult = _context_multiplier(obs, domain)
        expected = pred * max(ctx_mult, 1.0) if ctx_mult > 1.0 else pred
        residual = observed - expected
        scale = max(abs(expected) * 0.05, 1e-6)
        z = residual / scale

        v = next((x for x in verdicts if x.domain == domain), None)
        if v:
            v.baseline = round(pred, 4)
            v.context_effect = round(expected - pred, 4)
            v.observed = round(observed, 4)
            v.residual = round(residual, 4)
            v.z_score = round(z, 2)
            v.evidence.append(f"Prophet+CIS forecast baseline={pred:.4g}, expected={expected:.4g}")
            ml_meta["sources"].append(f"prophet:{metric}")

            if ctx_mult > 1.0 and (abs(z) <= SIGMA_GATE or observed <= expected * 1.15):
                v.verdict = Verdict.EXPECTED
                v.confidence = 0.95
                v.reason = f"{domain}: Prophet+CIS envelope (ctx {ctx_mult:.1f}×) explains observation"

    # Isolation Forest (Tier 2) — never override context-suppressed domains
    if_score, is_anom = registry.isolation_score(obs.metrics, ctx)
    ml_meta["isolation_forest_score"] = if_score
    if is_anom:
        ml_meta["sources"].append("isolation_forest")
        for v in verdicts:
            ctx_mult = _context_multiplier(obs, v.domain)
            if ctx_mult > 1.0:
                continue
            if v.verdict == Verdict.EXPECTED and abs(v.z_score) > 2.0:
                v.verdict = Verdict.UNEXPLAINED
                v.confidence = ALERT_CONF
                v.evidence.append(f"IsolationForest flagged multivariate anomaly (score={if_score:.3f})")

    # PELT on heap series (Tier 2)
    heap_hist = [_get_metric(h, ["memory_growth_slope"]) or 0.0 for h in history]
    heap_cur = _get_metric(obs, ["memory_growth_slope"])
    if heap_cur is not None:
        series = heap_hist + [heap_cur]
        if _pelt_change_point(series, registry.pelt_threshold) and heap_cur >= max(registry.pelt_threshold, 0.25):
            proc = next((v for v in verdicts if v.domain == "process"), None)
            if proc and proc.verdict != Verdict.ATTACK:
                proc.verdict = Verdict.INTERNAL_FAULT
                proc.confidence = max(proc.confidence, 0.80)
                proc.reason = f"process: PELT change-point on heap slope ({heap_cur:.2f} MB/min)"
                proc.evidence.append(f"PELT change-point on heap slope (threshold={registry.pelt_threshold})")
                ml_meta["sources"].append("pelt:memory")

    # LSTM auth autoencoder (Tier 2)
    hist_metrics = [h.metrics for h in history] + [obs.metrics]
    recon = registry.lstm_auth_error(hist_metrics)
    if recon is not None:
        ml_meta["lstm_recon_error"] = recon
        if recon > 0.35:
            sec = next((v for v in verdicts if v.domain == "security"), None)
            if sec and obs.metrics.get("app_auth_failure_rate_pct", 0) > 0.1:
                sec.verdict = Verdict.ATTACK
                sec.confidence = max(sec.confidence, min(0.97, 0.75 + recon))
                sec.evidence.append(f"LSTM autoencoder recon error={recon:.3f} on auth sequence")
                ml_meta["sources"].append("lstm:auth")

    return verdicts, ml_meta
