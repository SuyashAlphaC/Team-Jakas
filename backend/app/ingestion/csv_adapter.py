"""CSV ingestion and schema adaptation."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from app.models import Observation

CTX_PREFIX = "ctx_expected_"
TARGET_PREFIX = "target_"

METRIC_ALIASES = {
    "timestamp": ["timestamp", "time", "datetime", "event_time", "ts"],
    "app_request_rate": ["app_request_rate_per_min", "request_rate", "rps"],
    "app_auth_failure_rate": ["app_auth_failure_rate_pct", "auth_failure_rate"],
    "app_error_rate": ["app_error_rate_5xx_pct", "error_rate"],
    "app_latency_p99": ["app_latency_p99_ms", "latency_p99"],
    "memory_growth_slope": ["memory_growth_slope", "heap_growth"],
    "memory_utilization": ["memory_utilization_pct", "memory_util"],
    "network_packet_drop": ["network_packet_drop_rate_pct", "packet_drop"],
    "network_routing_churn": ["network_routing_churn_events", "route_churn"],
    "compute_cpu": ["compute_cpu_utilization_pct", "cpu_util"],
}


def _normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", h.lower().strip())


def inspect_csv(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty")
    headers = list(rows[0].keys())
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return {
        "path": str(path),
        "row_count": len(rows),
        "headers": headers,
        "hash": content_hash,
        "time_range": [rows[0].get("timestamp"), rows[-1].get("timestamp")],
    }


def load_observations(path: Path) -> list[Observation]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        observations: list[Observation] = []
        for i, row in enumerate(reader):
            metrics: dict[str, float] = {}
            context: dict[str, float] = {}
            labels: dict[str, str] = {}
            ts = row.get("timestamp", "")
            for key, val in row.items():
                if not key or val is None or val == "":
                    continue
                nk = _normalize_header(key)
                if nk == "timestamp":
                    continue
                if nk.startswith("ctx_expected_"):
                    ctx_key = nk[len("ctx_expected_"):]
                    try:
                        context[ctx_key] = float(val)
                    except ValueError:
                        labels[key] = str(val)
                elif nk.startswith("target_"):
                    labels[nk] = str(val)
                else:
                    try:
                        metrics[nk] = float(val)
                    except ValueError:
                        labels[key] = str(val)
            if not ts:
                continue
            observations.append(
                Observation(
                    timestamp=ts,
                    source_row=i,
                    metrics=metrics,
                    context=context,
                    labels=labels,
                )
            )
    observations.sort(key=lambda o: (o.timestamp, o.source_row))
    return observations
