# ML Training Guide

Phase 1 describes Prophet, STL, CIS, Isolation Forest, LSTM, and PELT.  
This project **trains real models** on synthetic 14-day telemetry (4032 rows).

## Train once

```bash
cd context-aware-observability
pip install -r backend/requirements.txt
python scripts/train_models.py
```

Or via API after backend is up:

```bash
curl -X POST http://127.0.0.1:8000/api/ml/train
curl http://127.0.0.1:8000/api/ml/status
```

## What gets trained

| Model | Library | Training data | Saved to |
|-------|---------|---------------|----------|
| **Prophet** + CIS regressors | `prophet` | 14-day synthetic CSV | `data/models/prophet_*.joblib` |
| **STL** | `statsmodels` | Same | `data/models/stl_*.joblib` |
| **Isolation Forest** | `sklearn` | Normal rows only | `data/models/isolation_forest.joblib` |
| **PELT** | `ruptures` | Leak labels → threshold | `manifest.json` |
| **LSTM autoencoder** | `torch` | Normal auth sequences | `data/models/lstm_auth.pt` |

## Inference

When `OBS_USE_ML=true` (default) and models exist:

1. **Prophet+CIS** replaces robust median baseline
2. **Isolation Forest** flags multivariate anomalies
3. **PELT** detects heap change-points
4. **LSTM** scores auth sequence reconstruction error

Rule-based analyzers + fusion calibrations still run (hybrid pipeline).

## Why synthetic data?

The secret seed has **6 rows** — too small to train. Synthetic data mirrors Phase 1:
- Diurnal traffic patterns
- Weekend ingress surges (3.5×)
- Merch drops (5× transaction)
- Injected attacks, leaks, retry storms
- Ground-truth labels

## Fallback

If models are missing, the system uses deterministic robust statistics (original demo ladder).
