"""Context Intelligence Service — event calendar → context multiplier vector."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from app.config_paths import CONFIG_DIR


@dataclass
class ContextVector:
    ingress_multiplier: float = 1.0
    transaction_multiplier: float = 1.0
    identity_multiplier: float = 1.0
    event_id: str = ""
    confidence: float = 0.95

    def as_dict(self) -> dict[str, float]:
        return {
            "ingress_multiplier": self.ingress_multiplier,
            "transaction_multiplier": self.transaction_multiplier,
            "identity_multiplier": self.identity_multiplier,
        }


class ContextIntelligenceService:
    """CIS: merges CSV context with optional calendar config."""

    def __init__(self) -> None:
        self._calendar: list[dict] = []
        cal_path = CONFIG_DIR / "event-calendar.yml"
        if cal_path.exists():
            with cal_path.open() as f:
                data = yaml.safe_load(f) or {}
                self._calendar = data.get("events", [])

    def from_observation_context(self, context: dict[str, float]) -> ContextVector:
        return ContextVector(
            ingress_multiplier=float(context.get("ingress_multiplier", 1.0)),
            transaction_multiplier=float(context.get("transaction_multiplier", 1.0)),
            identity_multiplier=float(context.get("identity_multiplier", 1.0)),
            event_id=context.get("event_id", ""),
            confidence=0.95,
        )

    def enrich(self, context: dict[str, float]) -> ContextVector:
        """Return CIS vector; CSV ctx columns are authoritative for demo replay."""
        return self.from_observation_context(context)


cis = ContextIntelligenceService()
