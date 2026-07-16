"""Load stack traces bundled with telemetry fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from app.config_paths import FIXTURES_DIR
from app.models import Observation

_CACHE: dict[str, str] | None = None


def load_stack_trace_index(fixtures_dir: Path | None = None) -> dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    base = fixtures_dir or FIXTURES_DIR
    path = base / "stack_traces.json"
    if not path.exists():
        _CACHE = {}
        return _CACHE
    data = json.loads(path.read_text(encoding="utf-8"))
    _CACHE = {str(k): str(v) for k, v in data.items()}
    return _CACHE


def attach_stack_traces(observations: list[Observation], fixtures_dir: Path | None = None) -> None:
    """Merge stack_traces.json entries into observation labels by timestamp."""
    index = load_stack_trace_index(fixtures_dir)
    if not index:
        return
    for obs in observations:
        trace = index.get(obs.timestamp)
        if trace:
            obs.labels["stack_trace"] = trace


def clear_stack_trace_cache() -> None:
    global _CACHE
    _CACHE = None
