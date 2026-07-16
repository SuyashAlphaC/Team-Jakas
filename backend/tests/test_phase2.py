"""Phase 2 tests — causal graph, risk planner, config awareness."""

import pytest
from pathlib import Path

from app.analysis.fusion import fuse_observation
from app.causal.graph import build_causal_graph
from app.config.awareness import enrich_root_with_deployment
from app.ingestion.csv_adapter import load_observations
from app.localization.scanner import localize
from app.rca.engine import build_incident
from app.remediation.risk_planner import plan_remediation
from app.reports.generator import render_rca_markdown

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEED = FIXTURES / "dataset_seed.csv"


def test_causal_graph_traces_symptoms_to_root():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    incident = build_incident("test-causal", obs_list[2], fusion.domain_verdicts, detect_ms=10.0)
    assert incident.causal_graph is not None
    assert len(incident.causal_graph.nodes) >= 4
    assert len(incident.causal_graph.edges) >= 3
    assert incident.causal_graph.primary_root_id is not None
    assert incident.reasoning_summary


def test_deployment_context_enriches_root():
    obs_list = load_observations(SEED)
    root = localize("attack", ["auth failures"])
    enriched = enrich_root_with_deployment(root, obs_list[2])
    assert any("config/" in e or "deploy" in e.lower() for e in enriched.evidence)


def test_risk_planner_graduated_ladder():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    incident = build_incident("test-plan", obs_list[2], fusion.domain_verdicts)
    actions = plan_remediation(incident, causal_graph=incident.causal_graph)
    assert len(actions) >= 2
    grades = [a.grade.value for a in actions]
    assert "observe" in grades
    assert all(a.risk_score >= 0 for a in actions)
    assert all(a.verification_criteria for a in actions)


def test_rca_report_includes_causal_graph():
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    incident = build_incident("test-rca2", obs_list[2], fusion.domain_verdicts)
    md = render_rca_markdown(incident)
    assert "Causal Dependency Graph" in md
    assert "Deployment & Config Context" in md
