"""Alertmanager webhook receiver.

Alertmanager posts firing alerts here; each one runs the incident
graph. Serve with: uvicorn kubmedic_agent.webhook:create_app --factory
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident


class AlertmanagerPayload(BaseModel):
    alerts: list[dict] = []


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    app = FastAPI(title="KubeMedic", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": config.model}

    @app.post("/alerts")
    def alerts(payload: AlertmanagerPayload) -> dict:
        results = []
        for alert in payload.alerts:
            if alert.get("status", "firing") != "firing":
                continue
            flat = {
                "alertname": alert.get("labels", {}).get("alertname", "unknown"),
                "labels": alert.get("labels", {}),
                "annotations": alert.get("annotations", {}),
            }
            state = run_incident(config, flat)
            results.append(
                {
                    "alert": flat["alertname"],
                    "status": state.get("status"),
                    "diagnosis": state.get("diagnosis"),
                    "pr": (state.get("pr") or {}).get("branch"),
                    "error": state.get("error"),
                }
            )
        return {"handled": len(results), "results": results}

    return app
