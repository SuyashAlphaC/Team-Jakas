#!/usr/bin/env python3
"""Train all ML models on synthetic Phase-1-scale telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ml.registry import registry
from app.ml.synthetic import generate_training_data


def main() -> int:
    days = 28
    print(f"Generating synthetic training data ({days} days, 5-min granularity)...")
    df = generate_training_data(days=days, freq_min=5)
    print(f"  rows: {len(df)}")
    print("Training Prophet, STL, IsolationForest, PELT, LSTM...")
    report = registry.train_all(df, save_csv=True, days=days)
    print(f"  Prophet: {report.prophet_models}")
    print(f"  STL: {report.stl_models}")
    print(f"  IsolationForest: {report.isolation_forest}")
    print(f"  LSTM auth: {report.lstm_auth}")
    print(f"  PELT threshold: {report.pelt_threshold}")
    print(f"  Secret seed accuracy: {report.secret_seed_accuracy * 100:.1f}%")
    print(f"  Synthetic val accuracy: {report.synthetic_val_accuracy * 100:.1f}%")
    print(f"  Duration: {report.duration_sec}s")
    if report.errors:
        print("  Errors:", report.errors)
        return 1
    if report.secret_seed_accuracy < 1.0:
        print("  WARNING: secret seed accuracy below 100% — check fusion calibrations")
    print("Done. Models saved to data/models/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
