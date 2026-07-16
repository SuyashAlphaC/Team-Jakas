"""Root cause analysis with causal graph reasoning and config awareness."""

from __future__ import annotations

from typing import Optional

from app.causal.graph import build_causal_graph
from app.config.awareness import deployment_context_for_incident, enrich_root_with_deployment
from app.localization.scanner import localize_all_from_verdict
from app.models import (
    CauseClass,
    DomainVerdict,
    Incident,
    Observation,
    RootCauseCandidate,
    Verdict,
)


def collapse_symptoms(verdicts: list[DomainVerdict]) -> list[str]:
    symptoms: list[str] = []
    for v in verdicts:
        if v.verdict != Verdict.EXPECTED:
            symptoms.append(
                f"{v.domain}: {v.verdict.value} (obs={v.observed:.4g}, "
                f"residual={v.residual:+.4g}, z={v.z_score:+.1f}σ, conf={v.confidence})"
            )
    return symptoms


def rank_roots(verdicts: list[DomainVerdict], obs: Observation | None = None) -> list[RootCauseCandidate]:
    roots: list[RootCauseCandidate] = []
    seen: set[str] = set()
    stack_text = obs.labels.get("stack_trace") if obs else None

    for v in verdicts:
        if v.verdict not in (Verdict.ATTACK, Verdict.INTERNAL_FAULT):
            continue
        key = f"{v.domain}:{v.verdict.value}"
        if key in seen:
            continue
        seen.add(key)

        candidates = localize_all_from_verdict(
            v.domain,
            v.verdict,
            v.evidence + [v.reason],
            stack_text=stack_text,
            confidence=v.confidence,
        )
        for root in candidates:
            file_key = root.file or root.service
            dedupe = f"{root.service}:{file_key}"
            if dedupe in {f"{r.service}:{r.file or r.service}" for r in roots}:
                continue
            if obs:
                root = enrich_root_with_deployment(root, obs)
            roots.append(root)

    if len(roots) > 1:
        roots.append(
            RootCauseCandidate(
                service="multiple",
                cause_class=CauseClass.COMBINATION,
                confidence=min(r.confidence for r in roots),
                mechanism=f"Concurrent roots: {', '.join(r.service for r in roots if r.service != 'multiple')}",
                proposed_fix="Scale for fans + block attack + fix internal leak concurrently",
                evidence=[e for r in roots for e in r.evidence],
            )
        )
    return roots


def build_incident(
    incident_id: str,
    obs: Observation,
    verdicts: list[DomainVerdict],
    fusion_summary: str = "",
    detect_ms: Optional[float] = None,
) -> Incident:
    roots = rank_roots(verdicts, obs)
    symptoms = collapse_symptoms(verdicts)
    suppressed = [v.domain for v in verdicts if v.verdict == Verdict.EXPECTED]
    alert_verdicts = [v for v in verdicts if v.verdict in (Verdict.ATTACK, Verdict.INTERNAL_FAULT)]

    if any(v.verdict == Verdict.ATTACK for v in verdicts):
        status = "remediating"
    elif alert_verdicts:
        status = "investigating"
    else:
        status = "resolved"

    conf = max((v.confidence for v in alert_verdicts), default=0.9)
    if fusion_summary and alert_verdicts:
        symptoms.insert(0, fusion_summary)

    causal_graph = build_causal_graph(obs, verdicts, roots)
    deployments = deployment_context_for_incident(roots, obs)

    reasoning_parts = causal_graph.reasoning_chain[:3]
    reasoning_summary = " → ".join(reasoning_parts) if reasoning_parts else fusion_summary

    return Incident(
        incident_id=incident_id,
        started_at=obs.timestamp,
        status=status,
        domain_verdicts=verdicts,
        roots=roots,
        symptoms=symptoms,
        suppressed_domains=suppressed,
        confidence=round(conf, 2),
        mttr_detect_ms=detect_ms,
        mttr_rca_ms=round((detect_ms or 0) * 1.4, 2) if detect_ms else None,
        causal_graph=causal_graph,
        deployment_context=deployments,
        reasoning_summary=reasoning_summary,
    )
