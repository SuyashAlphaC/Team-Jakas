"""Validate model accuracy on secret seed and synthetic holdout."""

from __future__ import annotations

from pathlib import Path

from app.analysis.fusion import fuse_observation
from app.config_paths import FIXTURES_DIR
from app.ingestion.csv_adapter import load_observations


def _score_rows(obs_list) -> tuple[int, int, list]:
    history = []
    correct = total = 0
    misses = []
    for obs in obs_list:
        fusion = fuse_observation(obs, history)
        history.append(obs)
        for domain in ("transaction", "security", "process"):
            label = obs.labels.get(f"target_{domain}_verdict", "0")
            pred = next((v.verdict.value for v in fusion.domain_verdicts if v.domain == domain), "n/a")
            total += 1
            ok = (label == "0" and pred == "expected") or (
                label == "1" and pred in ("attack", "internal_fault")
            )
            if ok:
                correct += 1
            else:
                misses.append({"timestamp": obs.timestamp, "domain": domain, "label": label, "pred": pred})
    return correct, total, misses


def secret_seed_accuracy(fixtures_dir: Path | None = None) -> dict:
    base = fixtures_dir or FIXTURES_DIR
    path = base / "dataset_seed.csv"
    if not path.exists():
        path = base / "dataset.csv"
    if not path.exists():
        return {"score": 0, "total": 0, "accuracy": 0.0, "misses": []}
    obs_list = load_observations(path)
    correct, total, misses = _score_rows(obs_list)
    return {
        "score": correct,
        "total": total,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "misses": misses,
    }


def synthetic_holdout_accuracy(df, holdout_frac: float = 0.15) -> dict:
    """Score on held-out tail of synthetic training data."""
    split = int(len(df) * (1 - holdout_frac))
    holdout = df.iloc[split:]
    from app.models import Observation

    obs_list = []
    for i, row in holdout.iterrows():
        metrics = {c: float(row[c]) for c in row.index if c.startswith("app_") or c.startswith("memory_") or c.startswith("network_") or c.startswith("compute_")}
        context = {
            "ingress_multiplier": float(row.get("ctx_expected_ingress_multiplier", 1)),
            "transaction_multiplier": float(row.get("ctx_expected_transaction_multiplier", 1)),
            "identity_multiplier": float(row.get("ctx_expected_identity_multiplier", 1)),
        }
        labels = {c: str(row[c]) for c in row.index if c.startswith("target_")}
        obs_list.append(
            Observation(timestamp=str(row["timestamp"]), source_row=int(i), metrics=metrics, context=context, labels=labels)
        )
    correct, total, misses = _score_rows(obs_list)
    return {
        "score": correct,
        "total": total,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "misses": misses[:10],
    }
