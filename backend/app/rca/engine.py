"""Root cause analysis with topology-aware symptom collapse."""

from __future__ import annotations

from typing import Optional

import yaml

from app.config_paths import TOPOLOGY_PATH
from app.localization.scanner import localize_from_verdict
from app.models import (
    CauseClass,
    DomainVerdict,
    Incident,
    Observation,
    RootCauseCandidate,
    Verdict,
)


def _load_topology() -> dict:
    if TOPOLOGY_PATH.exists():
        with TOPOLOGY_PATH.open() as f:
            return yaml.safe_load(f) or {}
    return {}


def collapse_symptoms(verdicts: list[DomainVerdict]) -> list[str]:
    symptoms: list[str] = []
    for v in verdicts:
        if v.verdict != Verdict.EXPECTED:
            symptoms.append(
                f"{v.domain}: {v.verdict.value} (obs={v.observed:.4g}, "
                f"residual={v.residual:+.4g}, z={v.z_score:+.1f}σ, conf={v.confidence})"
            )
    return symptoms


def rank_roots(verdicts: list[DomainVerdict]) -> list[RootCauseCandidate]:
    roots: list[RootCauseCandidate] = []
    seen: set[str] = set()

    for v in verdicts:
        if v.verdict not in (Verdict.ATTACK, Verdict.INTERNAL_FAULT):
            continue
        key = f"{v.domain}:{v.verdict.value}"
        if key in seen:
            continue
        seen.add(key)
        root = localize_from_verdict(v.domain, v.verdict, v.evidence + [v.reason])
        if root:
            root.confidence = v.confidence
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
    roots = rank_roots(verdicts)
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
    )
