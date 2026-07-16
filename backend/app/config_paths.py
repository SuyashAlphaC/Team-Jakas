"""Path and settings resolution for local and Docker runs."""

from __future__ import annotations

import os
from pathlib import Path

# backend/app/config_paths.py -> parents[2] = project root locally
_LOCAL_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("OBS_ROOT", _LOCAL_ROOT))
FIXTURES_DIR = Path(os.environ.get("OBS_FIXTURES", ROOT / "fixtures"))
CONFIG_DIR = Path(os.environ.get("OBS_CONFIG", ROOT / "config"))
DATA_DIR = Path(os.environ.get("OBS_DATA", ROOT / "data"))
TOPOLOGY_PATH = CONFIG_DIR / "topology.yml"
MODELS_DIR = Path(os.environ.get("OBS_MODELS", DATA_DIR / "models"))
TRAINING_CSV = Path(os.environ.get("OBS_TRAINING_CSV", DATA_DIR / "training_synthetic.csv"))
USE_ML = os.environ.get("OBS_USE_ML", "true").lower() in ("1", "true", "yes")
