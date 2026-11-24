"""Adaptador primario REST (FastAPI). Solo traduce HTTP <-> IncidentService."""

import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.inbound.presenters import summary_to_dict
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError


def build_default_service() -> IncidentService:
    return IncidentService(create_repository(os.getenv("DATABASE_URL")))


def create_app(service: Optional[IncidentService] = None) -> FastAPI:
    service = service or build_default_service()
    app = FastAPI(title="IncidentOps API", version="0.2.0")

    @app.post("/api/v1/incidents/triage", response_model=TriageResponse)
    def triage(request: TriageRequest) -> TriageResponse:
        try:
            result = service.triage_incident(request.incident_id, request.raw_text)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return TriageResponse(**asdict(result))

    @app.get("/api/v1/incidents/summary", response_model=ActiveIncidentsSummaryResponse)
    def summary(
        component: Optional[str] = None, reference_time: Optional[datetime] = None
    ) -> ActiveIncidentsSummaryResponse:
        result = service.get_active_incidents_summary(component, reference_time)
        return ActiveIncidentsSummaryResponse(**summary_to_dict(result))

    return app


app = create_app()
