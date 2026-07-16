"""Load remediation policies and topology shared by planner modules."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from app.config_paths import CONFIG_DIR, TOPOLOGY_PATH

POLICIES_PATH = CONFIG_DIR / "remediation-policies.yml"
DEPLOYMENTS_PATH = CONFIG_DIR / "deployments.yml"


@lru_cache(maxsize=1)
def load_topology() -> dict[str, Any]:
    if TOPOLOGY_PATH.exists():
        with TOPOLOGY_PATH.open() as f:
            return yaml.safe_load(f) or {}
    return {}


@lru_cache(maxsize=1)
def load_policies() -> dict[str, Any]:
    if POLICIES_PATH.exists():
        with POLICIES_PATH.open() as f:
            return yaml.safe_load(f) or {}
    return {
        "thresholds": {
            "suppress_confidence": 0.78,
            "alert_confidence": 0.72,
            "act_confidence": 0.85,
            "human_approval_confidence": 0.90,
        },
        "graduation": ["observe", "rate_limit", "throttle", "isolate", "rollback"],
    }


@lru_cache(maxsize=1)
def load_deployments() -> dict[str, Any]:
    if DEPLOYMENTS_PATH.exists():
        with DEPLOYMENTS_PATH.open() as f:
            data = yaml.safe_load(f) or {}
            return data.get("deployments", {})
    return {}


def service_for_domain(domain: str) -> str | None:
    topo = load_topology()
    mapping = topo.get("domain_mapping", {})
    return mapping.get(domain)


def downstream_services(service: str) -> list[str]:
    topo = load_topology()
    services = topo.get("services", {})
    seen: set[str] = set()
    queue = list(services.get(service, {}).get("downstream", []))
    while queue:
        s = queue.pop(0)
        if s in seen:
            continue
        seen.add(s)
        queue.extend(services.get(s, {}).get("downstream", []))
    return sorted(seen)


def upstream_services(service: str) -> list[str]:
    topo = load_topology()
    services = topo.get("services", {})
    seen: set[str] = set()
    queue = list(services.get(service, {}).get("upstream", []))
    while queue:
        s = queue.pop(0)
        if s in seen:
            continue
        seen.add(s)
        queue.extend(services.get(s, {}).get("upstream", []))
    return sorted(seen)
