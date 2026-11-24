"""DTOs Pydantic v2 del adaptador REST."""

from pydantic import BaseModel, field_validator


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("no puede estar vacío ni contener solo espacios")
    return value.strip()


class TriageRequest(BaseModel):
    incident_id: str
    raw_text: str

    _validate = field_validator("incident_id", "raw_text")(_not_blank)


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
