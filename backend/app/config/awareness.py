"""Deployment and configuration awareness for incident correlation."""

from __future__ import annotations

from datetime import datetime

from app.config.loader import load_deployments
from app.models import DeploymentContext, Observation, RootCauseCandidate


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def deployments_for_service(service: str, at: str | None = None) -> DeploymentContext | None:
    raw = load_deployments().get(service)
    if not raw:
        return None
    return DeploymentContext(
        service=service,
        version=raw.get("version", "unknown"),
        commit=raw.get("commit", "unknown"),
        deployed_at=raw.get("deployed_at", ""),
        author=raw.get("author", ""),
        message=raw.get("message", ""),
        config_snapshot=dict(raw.get("config", {})),
    )


def enrich_root_with_deployment(root: RootCauseCandidate, obs: Observation) -> RootCauseCandidate:
    """Attach deployment metadata and config values to a localized root cause."""
    dep = deployments_for_service(root.service, obs.timestamp)
    if not dep:
        return root

    if not root.likely_commit or root.likely_commit == dep.commit:
        root.likely_commit = dep.commit

    if root.config_key and root.config_key in dep.config_snapshot:
        bad_val = dep.config_snapshot[root.config_key]
        root.evidence.append(
            f"config/{root.service}/{root.config_key}={bad_val} (deploy {dep.version} @ {dep.deployed_at})"
        )
        root.mechanism += f" Config `{root.config_key}={bad_val}` from deploy {dep.commit[:7]}."

    root.evidence.append(f"Recent deploy: {dep.service} v{dep.version} ({dep.message})")
    return root


def deployment_context_for_incident(
    roots: list[RootCauseCandidate],
    obs: Observation,
) -> list[DeploymentContext]:
    """Collect deployment snapshots for all implicated services."""
    seen: set[str] = set()
    contexts: list[DeploymentContext] = []
    for root in roots:
        if root.service in seen or root.service == "multiple":
            continue
        seen.add(root.service)
        dep = deployments_for_service(root.service, obs.timestamp)
        if dep:
            contexts.append(dep)
    return contexts
