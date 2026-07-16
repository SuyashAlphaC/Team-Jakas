"""Jinja2 RCA and remediation report generation."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config_paths import DATA_DIR
from app.models import Incident, RemediationAction

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
REPORT_DIR = DATA_DIR / "reports"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "md"]),
    )


def render_rca_markdown(incident: Incident) -> str:
    env = _env()
    tpl = env.get_template("rca_report.md.j2")
    return tpl.render(incident=incident)


def render_remediation_markdown(actions: list[RemediationAction]) -> str:
    env = _env()
    tpl = env.get_template("remediation_log.md.j2")
    return tpl.render(actions=actions)


def save_incident_report(incident: Incident) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{incident.incident_id}_rca.md"
    path.write_text(render_rca_markdown(incident), encoding="utf-8")
    return path


def save_remediation_log(actions: list[RemediationAction]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "remediation_log.md"
    path.write_text(render_remediation_markdown(actions), encoding="utf-8")
    return path
