"""DTOs Pydantic v2 del adaptador REST."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("no puede estar vacío ni contener solo espacios")
    return value.strip()


class TriageRequest(BaseModel):
    incident_id: str
    raw_text: str

    validate_not_blank = field_validator("incident_id", "raw_text")(_not_blank)


class TriageResponse(BaseModel):
    incident_id: str
    severity: str
    component: str
    recommended_team: str
    duplicate_group_key: str
    rationale: str
    consistency_ratio: float


class ActiveIncidentItem(BaseModel):
    incident_id: str
    title: str
    component: str
    severity: str
    status: str
    elapsed_minutes: int
    allowed_minutes: int
    is_breached: bool
    requires_escalation: bool


class ActiveIncidentsSummaryResponse(BaseModel):
    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentItem]


IncidentStatusName = Literal["OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"]


class CreateIncidentRequest(BaseModel):
    title: str
    raw_text: str
    incident_id: Optional[str] = None
    created_at: Optional[datetime] = None
    status: IncidentStatusName = "OPEN"

    validate_not_blank = field_validator("title", "raw_text")(_not_blank)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _not_blank(value)


class IncidentCreatedResponse(BaseModel):
    incident_id: str
    title: str
    status: str
    created_at: datetime
    severity: str
    component: str
    recommended_team: str
    duplicate_group_key: str
    rationale: str
    is_duplicate: bool
    duplicate_of: list[str]


class SLAEvaluationResponse(BaseModel):
    incident_id: str
    severity: str
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["connected", "unavailable"]
