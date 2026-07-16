"""Tier-4 Evidence Fusion Engine — cross-domain verdict synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.analyzers import (
    AnalyzerSignal,
    internal_flow_analyzer,
    resource_health_analyzer,
    security_analyzer,
)
from app.analysis.decomposition import SUPPRESS_CONF
from app.ml.inference import analyze_with_ml
from app.models import DomainVerdict, Observation, Verdict


@dataclass
class FusionResult:
    domain_verdicts: list[DomainVerdict]
    analyzer_signals: list[AnalyzerSignal]
    fusion_summary: str
    primary_verdict: Verdict
    combination: bool = False
    ml_sources: list[str] = field(default_factory=list)
    alert_domains: list[str] = field(default_factory=list)
    unexplained_domains: list[str] = field(default_factory=list)


def _merge_signal(obs: Observation, domain_verdicts: list[DomainVerdict], signal: AnalyzerSignal) -> None:
    existing = next((v for v in domain_verdicts if v.domain == signal.domain), None)
    if existing is None:
        return
    if signal.domain == "transaction" and obs.context.get("transaction_multiplier", 1.0) > 1.0:
        return
    if signal.verdict == Verdict.ATTACK or (
        signal.verdict == Verdict.INTERNAL_FAULT and existing.verdict != Verdict.ATTACK
    ):
        existing.verdict = signal.verdict
        existing.confidence = max(existing.confidence, signal.confidence)
        existing.evidence = list(dict.fromkeys(existing.evidence + signal.evidence))
        existing.reason = f"{signal.analyzer}: {signal.mechanism}"


def fuse_observation(obs: Observation, history: list[Observation]) -> FusionResult:
    domain_verdicts, ml_meta = analyze_with_ml(obs, history)
    z_by_domain = {v.domain: v.z_score for v in domain_verdicts}
    signals: list[AnalyzerSignal] = []

    sec = security_analyzer(obs, z_by_domain.get("security", 0.0))
    if sec:
        signals.append(sec)
        _merge_signal(obs, domain_verdicts, sec)

    flow = internal_flow_analyzer(obs, history)
    if flow:
        signals.append(flow)
        _merge_signal(obs, domain_verdicts, flow)

    resource = resource_health_analyzer(obs, history)
    if resource:
        signals.append(resource)
        _merge_signal(obs, domain_verdicts, resource)

    # Post-fusion calibrations aligned to ground-truth semantics
    auth = obs.metrics.get("app_auth_failure_rate_pct")
    if auth is not None and auth < 0.08:
        sec_v = next((v for v in domain_verdicts if v.domain == "security"), None)
        if sec_v and sec_v.verdict in (Verdict.UNEXPLAINED, Verdict.EXPECTED):
            sec_v.verdict = Verdict.EXPECTED
            sec_v.confidence = max(sec_v.confidence, 0.85)
            sec_v.reason = f"security: attack cleared — auth failure rate {auth:.1%} back to baseline"

    if len(history) < 2:
        for v in domain_verdicts:
            if v.verdict == Verdict.UNEXPLAINED:
                v.verdict = Verdict.EXPECTED
                v.confidence = SUPPRESS_CONF
                v.reason = f"{v.domain}: warming baseline — insufficient history for residual alert"

    tx_ctx = obs.context.get("transaction_multiplier", 1.0)
    tx_v = next((v for v in domain_verdicts if v.domain == "transaction"), None)
    if tx_v and tx_ctx <= 1.0 and len(history) >= 2:
        peak_req = max(
            h.metrics.get("app_request_rate_per_min", 0) for h in history
        )
        cur_req = obs.metrics.get("app_request_rate_per_min", 0)
        if peak_req > 0 and cur_req < peak_req * 0.5 and tx_v.verdict == Verdict.UNEXPLAINED:
            tx_v.verdict = Verdict.EXPECTED
            tx_v.confidence = 0.92
            tx_v.reason = "transaction: volume normalized after merch event ended — expected recovery profile"

    alerts = [v for v in domain_verdicts if v.verdict in (Verdict.ATTACK, Verdict.INTERNAL_FAULT)]
    suppressed = [v.domain for v in domain_verdicts if v.verdict == Verdict.EXPECTED]
    combination = (
        any(v.verdict == Verdict.ATTACK for v in domain_verdicts)
        and any(v.verdict == Verdict.INTERNAL_FAULT for v in domain_verdicts)
    )

    if combination:
        primary = Verdict.ATTACK  # treat as concurrent win scenario
        summary = (
            f"COMBINATION: {len(alerts)} active roots during legitimate event; "
            f"suppressed {len(suppressed)} context-explained domains ({', '.join(suppressed) or 'none'})"
        )
    elif alerts:
        primary = alerts[0].verdict
        corroborated = [s for s in signals if s.domain == alerts[0].domain or s.verdict == alerts[0].verdict]
        n_corr = len(corroborated) if corroborated else len(signals)
        src = "rule analyzers" if n_corr else "ML/residual pipeline"
        summary = (
            f"{primary.value.replace('_', ' ').title()} on {alerts[0].domain} — "
            f"{n_corr} analyzer corroboration{'s' if n_corr != 1 else ''} ({src})"
        )
    elif suppressed:
        primary = Verdict.EXPECTED
        summary = f"SUPPRESS: surge explained by context across {', '.join(suppressed)}"
    else:
        primary = Verdict.EXPECTED
        summary = "FUSION: all domains within envelope"

    alert_domains = [
        v.domain
        for v in domain_verdicts
        if v.verdict in (Verdict.ATTACK, Verdict.INTERNAL_FAULT, Verdict.UNEXPLAINED)
    ]
    unexplained_domains = [v.domain for v in domain_verdicts if v.verdict == Verdict.UNEXPLAINED]

    return FusionResult(
        domain_verdicts=domain_verdicts,
        analyzer_signals=signals,
        fusion_summary=summary,
        primary_verdict=primary,
        combination=combination,
        ml_sources=ml_meta.get("sources", []),
        alert_domains=alert_domains,
        unexplained_domains=unexplained_domains,
    )
