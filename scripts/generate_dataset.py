#!/usr/bin/env python3
"""Generate expanded championship-night CSV with broad telemetry and multiple story arcs."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "dataset.csv"
SEED_BACKUP = ROOT / "fixtures" / "dataset_seed.csv"

RNG = np.random.default_rng(42)

# Original 6-row secret seed (embedded verbatim in timeline)
SECRET_SEED_ROWS = [
    {
        "timestamp": "2026-07-16T20:14:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 1.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 62.4,
        "compute_throttling_duration_ms": 0.0,
        "compute_context_switches_per_sec": 4200.0,
        "memory_utilization_pct": 55.2,
        "memory_growth_slope": 0.002,
        "memory_swap_rate_kb_per_sec": 0.0,
        "network_ingress_throughput_bps": 32000000000,
        "network_egress_throughput_bps": 45000000000,
        "network_packet_drop_rate_pct": 0.01,
        "network_routing_churn_events": 0,
        "app_request_rate_per_min": 1200000.0,
        "app_error_rate_5xx_pct": 0.02,
        "app_latency_p99_ms": 120.0,
        "app_auth_failure_rate_pct": 0.02,
        "streaming_cdn_rps": 850000.0,
        "streaming_segment_fetch_latency_ms": 45.0,
        "streaming_buffer_stall_rate_pct": 0.1,
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": 12,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 2.1,
        "target_transaction_verdict": 0,
        "target_security_verdict": 0,
        "target_process_verdict": 0,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
    {
        "timestamp": "2026-07-16T20:15:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 5.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 78.3,
        "compute_throttling_duration_ms": 12.5,
        "compute_context_switches_per_sec": 8900.0,
        "memory_utilization_pct": 58.1,
        "memory_growth_slope": 0.015,
        "memory_swap_rate_kb_per_sec": 0.0,
        "network_ingress_throughput_bps": 85000000000,
        "network_egress_throughput_bps": 92000000000,
        "network_packet_drop_rate_pct": 0.05,
        "network_routing_churn_events": 0,
        "app_request_rate_per_min": 4800000.0,
        "app_error_rate_5xx_pct": 0.15,
        "app_latency_p99_ms": 185.0,
        "app_auth_failure_rate_pct": 0.03,
        "streaming_cdn_rps": 3200000.0,
        "streaming_segment_fetch_latency_ms": 62.0,
        "streaming_buffer_stall_rate_pct": 0.2,
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": 45,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 3.5,
        "target_transaction_verdict": 0,
        "target_security_verdict": 0,
        "target_process_verdict": 0,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
    {
        "timestamp": "2026-07-16T20:16:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 5.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 89.1,
        "compute_throttling_duration_ms": 45.2,
        "compute_context_switches_per_sec": 14200.0,
        "memory_utilization_pct": 64.3,
        "memory_growth_slope": 0.890,
        "memory_swap_rate_kb_per_sec": 0.0,
        "network_ingress_throughput_bps": 92000000000,
        "network_egress_throughput_bps": 98000000000,
        "network_packet_drop_rate_pct": 1.20,
        "network_routing_churn_events": 0,
        "app_request_rate_per_min": 5200000.0,
        "app_error_rate_5xx_pct": 0.85,
        "app_latency_p99_ms": 290.0,
        "app_auth_failure_rate_pct": 0.54,
        "streaming_cdn_rps": 3400000.0,
        "streaming_segment_fetch_latency_ms": 88.0,
        "streaming_buffer_stall_rate_pct": 0.4,
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": 120,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 4.2,
        "target_transaction_verdict": 0,
        "target_security_verdict": 1,
        "target_process_verdict": 1,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
    {
        "timestamp": "2026-07-16T20:17:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 5.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 94.6,
        "compute_throttling_duration_ms": 110.8,
        "compute_context_switches_per_sec": 18500.0,
        "memory_utilization_pct": 72.5,
        "memory_growth_slope": 0.910,
        "memory_swap_rate_kb_per_sec": 12.4,
        "network_ingress_throughput_bps": 98000000000,
        "network_egress_throughput_bps": 99000000000,
        "network_packet_drop_rate_pct": 4.80,
        "network_routing_churn_events": 1,
        "app_request_rate_per_min": 5500000.0,
        "app_error_rate_5xx_pct": 2.40,
        "app_latency_p99_ms": 420.0,
        "app_auth_failure_rate_pct": 0.58,
        "streaming_cdn_rps": 3500000.0,
        "streaming_segment_fetch_latency_ms": 110.0,
        "streaming_buffer_stall_rate_pct": 0.6,
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": 280,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 5.8,
        "target_transaction_verdict": 0,
        "target_security_verdict": 1,
        "target_process_verdict": 1,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
    {
        "timestamp": "2026-07-16T20:18:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 5.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 98.2,
        "compute_throttling_duration_ms": 240.1,
        "compute_context_switches_per_sec": 22100.0,
        "memory_utilization_pct": 81.4,
        "memory_growth_slope": 0.925,
        "memory_swap_rate_kb_per_sec": 88.2,
        "network_ingress_throughput_bps": 99000000000,
        "network_egress_throughput_bps": 99000000000,
        "network_packet_drop_rate_pct": 8.15,
        "network_routing_churn_events": 3,
        "app_request_rate_per_min": 5600000.0,
        "app_error_rate_5xx_pct": 5.10,
        "app_latency_p99_ms": 580.0,
        "app_auth_failure_rate_pct": 0.61,
        "streaming_cdn_rps": 3550000.0,
        "streaming_segment_fetch_latency_ms": 145.0,
        "streaming_buffer_stall_rate_pct": 0.9,
        "control_plane_bgp_adjacency_flaps": 1,
        "control_plane_copp_drop_count": 420,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 7.2,
        "target_transaction_verdict": 0,
        "target_security_verdict": 1,
        "target_process_verdict": 1,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
    {
        "timestamp": "2026-07-16T20:19:00Z",
        "ctx_expected_ingress_multiplier": 3.5,
        "ctx_expected_transaction_multiplier": 1.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 3.5,
        "compute_cpu_utilization_pct": 74.1,
        "compute_throttling_duration_ms": 35.0,
        "compute_context_switches_per_sec": 9800.0,
        "memory_utilization_pct": 89.5,
        "memory_growth_slope": 0.880,
        "memory_swap_rate_kb_per_sec": 140.5,
        "network_ingress_throughput_bps": 41000000000,
        "network_egress_throughput_bps": 52000000000,
        "network_packet_drop_rate_pct": 1.50,
        "network_routing_churn_events": 0,
        "app_request_rate_per_min": 1800000.0,
        "app_error_rate_5xx_pct": 3.20,
        "app_latency_p99_ms": 310.0,
        "app_auth_failure_rate_pct": 0.04,
        "streaming_cdn_rps": 2800000.0,
        "streaming_segment_fetch_latency_ms": 95.0,
        "streaming_buffer_stall_rate_pct": 0.5,
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": 180,
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": 6.1,
        "target_transaction_verdict": 0,
        "target_security_verdict": 0,
        "target_process_verdict": 1,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    },
]

COLUMNS = list(SECRET_SEED_ROWS[0].keys())


def _base_row(ts: datetime) -> dict:
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ctx_expected_ingress_multiplier": 1.0,
        "ctx_expected_transaction_multiplier": 1.0,
        "ctx_expected_identity_multiplier": 1.0,
        "ctx_expected_streaming_multiplier": 1.0,
        "compute_cpu_utilization_pct": round(45 + RNG.random() * 10, 1),
        "compute_throttling_duration_ms": 0.0,
        "compute_context_switches_per_sec": round(3000 + RNG.random() * 800, 1),
        "memory_utilization_pct": round(48 + RNG.random() * 8, 1),
        "memory_growth_slope": round(0.001 + RNG.random() * 0.004, 3),
        "memory_swap_rate_kb_per_sec": 0.0,
        "network_ingress_throughput_bps": round(15e9 + RNG.random() * 5e9, 0),
        "network_egress_throughput_bps": round(20e9 + RNG.random() * 5e9, 0),
        "network_packet_drop_rate_pct": round(0.01 + RNG.random() * 0.02, 2),
        "network_routing_churn_events": 0,
        "app_request_rate_per_min": round(800000 + RNG.random() * 200000, 1),
        "app_error_rate_5xx_pct": round(0.02 + RNG.random() * 0.05, 2),
        "app_latency_p99_ms": round(90 + RNG.random() * 30, 1),
        "app_auth_failure_rate_pct": round(0.01 + RNG.random() * 0.02, 3),
        "streaming_cdn_rps": round(500000 + RNG.random() * 100000, 1),
        "streaming_segment_fetch_latency_ms": round(35 + RNG.random() * 15, 1),
        "streaming_buffer_stall_rate_pct": round(0.05 + RNG.random() * 0.1, 2),
        "control_plane_bgp_adjacency_flaps": 0,
        "control_plane_copp_drop_count": round(5 + RNG.random() * 10, 0),
        "control_plane_hsrp_state_transitions": 0,
        "commerce_cart_abandonment_rate_pct": round(1.5 + RNG.random() * 1.0, 1),
        "target_transaction_verdict": 0,
        "target_security_verdict": 0,
        "target_process_verdict": 0,
        "target_streaming_verdict": 0,
        "target_control_plane_verdict": 0,
    }


def _apply_event(row: dict, *, ingress=1.0, tx=1.0, stream=1.0) -> None:
    row["ctx_expected_ingress_multiplier"] = ingress
    row["ctx_expected_transaction_multiplier"] = tx
    row["ctx_expected_streaming_multiplier"] = stream
    row["network_ingress_throughput_bps"] *= ingress
    row["network_egress_throughput_bps"] *= ingress
    row["app_request_rate_per_min"] *= tx
    row["streaming_cdn_rps"] *= stream
    row["compute_cpu_utilization_pct"] = min(99, row["compute_cpu_utilization_pct"] * (1 + 0.12 * (ingress - 1)))


def generate(start: str = "2026-07-16T18:00:00Z", minutes: int = 180) -> list[dict]:
    t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
    seed_by_ts = {r["timestamp"]: r for r in SECRET_SEED_ROWS}
    rows: list[dict] = []

    for i in range(minutes):
        ts = t0 + timedelta(minutes=i)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if ts_str in seed_by_ts:
            rows.append(dict(seed_by_ts[ts_str]))
            continue

        row = _base_row(ts)
        minute_of_day = ts.hour * 60 + ts.minute

        # Pre-match baseline (18:00–20:13)
        if minute_of_day < 20 * 60 + 14:
            rows.append(row)
            continue

        # Post-merch recovery (20:20–20:39)
        if 20 * 60 + 20 <= minute_of_day <= 20 * 60 + 39:
            row["memory_growth_slope"] = round(0.4 + RNG.random() * 0.2, 3)
            row["memory_utilization_pct"] = round(75 + (minute_of_day - 1220) * 0.3, 1)
            row["target_process_verdict"] = 1
            rows.append(row)
            continue

        # Halftime ingress surge (20:40–20:44)
        if 20 * 60 + 40 <= minute_of_day <= 20 * 60 + 44:
            _apply_event(row, ingress=2.5, stream=2.5)
            rows.append(row)
            continue

        # Mini merch drop (20:45–20:49)
        if 20 * 60 + 45 <= minute_of_day <= 20 * 60 + 49:
            _apply_event(row, ingress=2.0, tx=3.0, stream=2.0)
            rows.append(row)
            continue

        # Retry storm — internal fault, no attack (20:50–20:54)
        if 20 * 60 + 50 <= minute_of_day <= 20 * 60 + 54:
            row["app_error_rate_5xx_pct"] = round(4.0 + RNG.random() * 3, 2)
            row["app_latency_p99_ms"] = round(450 + RNG.random() * 150, 1)
            row["target_transaction_verdict"] = 1
            rows.append(row)
            continue

        # Full-time push (21:00–21:08)
        if 21 * 60 + 0 <= minute_of_day <= 21 * 60 + 8:
            _apply_event(row, ingress=4.0, tx=3.0, stream=4.0)
            rows.append(row)
            continue

        # DDoS during full-time (21:05–21:07) — attack only
        if 21 * 60 + 5 <= minute_of_day <= 21 * 60 + 7:
            row["app_auth_failure_rate_pct"] = round(0.42 + RNG.random() * 0.15, 2)
            row["target_security_verdict"] = 1
            rows.append(row)
            continue

        # BGP/CoPP operational event (21:15–21:18)
        if 21 * 60 + 15 <= minute_of_day <= 21 * 60 + 18:
            row["control_plane_bgp_adjacency_flaps"] = int(3 + RNG.integers(0, 4))
            row["control_plane_copp_drop_count"] = int(800 + RNG.integers(0, 400))
            row["control_plane_hsrp_state_transitions"] = int(RNG.integers(1, 3))
            row["network_routing_churn_events"] = int(2 + RNG.integers(0, 3))
            row["target_control_plane_verdict"] = 1
            rows.append(row)
            continue

        # Streaming degradation window (21:22–21:25)
        if 21 * 60 + 22 <= minute_of_day <= 21 * 60 + 25:
            row["streaming_buffer_stall_rate_pct"] = round(2.5 + RNG.random() * 2, 2)
            row["streaming_segment_fetch_latency_ms"] = round(180 + RNG.random() * 80, 1)
            row["target_streaming_verdict"] = 1
            rows.append(row)
            continue

        rows.append(row)

    return rows


def main() -> None:
    # Backup original seed if not already saved
    if OUT.exists() and not SEED_BACKUP.exists():
        SEED_BACKUP.write_bytes(OUT.read_bytes())

    rows = generate(minutes=240)  # 4-hour championship window: 18:00–22:00
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows → {OUT}")
    print(f"Time range: {rows[0]['timestamp']} → {rows[-1]['timestamp']}")
    print(f"Columns: {len(COLUMNS)}")


if __name__ == "__main__":
    main()
