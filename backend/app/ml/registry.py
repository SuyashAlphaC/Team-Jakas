"""Train, save, and load all ML artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import STL

from app.config_paths import MODELS_DIR, TRAINING_CSV
from app.ml.lstm_auth import save_lstm, train_lstm_autoencoder
from app.ml.synthetic import KEY_METRICS, generate_training_data

IF_FEATURES = KEY_METRICS + [
    "streaming_cdn_rps",
    "streaming_segment_fetch_latency_ms",
    "streaming_buffer_stall_rate_pct",
    "control_plane_bgp_adjacency_flaps",
    "control_plane_copp_drop_count",
    "control_plane_hsrp_state_transitions",
    "commerce_cart_abandonment_rate_pct",
    "ctx_expected_ingress_multiplier",
    "ctx_expected_transaction_multiplier",
    "ctx_expected_identity_multiplier",
    "ctx_expected_streaming_multiplier",
]

PROPHET_METRICS = [
    "app_request_rate_per_min",
    "app_auth_failure_rate_pct",
    "memory_growth_slope",
    "compute_cpu_utilization_pct",
]


@dataclass
class TrainingReport:
    rows: int = 0
    prophet_models: list[str] = field(default_factory=list)
    stl_models: list[str] = field(default_factory=list)
    isolation_forest: bool = False
    lstm_auth: bool = False
    pelt_threshold: float = 0.0
    duration_sec: float = 0.0
    errors: list[str] = field(default_factory=list)
    secret_seed_accuracy: float = 0.0
    synthetic_val_accuracy: float = 0.0


class ModelRegistry:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._prophet: dict[str, Prophet] = {}
        self._stl: dict[str, dict] = {}
        self._if: IsolationForest | None = None
        self._lstm = None
        self._lstm_meta: dict = {}
        self._pelt_threshold = 0.5
        self._manifest: dict = {}
        self._loaded = False

    @property
    def ready(self) -> bool:
        return self._loaded and self._if is not None and (bool(self._prophet) or bool(self._stl))

    def manifest_path(self) -> Path:
        return self.models_dir / "manifest.json"

    def load(self) -> bool:
        mp = self.manifest_path()
        if not mp.exists():
            return False
        self._manifest = json.loads(mp.read_text())
        self._prophet = {}
        for name in self._manifest.get("prophet_models", []):
            p = self.models_dir / f"prophet_{name}.joblib"
            if p.exists():
                self._prophet[name] = joblib.load(p)
        self._stl = {}
        for name in self._manifest.get("stl_models", []):
            p = self.models_dir / f"stl_{name}.joblib"
            if p.exists():
                self._stl[name] = joblib.load(p)
        if_path = self.models_dir / "isolation_forest.joblib"
        if if_path.exists():
            self._if = joblib.load(if_path)
        lstm_path = self.models_dir / "lstm_auth.pt"
        if lstm_path.exists():
            from app.ml.lstm_auth import load_lstm

            self._lstm, ckpt = load_lstm(lstm_path)
            self._lstm_meta = ckpt.get("meta", {})
        self._pelt_threshold = float(self._manifest.get("pelt_threshold", 0.5))
        self._loaded = True
        return self.ready

    def train_all(self, df: pd.DataFrame | None = None, save_csv: bool = True, days: int = 28) -> TrainingReport:
        import time

        from app.ml.validate import secret_seed_accuracy, synthetic_holdout_accuracy

        t0 = time.perf_counter()
        report = TrainingReport()

        if df is None:
            df = generate_training_data(days=days, freq_min=5)
        report.rows = len(df)
        if save_csv:
            TRAINING_CSV.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(TRAINING_CSV, index=False)

        train_df = df.iloc[: int(len(df) * 0.85)].copy()
        val_df = df.iloc[int(len(df) * 0.85) :].copy()

        train_df = train_df.copy()
        train_df["ds"] = pd.to_datetime(train_df["timestamp"], utc=True).dt.tz_localize(None)

        # --- Prophet (Tier 1) with CIS regressors ---
        ctx_cols = [c for c in train_df.columns if c.startswith("ctx_expected_")]
        for metric in PROPHET_METRICS:
            try:
                fit_df = train_df[["ds", metric, *ctx_cols]].rename(columns={metric: "y"})
                m = Prophet(
                    daily_seasonality=True,
                    weekly_seasonality=True,
                    yearly_seasonality=False,
                    changepoint_prior_scale=0.05,
                    seasonality_prior_scale=10.0,
                )
                for c in ctx_cols:
                    m.add_regressor(c)
                m.fit(fit_df)
                joblib.dump(m, self.models_dir / f"prophet_{metric}.joblib")
                self._prophet[metric] = m
                report.prophet_models.append(metric)
            except Exception as e:
                report.errors.append(f"prophet/{metric}: {e}")

        # --- STL decomposition (Tier 1) ---
        for metric in ["app_request_rate_per_min", "memory_growth_slope"]:
            try:
                series = train_df[metric].values
                if len(series) >= 50:
                    period = max(12, min(288, len(series) // 4))
                    stl = STL(series, period=period, seasonal=13)
                    res = stl.fit()
                    stl_pack = {"trend_mean": float(np.mean(res.trend)), "seasonal_std": float(np.std(res.seasonal))}
                    joblib.dump(stl_pack, self.models_dir / f"stl_{metric}.joblib")
                    self._stl[metric] = stl_pack
                    report.stl_models.append(metric)
            except Exception as e:
                report.errors.append(f"stl/{metric}: {e}")

        # --- Isolation Forest (Tier 2) ---
        try:
            normal = train_df[
                (train_df["target_security_verdict"] == 0)
                & (train_df["target_process_verdict"] == 0)
                & (train_df["target_transaction_verdict"] == 0)
            ]
            if_cols = [c for c in IF_FEATURES if c in train_df.columns]
            X = normal[if_cols].fillna(0).values
            anomaly_rate = max(0.03, float((train_df[["target_security_verdict", "target_process_verdict", "target_transaction_verdict"]].max(axis=1) > 0).mean()))
            self._if = IsolationForest(
                n_estimators=500,
                contamination=min(0.08, anomaly_rate),
                max_samples="auto",
                random_state=42,
            )
            self._if.fit(X)
            joblib.dump(self._if, self.models_dir / "isolation_forest.joblib")
            report.isolation_forest = True
        except Exception as e:
            report.errors.append(f"isolation_forest: {e}")

        # --- PELT threshold from training leaks (Tier 2) ---
        try:
            normals = train_df[train_df["target_process_verdict"] == 0]["memory_growth_slope"]
            self._pelt_threshold = float(max(0.3, normals.quantile(0.97)))
            report.pelt_threshold = self._pelt_threshold
        except Exception as e:
            report.errors.append(f"pelt: {e}")

        # --- LSTM auth autoencoder (Tier 2) ---
        try:
            normal_df = train_df[train_df["target_security_verdict"] == 0]
            model, meta = train_lstm_autoencoder(normal_df, epochs=40)
            save_lstm(model, meta, self.models_dir / "lstm_auth.pt")
            self._lstm = model
            self._lstm_meta = meta
            report.lstm_auth = True
        except Exception as e:
            report.errors.append(f"lstm: {e}")

        self._manifest = {
            "prophet_models": report.prophet_models,
            "stl_models": report.stl_models,
            "isolation_forest": report.isolation_forest,
            "lstm_auth": report.lstm_auth,
            "pelt_threshold": self._pelt_threshold,
            "training_rows": report.rows,
            "training_days": days,
            "if_features": [c for c in IF_FEATURES if c in df.columns],
        }
        self.manifest_path().write_text(json.dumps(self._manifest, indent=2))
        self._loaded = True

        val = synthetic_holdout_accuracy(val_df)
        seed = secret_seed_accuracy()
        report.synthetic_val_accuracy = val["accuracy"]
        report.secret_seed_accuracy = seed["accuracy"]
        self._manifest["secret_seed_accuracy"] = seed["accuracy"]
        self._manifest["synthetic_val_accuracy"] = val["accuracy"]
        self.manifest_path().write_text(json.dumps(self._manifest, indent=2))

        report.duration_sec = round(time.perf_counter() - t0, 2)
        return report

    def prophet_predict(self, metric: str, ts: str, context: dict[str, float]) -> float | None:
        m = self._prophet.get(metric)
        if not m:
            return None
        future = pd.DataFrame([{"ds": pd.to_datetime(ts, utc=True).tz_localize(None)}])
        mapping = {
            "ingress_multiplier": "ctx_expected_ingress_multiplier",
            "transaction_multiplier": "ctx_expected_transaction_multiplier",
            "identity_multiplier": "ctx_expected_identity_multiplier",
        }
        for reg in m.extra_regressors:
            matched = False
            for key, col in mapping.items():
                if reg == col:
                    future[reg] = context.get(key, 1.0)
                    matched = True
                    break
            if not matched:
                future[reg] = 1.0
        fc = m.predict(future)
        return float(fc["yhat"].iloc[0])

    def isolation_score(self, metrics: dict[str, float], context: dict[str, float]) -> tuple[float, bool]:
        if self._if is None:
            return 0.0, False
        features = self._manifest.get("if_features", IF_FEATURES)
        vec = []
        for f in features:
            if f.startswith("ctx_"):
                key = f.replace("ctx_expected_", "").replace("ctx_", "")
                vec.append(context.get(key, 1.0))
            else:
                vec.append(metrics.get(f, 0.0))
        n_expected = getattr(self._if, "n_features_in_", len(vec))
        if len(vec) != n_expected:
            vec = (vec + [0.0] * n_expected)[:n_expected]
        pred = self._if.decision_function([vec])[0]
        is_anom = self._if.predict([vec])[0] == -1
        return float(pred), bool(is_anom)

    def lstm_auth_error(self, history_metrics: list[dict]) -> float | None:
        if self._lstm is None:
            return None
        from app.ml.lstm_auth import reconstruction_error

        return reconstruction_error(self._lstm, self._lstm_meta, history_metrics)

    @property
    def pelt_threshold(self) -> float:
        return self._pelt_threshold

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "loaded": self._loaded,
            "manifest": self._manifest,
            "models_dir": str(self.models_dir),
        }


registry = ModelRegistry()
