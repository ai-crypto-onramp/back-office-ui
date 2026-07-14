"""Health sidecar: FastAPI app exposing /healthz and /readyz.

Streamlit serves the UI on port 8501; this module runs alongside it
(or as a separate container process) on port 8080 so gatus and
docker-compose healthchecks can probe it. Run with:

    uvicorn back_office_ui.health_server:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI

from .health import READINESS_CHECKS, classify_readiness, readiness_report

app = FastAPI(title="Back Office UI — Health")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    results, failed, total = readiness_report()
    status_code, status = classify_readiness(failed, total)
    return {
        "status": status,
        "ready": failed == 0,
        "healthy": str(total - failed),
        "failed": str(failed),
        "total": str(total),
        **{name: state for name, state in results.items()},
    }


def _checks_names() -> list[str]:
    return [name for name, _ in READINESS_CHECKS]
