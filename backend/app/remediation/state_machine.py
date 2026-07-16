"""Graduated remediation — delegates to risk-aware planner."""

from __future__ import annotations

from app.models import Incident, RemediationAction, RemediationState
from app.remediation.feedback import advance_with_verification
from app.remediation.risk_planner import plan_remediation


def propose_actions(
    incident: Incident,
    prior_outcomes: dict[str, str] | None = None,
) -> list[RemediationAction]:
    return plan_remediation(
        incident,
        causal_graph=incident.causal_graph,
        prior_outcomes=prior_outcomes,
    )


def advance_action(
    action: RemediationAction,
    approve: bool = False,
    storage=None,
) -> RemediationAction:
    if storage is not None:
        return advance_with_verification(action, storage, approve=approve)
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
    action.outcome = "rolled_back"
    return action
