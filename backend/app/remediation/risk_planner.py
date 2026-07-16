"""Risk-aware remediation planner with blast-radius scoring and graduation ladder."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.loader import downstream_services, load_policies, service_for_domain
from app.models import (
    ActionGrade,
    CausalGraph,
    Incident,
    RemediationAction,
    RemediationState,
    Verdict,
)

GRADE_ORDER = {
    ActionGrade.OBSERVE: 0,
    ActionGrade.RATE_LIMIT: 1,
    ActionGrade.THROTTLE: 2,
    ActionGrade.RESTART: 3,
    ActionGrade.ISOLATE: 4,
    ActionGrade.ROLLBACK: 5,
}

GRADE_BLAST_BASE = {
    ActionGrade.OBSERVE: 0.05,
    ActionGrade.RATE_LIMIT: 0.25,
    ActionGrade.THROTTLE: 0.35,
    ActionGrade.RESTART: 0.55,
    ActionGrade.ISOLATE: 0.75,
    ActionGrade.ROLLBACK: 0.65,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action_id(incident_id: str, grade: ActionGrade, target: str, slot: int) -> str:
    safe = target.replace("_", "-").replace("/", "-")[:20]
    return f"act-{incident_id}-{grade.value}-{safe}-{slot}"


def _policies() -> dict:
    return load_policies().get("thresholds", {})


def _blast_radius_score(target: str, grade: ActionGrade) -> tuple[float, list[str], str]:
    affected = downstream_services(target)
    base = GRADE_BLAST_BASE.get(grade, 0.5)
    fanout = min(len(affected) * 0.08, 0.35)
    score = round(min(base + fanout, 0.95), 2)
    label = "low" if score < 0.35 else "medium" if score < 0.65 else "high"
    desc = f"{label} — affects {target}" + (f" + {len(affected)} downstream" if affected else "")
    return score, [target, *affected], desc


def _downgrade_grade(grade: ActionGrade, confidence: float, act_conf: float) -> ActionGrade:
    if confidence >= act_conf:
        return grade
    order = sorted(GRADE_ORDER, key=lambda g: GRADE_ORDER[g])
    idx = order.index(grade)
    return order[max(0, idx - 1)]


def _verification_for(grade: ActionGrade, target: str) -> str:
    checks = {
        ActionGrade.OBSERVE: f"metrics stable on {target} for 30s; no z-score escalation",
        ActionGrade.RATE_LIMIT: f"auth_failure_rate < 0.15 on {target}; checkout p99 stable",
        ActionGrade.THROTTLE: f"request_rate within envelope; error_rate_5xx < 0.5% on {target}",
        ActionGrade.RESTART: f"heap_slope < 0.05; memory_util < 75% on {target} post-rollout",
        ActionGrade.ISOLATE: f"traffic drained from {target}; dependent services healthy",
        ActionGrade.ROLLBACK: f"deploy revision reverted; config hash matches last-known-good on {target}",
    }
    return checks.get(grade, f"recovery metrics nominal on {target}")


def _command_for(grade: ActionGrade, target: str, domain: str, verdict: Verdict) -> tuple[str, str]:
    if grade == ActionGrade.OBSERVE:
        return (
            f"observe --duration=30s --target={target} --domains={domain}",
            "",
        )
    if grade == ActionGrade.RATE_LIMIT:
        return (
            f"waf rate-limit /auth/login --target={target} --asn-block --preserve-checkout",
            f"waf rate-limit /auth/login --target={target} --clear",
        )
    if grade == ActionGrade.THROTTLE:
        if target == "checkout":
            return (
                "kubectl scale deployment/checkout --replicas=12 && kubectl scale deployment/payment --replicas=8",
                "kubectl scale deployment/checkout --replicas=4 && kubectl scale deployment/payment --replicas=3",
            )
        return (
            f"circuit-breaker {target} --half-open-after=30s --max-retries=3",
            f"circuit-breaker {target} --close",
        )
    if grade == ActionGrade.RESTART:
        return (
            f"kubectl rollout restart deployment/{target} --max-unavailable=1",
            f"kubectl rollout undo deployment/{target}",
        )
    if grade == ActionGrade.ISOLATE:
        return (
            f"kubectl cordon node-pool/{target} && traffic-shift --exclude={target}",
            f"kubectl uncordon node-pool/{target} && traffic-shift --restore={target}",
        )
    if grade == ActionGrade.ROLLBACK:
        return (
            f"deploy rollback {target} --to-last-known-good --verify-config",
            f"deploy promote {target} --revision=current",
        )
    return (f"noop {target}", "")


def plan_remediation(
    incident: Incident,
    causal_graph: CausalGraph | None = None,
    prior_outcomes: dict[str, str] | None = None,
) -> list[RemediationAction]:
    """Select graded responses ranked by confidence and inverse blast radius."""
    policies = _policies()
    act_conf = float(policies.get("act_confidence", 0.85))
    human_conf = float(policies.get("human_approval_confidence", 0.90))
    prior_outcomes = prior_outcomes or {}

    has_attack = any(v.verdict == Verdict.ATTACK for v in incident.domain_verdicts)
    has_internal = any(v.verdict == Verdict.INTERNAL_FAULT for v in incident.domain_verdicts)
    in_event = len(incident.suppressed_domains) > 0 or any(
        v.verdict == Verdict.EXPECTED and v.context_effect > 0 for v in incident.domain_verdicts
    )

    candidates: list[RemediationAction] = []

    # Combination: always observe first
    if has_attack and has_internal:
        risk, affected, blast = _blast_radius_score("global", ActionGrade.OBSERVE)
        candidates.append(
            RemediationAction(
                action_id="pending",
                incident_id=incident.incident_id,
                grade=ActionGrade.OBSERVE,
                state=RemediationState.PROPOSED,
                target="global",
                reason="Combination incident — observe while causal graph correlates attack + internal fault",
                confidence=0.80,
                timestamp=_now(),
                proposed_command="observe --duration=30s --domains=security,process,transaction",
                rollback_command="",
                requires_approval=False,
                blast_radius=blast,
                risk_score=risk,
                priority=0,
                affected_services=affected,
                verification_criteria=_verification_for(ActionGrade.OBSERVE, "global"),
            )
        )

    # Scale for fans during live event + attack (win scenario)
    if in_event and has_attack:
        risk, affected, blast = _blast_radius_score("checkout", ActionGrade.THROTTLE)
        candidates.append(
            RemediationAction(
                action_id="pending",
                incident_id=incident.incident_id,
                grade=ActionGrade.THROTTLE,
                state=RemediationState.PROPOSED,
                target="checkout",
                reason="Legitimate merch surge — scale checkout/payment while blocking attack separately",
                confidence=0.95,
                timestamp=_now(),
                proposed_command="kubectl scale deployment/checkout --replicas=12 && kubectl scale deployment/payment --replicas=8",
                rollback_command="kubectl scale deployment/checkout --replicas=4 && kubectl scale deployment/payment --replicas=3",
                requires_approval=False,
                blast_radius=blast,
                risk_score=risk,
                priority=2,
                affected_services=affected,
                verification_criteria=_verification_for(ActionGrade.THROTTLE, "checkout"),
            )
        )

    for v in incident.domain_verdicts:
        if v.verdict == Verdict.EXPECTED:
            continue

        target = service_for_domain(v.domain) or v.domain
        if v.verdict == Verdict.ATTACK:
            grade = ActionGrade.RATE_LIMIT
            reason = f"Attack on {v.domain}: {v.reason}"
        elif v.verdict == Verdict.INTERNAL_FAULT:
            if v.domain == "process":
                grade = ActionGrade.RESTART
                target = "identity_svc"
            else:
                grade = ActionGrade.THROTTLE
                target = "payment"
            reason = f"Internal fault on {v.domain}: {v.reason}"
        else:
            grade = ActionGrade.OBSERVE
            reason = f"Unexplained on {v.domain}: {v.reason}"

        # Learn from prior failures — escalate if observe failed before
        learn_key = f"{v.domain}:{v.verdict.value}"
        if prior_outcomes.get(learn_key) == "failed" and grade == ActionGrade.OBSERVE:
            grade = ActionGrade.RATE_LIMIT if v.verdict == Verdict.ATTACK else ActionGrade.THROTTLE
            reason += " (escalated — prior observe did not recover)"

        grade = _downgrade_grade(grade, v.confidence, act_conf)
        cmd, rollback = _command_for(grade, target, v.domain, v.verdict)
        risk, affected, blast = _blast_radius_score(target, grade)
        requires = v.confidence >= human_conf and grade not in (ActionGrade.OBSERVE,)

        candidates.append(
            RemediationAction(
                action_id="pending",
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
                risk_score=risk,
                priority=GRADE_ORDER[grade],
                affected_services=affected,
                verification_criteria=_verification_for(grade, target),
                learned_from=learn_key if prior_outcomes.get(learn_key) else None,
            )
        )

    # Config-aware rollback if root implicates bad deploy
    for root in incident.roots:
        if root.likely_commit and root.config_key:
            risk, affected, blast = _blast_radius_score(root.service, ActionGrade.ROLLBACK)
            candidates.append(
                RemediationAction(
                    action_id="pending",
                    incident_id=incident.incident_id,
                    grade=ActionGrade.ROLLBACK,
                    state=RemediationState.PROPOSED,
                    target=root.service,
                    reason=f"Config `{root.config_key}` from commit {root.likely_commit[:7]} — rollback to last-known-good",
                    confidence=min(root.confidence, 0.88),
                    timestamp=_now(),
                    proposed_command=f"deploy rollback {root.service} --commit={root.likely_commit} --fix-config {root.config_key}",
                    rollback_command=f"deploy promote {root.service} --revision=current",
                    requires_approval=True,
                    blast_radius=blast,
                    risk_score=risk,
                    priority=GRADE_ORDER[ActionGrade.ROLLBACK],
                    affected_services=affected,
                    verification_criteria=_verification_for(ActionGrade.ROLLBACK, root.service),
                )
            )

    # Sort: observe first, then by ascending risk, descending confidence
    candidates.sort(key=lambda a: (a.priority, a.risk_score, -a.confidence))

    # Attach causal reasoning to first action if available
    if causal_graph and causal_graph.reasoning_chain and candidates:
        candidates[0].reason += f" | Causal: {causal_graph.reasoning_chain[0][:100]}"

    for slot, cand in enumerate(candidates):
        cand.action_id = _action_id(incident.incident_id, cand.grade, cand.target, slot)

    return candidates
