"""Deterministic replay engine with fusion pipeline and report generation."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.analysis.fusion import fuse_observation
from app.ingestion.csv_adapter import inspect_csv, load_observations
from app.models import Observation, ReplayEvent, Verdict
from app.rca.engine import build_incident
from app.remediation.state_machine import propose_actions
from app.reports.generator import save_incident_report, save_remediation_log
from app.storage.sqlite import Storage


class ReplayEngine:
    def __init__(self, storage: Storage, fixtures_dir: Path):
        self.storage = storage
        self.fixtures_dir = fixtures_dir
        self.observations: list[Observation] = []
        self._subscribers: list[asyncio.Queue] = []
        self._running = False
        self._active_incident_id: str | None = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    async def _emit(self, event: ReplayEvent) -> None:
        self.storage.append_replay_event(event)
        for q in self._subscribers:
            await q.put(event)

    def load_fixture(self, filename: str = "dataset.csv") -> dict:
        path = self.fixtures_dir / filename
        info = inspect_csv(path)
        self.observations = load_observations(path)
        dataset_id = self.storage.import_dataset(info["path"], info["hash"], info["row_count"])
        return {**info, "dataset_id": dataset_id}

    async def replay(self, speed: float = 1.0, step_ms: int = 400):
        if not self.observations:
            self.load_fixture()
        self._running = True
        history: list[Observation] = []
        all_actions = []
        run_incidents = 0
        total = len(self.observations)

        self.storage.reset_for_replay()
        self._active_incident_id = None

        from app.metrics.exporter import record_decomposition, record_fusion, record_live_tick, reset_replay_metrics

        reset_replay_metrics()

        for i, obs in enumerate(self.observations):
            if not self._running:
                break

            await self._emit(
                ReplayEvent(
                    seq=i * 10,
                    event_type="observation",
                    timestamp=obs.timestamp,
                    data={
                        "metrics": obs.metrics,
                        "context": obs.context,
                        "labels": obs.labels,
                        "progress": {"index": i + 1, "total": total},
                    },
                )
            )

            t0 = time.perf_counter()
            fusion = fuse_observation(obs, history)
            history.append(obs)
            detect_ms = (time.perf_counter() - t0) * 1000

            from app.metrics.exporter import record_decomposition, record_fusion, record_live_tick

            record_live_tick(obs, minute_index=i + 1)
            record_decomposition(fusion.domain_verdicts)

            decomp = [
                {
                    "domain": v.domain,
                    "baseline": v.baseline,
                    "context_effect": v.context_effect,
                    "observed": v.observed,
                    "residual": v.residual,
                    "z_score": v.z_score,
                    "verdict": v.verdict.value,
                }
                for v in fusion.domain_verdicts
            ]
            await self._emit(
                ReplayEvent(
                    seq=i * 10 + 1,
                    event_type="decomposition",
                    timestamp=obs.timestamp,
                    data={"domains": decomp},
                )
            )

            unexplained = [v for v in fusion.domain_verdicts if v.verdict == Verdict.UNEXPLAINED]
            await self._emit(
                ReplayEvent(
                    seq=i * 10 + 2,
                    event_type="fusion",
                    timestamp=obs.timestamp,
                    data={
                        "summary": fusion.fusion_summary,
                        "combination": fusion.combination,
                        "primary_verdict": fusion.primary_verdict.value,
                        "alert_domains": fusion.alert_domains,
                        "unexplained_domains": fusion.unexplained_domains,
                        "ml_sources": fusion.ml_sources,
                        "signals": [
                            {
                                "analyzer": s.analyzer,
                                "domain": s.domain,
                                "verdict": s.verdict.value,
                                "confidence": s.confidence,
                                "evidence": s.evidence,
                            }
                            for s in fusion.analyzer_signals
                        ],
                    },
                )
            )

            if unexplained:
                await self._emit(
                    ReplayEvent(
                        seq=i * 10 + 25,
                        event_type="unexplained",
                        timestamp=obs.timestamp,
                        data={
                            "domains": [
                                {"domain": v.domain, "z_score": v.z_score, "reason": v.reason}
                                for v in unexplained
                            ],
                        },
                    )
                )

            await self._emit(
                ReplayEvent(
                    seq=i * 10 + 3,
                    event_type="verdicts",
                    timestamp=obs.timestamp,
                    data={"verdicts": [v.model_dump() for v in fusion.domain_verdicts]},
                )
            )

            alerts = [
                v
                for v in fusion.domain_verdicts
                if v.verdict in (Verdict.ATTACK, Verdict.INTERNAL_FAULT)
            ]

            if not alerts and fusion.primary_verdict == Verdict.EXPECTED:
                suppressed = [v.domain for v in fusion.domain_verdicts if v.verdict == Verdict.EXPECTED]
                await self._emit(
                    ReplayEvent(
                        seq=i * 10 + 4,
                        event_type="suppress",
                        timestamp=obs.timestamp,
                        data={
                            "domains": suppressed,
                            "reason": fusion.fusion_summary,
                            "confidence": max((v.confidence for v in fusion.domain_verdicts), default=0.95),
                        },
                    )
                )

            if alerts:
                if fusion.combination and self._active_incident_id:
                    incident_id = self._active_incident_id
                else:
                    incident_id = f"inc-{obs.source_row:04d}"
                    if fusion.combination:
                        self._active_incident_id = incident_id

                incident = build_incident(
                    incident_id,
                    obs,
                    fusion.domain_verdicts,
                    fusion_summary=fusion.fusion_summary,
                    detect_ms=detect_ms,
                )
                incident.mttr_mitigate_ms = round(detect_ms * 2.2, 2)
                self.storage.save_incident(incident)
                save_incident_report(incident)
                run_incidents += 1

                await self._emit(
                    ReplayEvent(
                        seq=i * 10 + 5,
                        event_type="incident",
                        timestamp=obs.timestamp,
                        data=incident.model_dump(),
                    )
                )

                if incident.causal_graph:
                    await self._emit(
                        ReplayEvent(
                            seq=i * 10 + 55,
                            event_type="causal_graph",
                            timestamp=obs.timestamp,
                            data=incident.causal_graph.model_dump(),
                        )
                    )

                prior = self.storage.feedback_outcomes()
                actions = propose_actions(incident, prior_outcomes=prior)
                for action in actions:
                    self.storage.save_action(action)
                    all_actions.append(action)
                    await self._emit(
                        ReplayEvent(
                            seq=i * 10 + 6,
                            event_type="action",
                            timestamp=obs.timestamp,
                            data=action.model_dump(),
                        )
                    )

            record_fusion(fusion, incident_created=bool(alerts))

            from app.metrics.grafana_annotations import push_alert_annotations

            await push_alert_annotations(
                fusion,
                incident_created=bool(alerts),
                replay_minute=i + 1,
            )

            pause_ms = 0
            if fusion.combination or any(v.verdict == Verdict.ATTACK for v in fusion.domain_verdicts):
                pause_ms = 2200
            elif alerts:
                pause_ms = 600
            elif unexplained:
                pause_ms = 400

            await asyncio.sleep(step_ms / 1000.0 / max(speed, 0.1) + pause_ms / 1000.0)

        if all_actions:
            save_remediation_log(all_actions)

        await self._emit(
            ReplayEvent(
                seq=9999,
                event_type="replay_complete",
                timestamp="",
                data={"total_rows": total, "incidents": run_incidents},
            )
        )
        self._running = False
        self._active_incident_id = None

    def stop(self) -> None:
        self._running = False
