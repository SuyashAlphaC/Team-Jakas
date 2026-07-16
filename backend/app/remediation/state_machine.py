"""Graduated remediation with scale-for-fans + block-attack win scenario."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models import (
    ActionGrade,
    Incident,
    RemediationAction,
    RemediationState,
    Verdict,
)

ACT_CONF = 0.85
HUMAN_APPROVAL_CONF = 0.90


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action_id() -> str:
    return f"act-{uuid.uuid4().hex[:12]}"


def _has_context_event(incident: Incident) -> bool:
    return len(incident.suppressed_domains) > 0 or any(
        v.verdict == Verdict.EXPECTED and v.context_effect > 0
        for v in incident.domain_verdicts
    )


def propose_actions(incident: Incident) -> list[RemediationAction]:
    actions: list[RemediationAction] = []
    has_attack = any(v.verdict == Verdict.ATTACK for v in incident.domain_verdicts)
    has_internal = any(v.verdict == Verdict.INTERNAL_FAULT for v in incident.domain_verdicts)
    in_event = _has_context_event(incident)

    # Win scenario: scale for fans WHILE blocking attack during live event
    if in_event and has_attack:
        actions.append(
            RemediationAction(
                action_id=_action_id(),
                incident_id=incident.incident_id,
                grade=ActionGrade.THROTTLE,
                state=RemediationState.PROPOSED,
                target="checkout",
                reason="Legitimate merch surge active — scale checkout/payment replicas for fans",
                confidence=0.95,
                timestamp=_now(),
                proposed_command="kubectl scale deployment/checkout --replicas=12 && kubectl scale deployment/payment --replicas=8",
                rollback_command="kubectl scale deployment/checkout --replicas=4 && kubectl scale deployment/payment --replicas=3",
                requires_approval=False,
                blast_radius="low — preserves fan checkout path",
            )
        )

    for v in incident.domain_verdicts:
        if v.verdict == Verdict.EXPECTED:
            continue

        if v.verdict == Verdict.ATTACK:
            grade = ActionGrade.RATE_LIMIT
            target = "identity"
            cmd = "waf rate-limit /auth/login --asn-block --top24 --preserve-checkout"
            rollback = "waf rate-limit /auth/login --clear"
            reason = f"Attack on {v.domain} during event: {v.reason}"
            requires = v.confidence >= HUMAN_APPROVAL_CONF
            blast = "medium — targeted at suspect ASNs only"
        elif v.verdict == Verdict.INTERNAL_FAULT:
            if v.domain == "process":
                grade = ActionGrade.RESTART
                target = "identity_svc"
                cmd = "kubectl rollout restart deployment/identity-svc --max-unavailable=1"
                rollback = "kubectl rollout undo deployment/identity-svc"
                blast = "medium — rolling restart, warm standby absorbs auth"
            else:
                grade = ActionGrade.THROTTLE
                target = "payment"
                cmd = "circuit-breaker payment-svc --half-open-after=30s --max-retries=3"
                rollback = "circuit-breaker payment-svc --close"
                blast = "low — stops retry storm without blocking checkout"
            reason = f"Internal fault on {v.domain}: {v.reason}"
            requires = v.confidence >= HUMAN_APPROVAL_CONF
        else:
            continue

        if v.confidence < ACT_CONF and grade != ActionGrade.OBSERVE:
            grade = ActionGrade.OBSERVE
            cmd = f"observe {v.domain} --await-confidence={ACT_CONF}"
            requires = False
            blast = "none"

        actions.append(
            RemediationAction(
                action_id=_action_id(),
                incident_id=incident.incident_id,
                grade=grade,
                state=RemediationState.PROPOSED,
                target=target,
                reason=reason,
                confidence=v.confidence,
                timestamp=_now(),
                proposed_command=cmd,
                rollback_command=rollback,
                requires_approval=requires,
                blast_radius=blast,
            )
        )

    # Graduation ladder: observe first if combination detected
    if has_attack and has_internal and not any(a.grade == ActionGrade.OBSERVE for a in actions):
        actions.insert(
            0,
            RemediationAction(
                action_id=_action_id(),
                incident_id=incident.incident_id,
                grade=ActionGrade.OBSERVE,
                state=RemediationState.PROPOSED,
                target="global",
                reason="Combination incident — observe 30s while correlating attack + internal fault",
                confidence=0.80,
                timestamp=_now(),
                proposed_command="observe --duration=30s --domains=security,process,transaction",
                rollback_command="",
                requires_approval=False,
                blast_radius="none",
            ),
        )

    return actions


def advance_action(action: RemediationAction, approve: bool = False) -> RemediationAction:
    if action.state == RemediationState.PROPOSED:
        if action.requires_approval and not approve:
            action.state = RemediationState.REJECTED
            return action
        action.state = RemediationState.EXECUTING
    elif action.state == RemediationState.EXECUTING:
        action.state = RemediationState.VERIFYING
    elif action.state == RemediationState.VERIFYING:
        action.state = RemediationState.SUCCEEDED
    return action


def rollback_action(action: RemediationAction) -> RemediationAction:
    action.state = RemediationState.ROLLED_BACK
    return action
