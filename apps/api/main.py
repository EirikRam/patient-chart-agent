from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from apps.api.routers.analyze import router as analyze_router
from packages.risklib.rules import discover_rules

app = FastAPI(title="Patient Chart Agent API")
app.include_router(analyze_router)

@app.get("/")
def root() -> dict:
    return {
        "name": "patient-chart-agent",
        "status": "ok",
        "endpoints": ["/healthz", "/readyz", "/v1/analyze"],
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> JSONResponse:
    try:
        discover_rules()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})
    return JSONResponse(status_code=200, content={"status": "ok"})


__all__ = ["app"]