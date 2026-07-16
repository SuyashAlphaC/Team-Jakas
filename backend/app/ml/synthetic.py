"""Generate synthetic training telemetry matching Phase 1 Sphere Sports narrative."""

from __future__ import annotations

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

KEY_METRICS = [
    "app_request_rate_per_min",
    "app_auth_failure_rate_pct",
    "app_error_rate_5xx_pct",
    "app_latency_p99_ms",
    "memory_growth_slope",
    "memory_utilization_pct",
    "network_packet_drop_rate_pct",
    "compute_cpu_utilization_pct",
]

CONTEXT_COLS = [
    "ctx_expected_ingress_multiplier",
    "ctx_expected_transaction_multiplier",
    "ctx_expected_identity_multiplier",
    "ctx_expected_streaming_multiplier",
]


def generate_training_data(days: int = 14, freq_min: int = 5) -> pd.DataFrame:
    """14 days × 288 points/day (5-min) ≈ 4032 rows — enough to train Prophet/STL/IF/LSTM."""
    n = days * 24 * 60 // freq_min
    t0 = pd.Timestamp("2026-07-01T00:00:00Z")
    ts = pd.date_range(t0, periods=n, freq=f"{freq_min}min", tz="UTC")

    hour = (ts.hour + ts.minute / 60.0).to_numpy(dtype=float)
    day_of_week = ts.dayofweek.to_numpy(dtype=int)

    # Base diurnal patterns (numpy arrays — mutable for fault injection)
    ingress_base = 30e9 + 5e9 * np.sin(2 * np.pi * hour / 24)
    req_base = 1.2e6 + 200e3 * np.sin(2 * np.pi * hour / 24)
    auth_base = 0.02 + 0.005 * (day_of_week >= 5).astype(float)
    err_base = 0.05 + 0.02 * RNG.random(n)
    lat_base = 120 + 30 * np.sin(2 * np.pi * hour / 24)
    heap_base = 0.002 + 0.001 * RNG.random(n)
    mem_base = 50 + 5 * np.sin(2 * np.pi * hour / 24)
    drop_base = 0.01 + 0.005 * RNG.random(n)
    cpu_base = 55 + 10 * np.sin(2 * np.pi * hour / 24)

    ctx_ingress = np.ones(n)
    ctx_tx = np.ones(n)
    ctx_id = np.ones(n)
    ctx_stream = np.ones(n)

    # Scheduled events: weekend match + daily ingress peaks
    for i in range(n):
        if day_of_week[i] in (5, 6) and 19 <= hour[i] <= 22:
            ctx_ingress[i] = 3.5
            ctx_stream[i] = 3.5
        if day_of_week[i] == 5 and 20.0 <= hour[i] <= 20.5:
            ctx_tx[i] = 5.0

    # Labels: 0 normal, 1 anomaly
    label_tx = np.zeros(n, dtype=int)
    label_sec = np.zeros(n, dtype=int)
    label_proc = np.zeros(n, dtype=int)

    # Inject credential stuffing during merch windows (~5% of rows)
    attack_idx = RNG.choice(n, size=max(20, n // 50), replace=False)
    for i in attack_idx:
        if ctx_tx[i] >= 5.0 and ctx_id[i] <= 1.0:
            auth_base[i] = 0.35 + RNG.random() * 0.25
            label_sec[i] = 1

    # Inject memory leaks (~3%)
    leak_starts = RNG.choice(n - 50, size=max(10, n // 100), replace=False)
    for s in leak_starts:
        for j in range(s, min(s + 40, n)):
            heap_base[j] = max(heap_base[j], 0.5 + (j - s) * 0.02)
            label_proc[j] = 1

    # Inject retry storms after some events
    storm_idx = RNG.choice(n, size=max(15, n // 80), replace=False)
    for i in storm_idx:
        if ctx_tx[i] <= 1.0:
            err_base[i] = 3.0 + RNG.random() * 4
            lat_base[i] = 400 + RNG.random() * 200
            label_tx[i] = 1

    noise = lambda s, m: s * (1 + RNG.normal(0, m, n))

    stream_rps = 850000 + 150000 * np.sin(2 * np.pi * hour / 24)
    stream_lat = 45 + 10 * np.sin(2 * np.pi * hour / 24)
    stream_stall = 0.1 + 0.05 * RNG.random(n)
    bgp_flaps = np.zeros(n, dtype=int)
    copp_drops = 12 + (ctx_ingress > 1).astype(int) * 30
    hsrp_trans = np.zeros(n, dtype=int)
    cart_abandon = 2.0 + 0.5 * (ctx_tx > 1).astype(float)

    df = pd.DataFrame(
        {
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ctx_expected_ingress_multiplier": ctx_ingress,
            "ctx_expected_transaction_multiplier": ctx_tx,
            "ctx_expected_identity_multiplier": ctx_id,
            "ctx_expected_streaming_multiplier": ctx_stream,
            "app_request_rate_per_min": noise(req_base * ctx_tx, 0.05),
            "app_auth_failure_rate_pct": np.clip(noise(auth_base, 0.1), 0, 1),
            "app_error_rate_5xx_pct": np.clip(noise(err_base, 0.15), 0, 20),
            "app_latency_p99_ms": np.clip(noise(lat_base, 0.08), 50, 2000),
            "memory_growth_slope": np.clip(noise(heap_base, 0.2), 0, 5),
            "memory_utilization_pct": np.clip(noise(mem_base + heap_base * 5, 0.03), 0, 100),
            "network_packet_drop_rate_pct": np.clip(noise(drop_base * (1 + ctx_ingress * 0.1), 0.2), 0, 15),
            "compute_cpu_utilization_pct": np.clip(noise(cpu_base * (1 + ctx_ingress * 0.15), 0.05), 0, 100),
            "streaming_cdn_rps": noise(stream_rps * ctx_stream, 0.06),
            "streaming_segment_fetch_latency_ms": np.clip(noise(stream_lat, 0.1), 20, 500),
            "streaming_buffer_stall_rate_pct": np.clip(noise(stream_stall, 0.2), 0, 5),
            "control_plane_bgp_adjacency_flaps": bgp_flaps,
            "control_plane_copp_drop_count": copp_drops,
            "control_plane_hsrp_state_transitions": hsrp_trans,
            "commerce_cart_abandonment_rate_pct": np.clip(noise(cart_abandon, 0.15), 0, 20),
            "target_transaction_verdict": label_tx,
            "target_security_verdict": label_sec,
            "target_process_verdict": label_proc,
        }
    )
    return df
