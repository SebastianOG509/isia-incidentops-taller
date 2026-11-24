"""Adaptador primario REST (FastAPI). Solo traduce HTTP <-> IncidentService."""

import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Response

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    CreateIncidentRequest,
    HealthResponse,
    IncidentCreatedResponse,
    SLAEvaluationResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.inbound.presenters import (
    health_to_dict,
    registration_to_dict,
    sla_to_dict,
    summary_to_dict,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import (
    IncidentAlreadyExistsError,
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)


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

    @app.post(
        "/api/v1/incidents",
        response_model=IncidentCreatedResponse,
        status_code=201,
        responses={409: {"description": "El incidente ya existe"}},
    )
    def create_incident(request: CreateIncidentRequest) -> IncidentCreatedResponse:
        try:
            registration = service.create_incident(
                title=request.title,
                raw_text=request.raw_text,
                incident_id=request.incident_id,
                created_at=request.created_at,
                status=request.status,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except IncidentAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return IncidentCreatedResponse(**registration_to_dict(registration))

    @app.get(
        "/api/v1/incidents/{incident_id}/sla",
        response_model=SLAEvaluationResponse,
        responses={404: {"description": "El incidente no existe"}},
    )
    def incident_sla(
        incident_id: str, reference_time: Optional[datetime] = None
    ) -> SLAEvaluationResponse:
        try:
            evaluation = service.evaluate_incident_sla(incident_id, reference_time)
        except IncidentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return SLAEvaluationResponse(**sla_to_dict(evaluation))

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Base de datos no disponible"}},
    )
    def health(response: Response) -> HealthResponse:
        healthy = service.check_health()
        if not healthy:
            response.status_code = 503
        return HealthResponse(**health_to_dict(healthy))

    return app


app = create_app()
