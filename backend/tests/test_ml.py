"""ML training and inference tests."""

from pathlib import Path

import pytest

from app.ml.registry import ModelRegistry
from app.ml.synthetic import generate_training_data


@pytest.fixture(scope="module")
def trained_registry(tmp_path_factory):
    reg = ModelRegistry(models_dir=tmp_path_factory.mktemp("models"))
    df = generate_training_data(days=3, freq_min=15)  # ~288 rows — fast train
    report = reg.train_all(df, save_csv=False)
    assert report.prophet_models, f"prophet failed: {report.errors}"
    assert report.isolation_forest
    return reg


def test_synthetic_data_shape():
    df = generate_training_data(days=2, freq_min=10)
    assert len(df) > 100
    assert "app_auth_failure_rate_pct" in df.columns


def test_train_prophet_and_if(trained_registry):
    st = trained_registry.status()
    assert st["ready"]
    assert "app_request_rate_per_min" in st["manifest"]["prophet_models"]


def test_prophet_predict(trained_registry):
    pred = trained_registry.prophet_predict(
        "app_request_rate_per_min",
        "2026-07-16T20:15:00Z",
        {"ingress_multiplier": 3.5, "transaction_multiplier": 5.0, "identity_multiplier": 1.0},
    )
    assert pred is not None
    assert pred > 0


def test_isolation_forest_scoring(trained_registry):
    score, anom = trained_registry.isolation_score(
        {"app_auth_failure_rate_pct": 0.55, "app_request_rate_per_min": 5e6},
        {"ingress_multiplier": 3.5, "transaction_multiplier": 5.0, "identity_multiplier": 1.0},
    )
    assert isinstance(score, float)
