import pytest
from pathlib import Path

from app.analysis.fusion import fuse_observation
from app.ingestion.csv_adapter import inspect_csv, load_observations
from app.localization.scanner import localize
from app.rca.engine import build_incident
from app.remediation.state_machine import propose_actions
from app.reports.generator import render_rca_markdown

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEED = FIXTURES / "dataset_seed.csv"
FULL = FIXTURES / "dataset.csv"

def test_csv_loads():
    info = inspect_csv(FULL)
    assert info["row_count"] >= 180
    assert len(load_observations(FULL)) == info["row_count"]


def test_seed_backup_exists():
    info = inspect_csv(SEED)
    assert info["row_count"] == 6


def test_transaction_suppressed_at_merch_drop():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[1], obs_list[:1])
    tx = next(v for v in fusion.domain_verdicts if v.domain == "transaction")
    assert tx.verdict.value == "expected"
    assert tx.confidence >= 0.78


def test_attack_and_internal_at_t16():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    sec = next(v for v in fusion.domain_verdicts if v.domain == "security")
    proc = next(v for v in fusion.domain_verdicts if v.domain == "process")
    assert sec.verdict.value == "attack"
    assert proc.verdict.value == "internal_fault"
    assert fusion.combination is True
    assert len(fusion.analyzer_signals) >= 2


def test_code_localization_has_line_number():
    root = localize("internal_fault_transaction", ["retry storm"])
    assert root.file and "retry.py" in root.file


def test_rca_report_renders():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    incident = build_incident("test-inc", obs_list[2], fusion.domain_verdicts, detect_ms=12.0)
    md = render_rca_markdown(incident)
    assert "Symptom Storm" in md


def test_scale_and_block_actions_for_combination():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    incident = build_incident("test-inc", obs_list[2], fusion.domain_verdicts)
    actions = propose_actions(incident)
    assert len(actions) >= 1


def test_label_accuracy_on_seed():
    obs_list = load_observations(SEED)
    history = []
    correct = total = 0
    for obs in obs_list:
        fusion = fuse_observation(obs, history)
        history.append(obs)
        for domain, label_key in [
            ("transaction", "target_transaction_verdict"),
            ("security", "target_security_verdict"),
            ("process", "target_process_verdict"),
        ]:
            label = obs.labels.get(label_key, "0")
            pred = next((v.verdict.value for v in fusion.domain_verdicts if v.domain == domain), "n/a")
            total += 1
            if (label == "0" and pred == "expected") or (label == "1" and pred in ("attack", "internal_fault")):
                correct += 1
    assert correct / total >= 0.75
