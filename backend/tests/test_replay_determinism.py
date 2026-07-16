"""Replay should produce identical incident/action counts on each run."""

import asyncio
from pathlib import Path

import pytest

from app.ingestion.csv_adapter import load_observations
from app.replay.engine import ReplayEngine
from app.storage.sqlite import Storage

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def engine(tmp_path):
    storage = Storage(tmp_path / "test.db")
    eng = ReplayEngine(storage, FIXTURES)
    eng.load_fixture("dataset_seed.csv")
    return eng


def test_replay_counts_are_identical_across_runs(engine):
    async def run_once():
        await engine.replay(speed=200.0, step_ms=0)
        return len(engine.storage.list_incidents()), len(engine.storage.list_actions())

    counts = [asyncio.run(run_once()) for _ in range(2)]
    assert counts[0] == counts[1]
    assert counts[0][0] > 0


def test_reset_for_replay_clears_prior_run(engine):
    async def run():
        await engine.replay(speed=200.0, step_ms=0)

    asyncio.run(run())
    first = len(engine.storage.list_incidents())
    asyncio.run(run())
    second = len(engine.storage.list_incidents())
    assert first == second
