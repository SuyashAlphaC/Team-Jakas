"""Prometheus alert metrics exported from model fusion."""

from prometheus_client import generate_latest

from app.analysis.fusion import fuse_observation
from app.ingestion.csv_adapter import load_observations
from app.metrics.exporter import record_fusion, reset_alert_metrics
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SEED = FIXTURES / "dataset_seed.csv"


def test_fusion_exports_attack_metrics():
    reset_alert_metrics()
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[2], obs_list[:2])
    record_fusion(fusion, incident_created=True)
    body = generate_latest().decode()
    assert 'observability_domain_alert_active{domain="security",verdict="attack"} 1.0' in body
    assert 'observability_domain_alert_active{domain="process",verdict="internal_fault"} 1.0' in body
    assert "observability_fusion_combination 1.0" in body
    assert "observability_incidents_created_total" in body


def test_expected_minute_clears_fusion_alert():
    reset_alert_metrics()
    obs_list = load_observations(SEED)
    fusion = fuse_observation(obs_list[1], obs_list[:1])
    record_fusion(fusion)
    body = generate_latest().decode()
    assert "observability_fusion_alert_active 0.0" in body
