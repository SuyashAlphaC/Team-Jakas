"""Shared data models for observability pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    EXPECTED = "expected"
    ATTACK = "attack"
    INTERNAL_FAULT = "internal_fault"
    UNEXPLAINED = "unexplained"


class CauseClass(str, Enum):
    LEGITIMATE = "legitimate"
    MALICIOUS = "malicious"
    OPERATIONAL = "operational"
    CODE_CONFIG = "code_config"
    COMBINATION = "combination"


class ActionGrade(str, Enum):
    OBSERVE = "observe"
    RATE_LIMIT = "rate_limit"
    THROTTLE = "throttle"
    RESTART = "restart"
    ISOLATE = "isolate"
    ROLLBACK = "rollback"


class RemediationState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class Observation(BaseModel):
    timestamp: str
    source_row: int
    metrics: dict[str, float]
    context: dict[str, float] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class DomainVerdict(BaseModel):
    domain: str
    verdict: Verdict
    confidence: float
    baseline: float
    observed: float
    context_effect: float
    residual: float
    z_score: float
    reason: str
    evidence: list[str] = Field(default_factory=list)


class RootCauseCandidate(BaseModel):
    service: str
    cause_class: CauseClass
    confidence: float
    file: Optional[str] = None
    function: Optional[str] = None
    config_key: Optional[str] = None
    likely_commit: Optional[str] = None
    mechanism: str = ""
    proposed_fix: str = ""
    evidence: list[str] = Field(default_factory=list)


class CausalNode(BaseModel):
    node_id: str
    node_type: str  # symptom | service | root | config | deployment
    label: str
    domain: Optional[str] = None
    service: Optional[str] = None
    metric: Optional[str] = None
    value: Optional[float] = None
    confidence: float = 0.0


class CausalEdge(BaseModel):
    source: str
    target: str
    relation: str  # observed_on | propagates_to | caused_by | configured_by | deployed_in
    weight: float = 1.0
    evidence: str = ""


class CausalGraph(BaseModel):
    nodes: list[CausalNode] = Field(default_factory=list)
    edges: list[CausalEdge] = Field(default_factory=list)
    primary_root_id: Optional[str] = None
    reasoning_chain: list[str] = Field(default_factory=list)


class DeploymentContext(BaseModel):
    service: str
    version: str
    commit: str
    deployed_at: str
    author: str = ""
    message: str = ""
    config_snapshot: dict[str, str] = Field(default_factory=dict)


class Incident(BaseModel):
    incident_id: str
    started_at: str
    status: str = "detected"
    domain_verdicts: list[DomainVerdict] = Field(default_factory=list)
    roots: list[RootCauseCandidate] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    suppressed_domains: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    mttr_detect_ms: Optional[float] = None
    mttr_rca_ms: Optional[float] = None
    mttr_mitigate_ms: Optional[float] = None
    causal_graph: Optional[CausalGraph] = None
    deployment_context: list[DeploymentContext] = Field(default_factory=list)
    reasoning_summary: str = ""


class RemediationAction(BaseModel):
    action_id: str
    incident_id: str
    grade: ActionGrade
    state: RemediationState
    target: str
    reason: str
    confidence: float
    timestamp: str
    proposed_command: str = ""
    rollback_command: str = ""
    requires_approval: bool = False
    blast_radius: str = ""
    risk_score: float = 0.0
    priority: int = 0
    affected_services: list[str] = Field(default_factory=list)
    verification_criteria: str = ""
    verification_result: str = ""
    outcome: str = ""
    learned_from: Optional[str] = None


class ReplayEvent(BaseModel):
    seq: int
    event_type: str
    timestamp: str
    data: dict[str, Any]
