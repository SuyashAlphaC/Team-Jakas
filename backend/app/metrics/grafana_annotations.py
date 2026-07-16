"""Push dotted vertical-line annotations to Grafana when the model predicts alerts."""

from __future__ import annotations

import logging
import os
import time

import httpx

from app.analysis.fusion import FusionResult
from app.models import Verdict

logger = logging.getLogger(__name__)

GRAFANA_URL = os.environ.get("GRAFANA_INTERNAL_URL", "http://grafana:3000")
GRAFANA_USER = os.environ.get("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASS = os.environ.get("GRAFANA_ADMIN_PASSWORD", "observability")
DASHBOARD_UID = "domain-cpu-telemetry"
PANEL_ID = 9

_VERDICT_COLORS = {
    "attack": "rgba(244, 33, 46, 1)",
    "internal_fault": "rgba(255, 173, 31, 1)",
    "unexplained": "rgba(120, 86, 255, 1)",
    "combination": "rgba(255, 0, 128, 1)",
    "incident": "rgba(0, 186, 124, 1)",
}


async def push_alert_annotations(
    fusion: FusionResult,
    *,
    incident_created: bool = False,
    replay_minute: int | None = None,
) -> None:
    """Create Grafana annotations (dashed vertical markers) for each model alert."""
    if not os.environ.get("GRAFANA_ANNOTATIONS_ENABLED", "true").lower() in ("1", "true", "yes"):
        return

    t_ms = int(time.time() * 1000)
    minute_label = f"min {replay_minute}" if replay_minute else "live"
    payloads: list[dict] = []

    for v in fusion.domain_verdicts:
        if v.verdict.value not in ("attack", "internal_fault", "unexplained"):
            continue
        payloads.append(
            {
                "dashboardUID": DASHBOARD_UID,
                "panelId": PANEL_ID,
                "time": t_ms,
                "timeEnd": t_ms,
                "tags": [v.verdict.value, v.domain, "model-alert"],
                "text": f"{minute_label} · {v.domain}: {v.verdict.value} ({v.confidence:.0%}) — {v.reason[:120]}",
            }
        )

    if fusion.combination:
        payloads.append(
            {
                "dashboardUID": DASHBOARD_UID,
                "panelId": PANEL_ID,
                "time": t_ms,
                "timeEnd": t_ms,
                "tags": ["combination", "attack", "internal_fault", "model-alert"],
                "text": f"{minute_label} · COMBINATION ★ — {fusion.fusion_summary[:160]}",
            }
        )

    if incident_created:
        kind = "combination" if fusion.combination else (
            "attack" if any(v.verdict == Verdict.ATTACK for v in fusion.domain_verdicts) else "internal_fault"
        )
        payloads.append(
            {
                "dashboardUID": DASHBOARD_UID,
                "panelId": PANEL_ID,
                "time": t_ms,
                "timeEnd": t_ms,
                "tags": ["incident", kind, "model-alert"],
                "text": f"{minute_label} · Incident opened ({kind}) — RCA + remediation proposed",
            }
        )

    if not payloads:
        return

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            for body in payloads:
                resp = await client.post(
                    f"{GRAFANA_URL}/api/annotations",
                    auth=(GRAFANA_USER, GRAFANA_PASS),
                    json=body,
                )
                if resp.status_code >= 400:
                    logger.warning("Grafana annotation failed: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.debug("Grafana annotations unavailable: %s", exc)
