"""
Dashboard API — exposes the four-dimension metrics as JSON for the dashboard
frontend. Reads from the standardized telemetry log, so it is model-agnostic.
"""
from __future__ import annotations

from typing import Optional

from .metrics import MetricsEngine


def build_dashboard_payload(engine: Optional[MetricsEngine] = None) -> dict:
    engine = engine or MetricsEngine()
    report = engine.full_report()
    return {
        "dimensions": {
            "business": report["business"],
            "performance": report["performance"],
            "costs": report["costs"],
            "orchestration": report["orchestration"],
        },
        "generated_at": report["generated_at"],
        "event_count": report["event_count"],
    }
