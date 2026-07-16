"""Verification hooks and feedback loop for remediation outcomes."""

from __future__ import annotations

from app.models import RemediationAction, RemediationState


def verify_recovery(action: RemediationAction) -> tuple[bool, str]:
    """Simulated post-action verification — checks criteria against action grade."""
    if action.grade.value == "observe":
        return True, "Metrics stable during observation window"
    if action.grade.value == "rate_limit":
        return True, "auth_failure_rate dropped below 0.15; checkout path preserved"
    if action.grade.value == "throttle":
        return True, "Error rate normalized; fan checkout path within SLO"
    if action.grade.value == "restart":
        return True, "Heap slope normalized post-restart; memory_util < 75%"
    if action.grade.value == "isolate":
        return False, "Downstream checkout latency elevated — partial recovery only"
    if action.grade.value == "rollback":
        return True, "Config hash matches last-known-good; deploy revision verified"
    return True, "Recovery criteria met"


def record_outcome(storage, action: RemediationAction, success: bool, detail: str) -> RemediationAction:
    action.outcome = "succeeded" if success else "failed"
    action.verification_result = detail
    storage.save_action(action)
    storage.record_feedback(action.action_id, action.incident_id, action.grade.value, action.outcome, detail)
    return action


def advance_with_verification(
    action: RemediationAction,
    storage,
    approve: bool = False,
) -> RemediationAction:
    """Advance action through lifecycle with verification and feedback recording."""
    if action.state == RemediationState.PROPOSED:
        if action.requires_approval and not approve:
            action.state = RemediationState.REJECTED
            action.outcome = "rejected"
            storage.save_action(action)
            return action
        action.state = RemediationState.EXECUTING
    elif action.state == RemediationState.EXECUTING:
        action.state = RemediationState.VERIFYING
    elif action.state == RemediationState.VERIFYING:
        ok, detail = verify_recovery(action)
        action.verification_result = detail
        if ok:
            action.state = RemediationState.SUCCEEDED
            action.outcome = "succeeded"
        else:
            action.state = RemediationState.FAILED
            action.outcome = "failed"
        storage.record_feedback(
            action.action_id,
            action.incident_id,
            action.grade.value,
            action.outcome,
            detail,
        )
    storage.save_action(action)
    return action
