"""LSTM autoencoder for auth-domain sequence anomalies."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import torch
import torch.nn as nn

SEQ_LEN = 12
AUTH_FEATURES = ["app_auth_failure_rate_pct", "app_request_rate_per_min", "app_error_rate_5xx_pct"]


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int = 3, hidden: int = 16, latent: int = 8):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden, batch_first=True)
        self.decoder = nn.LSTM(hidden, input_dim, batch_first=True)
        self.hidden = hidden

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h, _) = self.encoder(x)
        h_rep = h.repeat(x.size(1), 1, 1).permute(1, 0, 2)
        out, _ = self.decoder(h_rep)
        return out


def build_sequences(df, feature_cols: list[str], seq_len: int = SEQ_LEN) -> np.ndarray:
    arr = df[feature_cols].values.astype(np.float32)
    # normalize per column
    mu = arr.mean(axis=0)
    sigma = arr.std(axis=0) + 1e-6
    arr = (arr - mu) / sigma
    seqs = []
    for i in range(seq_len, len(arr)):
        seqs.append(arr[i - seq_len : i])
    return np.stack(seqs) if seqs else np.empty((0, seq_len, len(feature_cols)))


def train_lstm_autoencoder(df, epochs: int = 25, batch_size: int = 64) -> tuple[LSTMAutoencoder, dict]:
    seqs = build_sequences(df, AUTH_FEATURES)
    if len(seqs) < 100:
        raise ValueError("insufficient sequences for LSTM training")

    model = LSTMAutoencoder(input_dim=len(AUTH_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    model.train()

    tensor = torch.from_numpy(seqs)
    for _ in range(epochs):
        perm = torch.randperm(len(tensor))
        for start in range(0, len(tensor), batch_size):
            batch = tensor[perm[start : start + batch_size]]
            opt.zero_grad()
            recon = model(batch)
            loss = loss_fn(recon, batch)
            loss.backward()
            opt.step()

    meta = {"mu": df[AUTH_FEATURES].mean().tolist(), "sigma": (df[AUTH_FEATURES].std() + 1e-6).tolist()}
    return model, meta


def save_lstm(model: LSTMAutoencoder, meta: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "meta": meta, "features": AUTH_FEATURES, "seq_len": SEQ_LEN}, path)


def load_lstm(path: Path) -> tuple[LSTMAutoencoder, dict]:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model = LSTMAutoencoder(input_dim=len(ckpt["features"]))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, ckpt


def reconstruction_error(model: LSTMAutoencoder, meta: dict, history_rows: list[dict]) -> float | None:
    if len(history_rows) < SEQ_LEN:
        return None
    mu = np.array(meta["mu"])
    sigma = np.array(meta["sigma"])
    window = []
    for row in history_rows[-SEQ_LEN:]:
        window.append([row.get(f, 0.0) for f in AUTH_FEATURES])
    arr = (np.array(window, dtype=np.float32) - mu.astype(np.float32)) / sigma.astype(np.float32)
    x = torch.from_numpy(arr).unsqueeze(0).float()
    with torch.no_grad():
        recon = model(x)
    err = float(torch.mean((recon - x) ** 2))
    return err
