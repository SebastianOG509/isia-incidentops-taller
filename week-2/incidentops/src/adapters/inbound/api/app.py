"""Adaptador primario REST (FastAPI). Solo traduce HTTP <-> IncidentService."""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from src.adapters.inbound.api.schemas import TriageRequest, TriageResponse
from src.application.services import IncidentService, ValidationError


def create_app(service: IncidentService | None = None) -> FastAPI:
    service = service or IncidentService()
    app = FastAPI(title="IncidentOps API", version="0.2.0")

    @app.post("/api/v1/incidents/triage", response_model=TriageResponse)
    def triage(request: TriageRequest) -> TriageResponse:
        try:
            result = service.triage_incident(request.incident_id, request.raw_text)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return TriageResponse(**asdict(result))

    return app


app = create_app()
