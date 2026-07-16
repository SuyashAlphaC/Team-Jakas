"""FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from app.config_paths import DATA_DIR, FIXTURES_DIR, MODELS_DIR
from app.ml.registry import registry
from app.replay.engine import ReplayEngine
from app.remediation.state_machine import advance_action, rollback_action
from app.reports.generator import render_rca_markdown, render_remediation_markdown, save_remediation_log
from app.storage.sqlite import Storage

DB_PATH = DATA_DIR / "observability.db"
REPORT_DIR = DATA_DIR / "reports"

storage = Storage(DB_PATH)
engine = ReplayEngine(storage, FIXTURES_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if registry.manifest_path().exists():
        registry.load()
    else:
        # Auto-train on first start when no models present (local + Docker)
        registry.train_all(days=28)
    yield


app = FastAPI(title="Context-Aware Observability", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApproveRequest(BaseModel):
    approve: bool = True


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "context-aware-observability",
        "version": "0.3.0",
        "ml_ready": registry.ready,
        "secret_seed_accuracy": registry._manifest.get("secret_seed_accuracy"),
    }


@app.get("/api/ml/status")
def ml_status():
    return registry.status()


@app.post("/api/ml/train")
def ml_train(days: int = 14):
    from app.ml.synthetic import generate_training_data

    df = generate_training_data(days=days, freq_min=5)
    report = registry.train_all(df)
    return {
        "status": "trained",
        "rows": report.rows,
        "prophet": report.prophet_models,
        "stl": report.stl_models,
        "isolation_forest": report.isolation_forest,
        "lstm_auth": report.lstm_auth,
        "pelt_threshold": report.pelt_threshold,
        "secret_seed_accuracy": report.secret_seed_accuracy,
        "synthetic_val_accuracy": report.synthetic_val_accuracy,
        "duration_sec": report.duration_sec,
        "errors": report.errors,
    }


@app.post("/api/ml/load")
def ml_load():
    ok = registry.load()
    if not ok:
        raise HTTPException(404, "no trained models found — POST /api/ml/train first")
    return registry.status()


@app.post("/api/import")
def import_dataset(filename: str = "dataset.csv"):
    try:
        info = engine.load_fixture(filename)
        return {"status": "imported", **info}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/replay/start")
async def start_replay(speed: float = 2.0):
    if engine._running:
        return {"status": "already_running"}
    asyncio.create_task(_run_replay(speed))
    return {"status": "started", "speed": speed}


async def _run_replay(speed: float):
    await engine.replay(speed=speed, step_ms=400)


@app.post("/api/replay/stop")
def stop_replay():
    engine.stop()
    return {"status": "stopped"}


@app.get("/api/replay/state")
def replay_state():
    return storage.get_replay_state()


@app.get("/api/incidents")
def list_incidents():
    return [i.model_dump() for i in storage.list_incidents()]


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    for inc in storage.list_incidents():
        if inc.incident_id == incident_id:
            return inc.model_dump()
    raise HTTPException(404, "incident not found")


@app.get("/api/incidents/{incident_id}/report")
def incident_report(incident_id: str):
    path = REPORT_DIR / f"{incident_id}_rca.md"
    if path.exists():
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
    for inc in storage.list_incidents():
        if inc.incident_id == incident_id:
            return PlainTextResponse(render_rca_markdown(inc), media_type="text/markdown")
    raise HTTPException(404, "incident not found")


@app.get("/api/actions")
def list_actions():
    return [a.model_dump() for a in storage.list_actions()]


@app.get("/api/reports/remediation")
def remediation_report():
    actions = storage.list_actions()
    save_remediation_log(actions)
    path = REPORT_DIR / "remediation_log.md"
    if path.exists():
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
    return PlainTextResponse(render_remediation_markdown(actions), media_type="text/markdown")


@app.get("/api/validation")
def validate_against_labels(use_seed: bool = True):
    """Score decisions against ground-truth labels (canonical 6-row seed by default)."""
    from app.analysis.fusion import fuse_observation
    from app.ingestion.csv_adapter import load_observations

    filename = "dataset_seed.csv" if use_seed else "dataset.csv"
    path = FIXTURES_DIR / filename
    if not path.exists() and use_seed:
        path = FIXTURES_DIR / "dataset.csv"
    obs_list = load_observations(path)
    history: list = []
    results = []
    for obs in obs_list:
        fusion = fuse_observation(obs, history)
        history.append(obs)
        labels = obs.labels
        row = {
            "timestamp": obs.timestamp,
            "predictions": {
                "transaction": next((v.verdict.value for v in fusion.domain_verdicts if v.domain == "transaction"), "n/a"),
                "security": next((v.verdict.value for v in fusion.domain_verdicts if v.domain == "security"), "n/a"),
                "process": next((v.verdict.value for v in fusion.domain_verdicts if v.domain == "process"), "n/a"),
            },
            "labels": {
                "transaction": labels.get("target_transaction_verdict", "0"),
                "security": labels.get("target_security_verdict", "0"),
                "process": labels.get("target_process_verdict", "0"),
            },
        }
        results.append(row)

    def _match(pred: str, label: str) -> bool:
        if label == "0":
            return pred in ("expected", "n/a")
        if label == "1":
            return pred in ("attack", "internal_fault", "unexplained")
        return True

    score = sum(
        1
        for r in results
        for domain in ("transaction", "security", "process")
        if _match(r["predictions"][domain], r["labels"][domain])
    )
    total = len(results) * 3
    return {
        "score": score,
        "total": total,
        "accuracy": round(score / total, 3) if total else 0,
        "dataset": path.name,
        "row_count": len(obs_list),
        "rows": results,
    }


@app.post("/api/actions/{action_id}/advance")
def advance(action_id: str, body: ApproveRequest):
    actions = storage.list_actions()
    action = next((a for a in actions if a.action_id == action_id), None)
    if not action:
        raise HTTPException(404, "action not found")
    updated = advance_action(action, approve=body.approve)
    storage.save_action(updated)
    return updated.model_dump()


@app.post("/api/actions/{action_id}/rollback")
def rollback(action_id: str):
    actions = storage.list_actions()
    action = next((a for a in actions if a.action_id == action_id), None)
    if not action:
        raise HTTPException(404, "action not found")
    updated = rollback_action(action)
    storage.save_action(updated)
    return updated.model_dump()


@app.get("/api/audit")
def audit(limit: int = 50):
    return storage.get_audit_chain(limit)


@app.get("/api/stream")
async def stream():
    queue = engine.subscribe()

    async def event_generator():
        yield f"data: {json.dumps({'event_type': 'connected'})}\n\n"
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event.model_dump())}\n\n"
                if event.event_type == "replay_complete":
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
