"""Causal dependency graph — trace correlated symptoms to root cause."""

from __future__ import annotations

from app.config.loader import downstream_services, load_topology, service_for_domain, upstream_services
from app.models import (
    CausalEdge,
    CausalGraph,
    CausalNode,
    DomainVerdict,
    Observation,
    RootCauseCandidate,
    Verdict,
)

# Metric → symptom label + typical propagation path
METRIC_SYMPTOMS: list[tuple[str, str, str, float]] = [
    ("memory_growth_slope", "memory_leak", "process", 0.85),
    ("memory_utilization_pct", "memory_pressure", "process", 0.75),
    ("memory_swap_rate_kb_per_sec", "swap_churn", "process", 0.80),
    ("compute_cpu_utilization_pct", "cpu_spike", "compute", 0.70),
    ("compute_throttling_duration_ms", "cpu_throttle", "compute", 0.72),
    ("app_auth_failure_rate_pct", "auth_failures", "security", 0.90),
    ("app_latency_p99_ms", "latency_spike", "transaction", 0.78),
    ("app_error_rate_5xx_pct", "error_burst", "transaction", 0.76),
    ("app_request_rate_per_min", "request_surge", "transaction", 0.60),
    ("network_packet_drop_rate_pct", "packet_loss", "network", 0.74),
    ("network_ingress_throughput_bps", "ingress_surge", "network", 0.55),
]

# Known causal propagation: upstream symptom → downstream symptom
PROPAGATION_RULES: list[tuple[str, str, str, float]] = [
    ("auth_failures", "cpu_spike", "identity_svc overload from failed auth attempts", 0.82),
    ("auth_failures", "latency_spike", "checkout blocked on identity dependency", 0.78),
    ("memory_leak", "cpu_spike", "GC pressure from heap growth", 0.85),
    ("memory_leak", "latency_spike", "identity_svc slow under memory pressure", 0.80),
    ("memory_leak", "swap_churn", "kernel swapping under heap pressure", 0.88),
    ("error_burst", "latency_spike", "retry storm amplifies tail latency", 0.83),
    ("request_surge", "cpu_spike", "legitimate load during merch drop", 0.65),
    ("packet_loss", "latency_spike", "network degradation propagates to app tier", 0.70),
]


def _node_id(prefix: str, key: str) -> str:
    return f"{prefix}:{key}"


def _metric_threshold(metric: str, value: float) -> bool:
    thresholds = {
        "memory_growth_slope": 0.05,
        "memory_utilization_pct": 70.0,
        "memory_swap_rate_kb_per_sec": 1.0,
        "compute_cpu_utilization_pct": 75.0,
        "compute_throttling_duration_ms": 5.0,
        "app_auth_failure_rate_pct": 0.10,
        "app_latency_p99_ms": 200.0,
        "app_error_rate_5xx_pct": 0.5,
        "network_packet_drop_rate_pct": 0.5,
    }
    t = thresholds.get(metric)
    if t is None:
        return False
    if metric == "app_request_rate_per_min":
        return value > 3_000_000
    return value >= t


def _extract_symptoms(obs: Observation, verdicts: list[DomainVerdict]) -> list[CausalNode]:
    nodes: list[CausalNode] = []
    active_domains = {v.domain for v in verdicts if v.verdict != Verdict.EXPECTED}

    for metric, label, domain, base_conf in METRIC_SYMPTOMS:
        val = obs.metrics.get(metric)
        if val is None:
            continue
        if not _metric_threshold(metric, val) and domain not in active_domains:
            continue
        conf = base_conf
        for v in verdicts:
            if v.domain == domain and v.verdict != Verdict.EXPECTED:
                conf = max(conf, v.confidence)
        nodes.append(
            CausalNode(
                node_id=_node_id("symptom", label),
                node_type="symptom",
                label=label.replace("_", " "),
                domain=domain,
                metric=metric,
                value=round(val, 4),
                confidence=round(conf, 2),
            )
        )
    return nodes


def build_causal_graph(
    obs: Observation,
    verdicts: list[DomainVerdict],
    roots: list[RootCauseCandidate],
) -> CausalGraph:
    """Construct symptom → service → root cause dependency graph."""
    nodes: list[CausalNode] = []
    edges: list[CausalEdge] = []
    reasoning: list[str] = []

    symptom_nodes = _extract_symptoms(obs, verdicts)
    nodes.extend(symptom_nodes)
    symptom_ids = {n.node_id for n in symptom_nodes}

    # Domain verdict symptoms
    for v in verdicts:
        if v.verdict == Verdict.EXPECTED:
            continue
        sid = _node_id("domain", v.domain)
        nodes.append(
            CausalNode(
                node_id=sid,
                node_type="symptom",
                label=f"{v.domain} {v.verdict.value}",
                domain=v.domain,
                confidence=v.confidence,
            )
        )
        symptom_ids.add(sid)

    # Service nodes from topology
    implicated_services: set[str] = set()
    for v in verdicts:
        if v.verdict == Verdict.EXPECTED:
            continue
        svc = service_for_domain(v.domain)
        if svc:
            implicated_services.add(svc)

    for root in roots:
        if root.service != "multiple":
            implicated_services.add(root.service)

    for svc in sorted(implicated_services):
        nodes.append(
            CausalNode(
                node_id=_node_id("service", svc),
                node_type="service",
                label=svc,
                service=svc,
                confidence=0.9,
            )
        )

    # Root cause nodes
    primary_root_id: str | None = None
    best_conf = 0.0
    for i, root in enumerate(roots):
        if root.cause_class.value == "combination":
            continue
        rid = _node_id("root", root.service)
        nodes.append(
            CausalNode(
                node_id=rid,
                node_type="root",
                label=f"{root.service} ({root.cause_class.value})",
                service=root.service,
                confidence=root.confidence,
            )
        )
        if root.confidence > best_conf:
            best_conf = root.confidence
            primary_root_id = rid

        if root.config_key:
            cid = _node_id("config", root.config_key)
            nodes.append(
                CausalNode(
                    node_id=cid,
                    node_type="config",
                    label=root.config_key,
                    service=root.service,
                    confidence=root.confidence,
                )
            )
            edges.append(
                CausalEdge(
                    source=rid,
                    target=cid,
                    relation="configured_by",
                    weight=root.confidence,
                    evidence=f"Config key {root.config_key} implicated in {root.mechanism[:80]}",
                )
            )

        if root.likely_commit:
            did = _node_id("deploy", root.likely_commit)
            nodes.append(
                CausalNode(
                    node_id=did,
                    node_type="deployment",
                    label=f"commit {root.likely_commit[:7]}",
                    service=root.service,
                    confidence=0.85,
                )
            )
            edges.append(
                CausalEdge(
                    source=rid,
                    target=did,
                    relation="deployed_in",
                    weight=0.85,
                    evidence=f"Recent deploy {root.likely_commit} on {root.service}",
                )
            )

    # Symptom → service edges via domain mapping
    for sn in symptom_nodes:
        svc = service_for_domain(sn.domain or "")
        if not svc:
            continue
        svc_id = _node_id("service", svc)
        edges.append(
            CausalEdge(
                source=sn.node_id,
                target=svc_id,
                relation="observed_on",
                weight=sn.confidence,
                evidence=f"{sn.metric}={sn.value} on {sn.domain}",
            )
        )

    for v in verdicts:
        if v.verdict == Verdict.EXPECTED:
            continue
        svc = service_for_domain(v.domain)
        if not svc:
            continue
        edges.append(
            CausalEdge(
                source=_node_id("domain", v.domain),
                target=_node_id("service", svc),
                relation="observed_on",
                weight=v.confidence,
                evidence=v.reason,
            )
        )

    # Symptom propagation (correlated symptoms)
    labels = {n.label.replace(" ", "_"): n.node_id for n in symptom_nodes}
    for src_label, dst_label, evidence, weight in PROPAGATION_RULES:
        src_id = labels.get(src_label) or _node_id("symptom", src_label)
        dst_id = labels.get(dst_label) or _node_id("symptom", dst_label)
        if src_id in symptom_ids and dst_id in symptom_ids:
            edges.append(
                CausalEdge(
                    source=src_id,
                    target=dst_id,
                    relation="propagates_to",
                    weight=weight,
                    evidence=evidence,
                )
            )
            reasoning.append(f"{src_label} → {dst_label}: {evidence}")

    # Service → root cause (caused_by)
    for root in roots:
        if root.cause_class.value == "combination":
            continue
        rid = _node_id("root", root.service)
        svc_id = _node_id("service", root.service)
        edges.append(
            CausalEdge(
                source=svc_id,
                target=rid,
                relation="caused_by",
                weight=root.confidence,
                evidence=root.mechanism[:120],
            )
        )

    # Topology propagation: upstream service stress → downstream latency
    topo = load_topology()
    for svc in implicated_services:
        for up in upstream_services(svc):
            if up in implicated_services:
                edges.append(
                    CausalEdge(
                        source=_node_id("service", up),
                        target=_node_id("service", svc),
                        relation="propagates_to",
                        weight=0.7,
                        evidence=f"Topology: {up} → {svc} dependency chain",
                    )
                )

    # Build reasoning chain: trace from primary root backward
    if primary_root_id:
        root_node = next((n for n in nodes if n.node_id == primary_root_id), None)
        if root_node:
            upstream_symptoms = [
                e.source for e in edges
                if e.target == _node_id("service", root_node.service or "")
                and e.relation == "observed_on"
            ]
            symptom_labels = [n.label for n in nodes if n.node_id in upstream_symptoms]
            reasoning.insert(
                0,
                f"Primary root: {root_node.label} — correlated symptoms: {', '.join(symptom_labels) or 'domain verdicts'}",
            )
            blast = downstream_services(root_node.service or "")
            if blast:
                reasoning.append(f"Blast radius if {root_node.service} fails: {', '.join(blast)}")

    return CausalGraph(
        nodes=nodes,
        edges=edges,
        primary_root_id=primary_root_id,
        reasoning_chain=reasoning,
    )
