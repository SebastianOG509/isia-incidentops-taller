"""Casos de uso compartidos de IncidentOps.

Todos los adaptadores primarios (API REST, CLI y futuros como MCP) invocan estos métodos;
ninguna regla de negocio vive fuera de `src.domain`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident, SLAEvaluation, TriageResult
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Entrada de negocio inválida (campos obligatorios vacíos o solo espacios)."""


@dataclass(frozen=True)
class IncidentSummaryItem:
    incident: Incident
    evaluation: SLAEvaluation


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    total_active: int
    breached_count: int
    incidents: list[IncidentSummaryItem]


def _require_text(value: str, field_name: str) -> str:
    if value is None or not value.strip():
        raise ValidationError(f"El campo '{field_name}' es obligatorio y no puede estar vacío.")
    return value.strip()


class IncidentService:
    """Fachada de casos de uso de incidentes."""

    def __init__(self, repository: IncidentRepositoryPort) -> None:
        self.repository = repository

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Clasifica un reporte sin persistirlo (Hito 001)."""
        clean_id = _require_text(incident_id, "incident_id")
        clean_text = _require_text(raw_text, "raw_text")
        return classify_incident_report(clean_id, clean_text)

    def get_active_incidents_summary(
        self,
        component_filter: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ActiveIncidentsSummary:
        """Resume los incidentes OPEN/IN_PROGRESS con su evaluación de SLA (Hito 002)."""
        reference = reference_time or datetime.now()
        component = component_filter.strip() if component_filter else None
        items = [
            IncidentSummaryItem(incident, evaluate_sla_status(incident, reference))
            for incident in self.repository.list_active_incidents(component or None)
        ]
        return ActiveIncidentsSummary(
            total_active=len(items),
            breached_count=sum(1 for item in items if item.evaluation.is_breached),
            incidents=items,
        )
