"""Casos de uso compartidos de IncidentOps.

Todos los adaptadores primarios (API REST, CLI y futuros como MCP) invocan estos métodos;
ninguna regla de negocio vive fuera de `src.domain`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.application.ports import IncidentRepositoryPort
from src.domain.models import INCIDENT_STATUSES, Incident, SLAEvaluation, TriageResult
from src.domain.sla_calculator import evaluate_sla_status, normalize_timestamp, now_local
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Entrada de negocio inválida."""


class IncidentNotFoundError(LookupError):
    """El incidente solicitado no existe."""


class IncidentAlreadyExistsError(ValueError):
    """Se intentó registrar un identificador que ya existe."""


@dataclass(frozen=True)
class IncidentSummaryItem:
    incident: Incident
    evaluation: SLAEvaluation


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    total_active: int
    breached_count: int
    incidents: list[IncidentSummaryItem]


@dataclass(frozen=True)
class IncidentRegistration:
    incident: Incident
    triage: TriageResult
    is_duplicate: bool
    duplicate_of: list[str]


def _require_text(value: Optional[str], field_name: str) -> str:
    if value is None or not value.strip():
        raise ValidationError(f"El campo '{field_name}' es obligatorio y no puede estar vacío.")
    return value.strip()


def _generate_incident_id() -> str:
    return f"INC-{uuid.uuid4().hex[:8].upper()}"


class IncidentService:
    """Fachada de casos de uso de incidentes."""

    def __init__(self, repository: IncidentRepositoryPort) -> None:
        self.repository = repository

    # --- Hito 001 -----------------------------------------------------------------
    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Clasifica un reporte sin persistirlo."""
        clean_id = _require_text(incident_id, "incident_id")
        clean_text = _require_text(raw_text, "raw_text")
        return classify_incident_report(clean_id, clean_text)

    # --- Hito 002 -----------------------------------------------------------------
    def get_active_incidents_summary(
        self,
        component_filter: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ActiveIncidentsSummary:
        """Resume los incidentes OPEN/IN_PROGRESS con su evaluación de SLA."""
        reference = reference_time or now_local()
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

    # --- Hito 003 -----------------------------------------------------------------
    def create_incident(
        self,
        title: str,
        raw_text: str,
        incident_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> IncidentRegistration:
        """Registra un incidente clasificado y detecta equivalentes abiertos."""
        clean_title = _require_text(title, "title")
        clean_text = _require_text(raw_text, "raw_text")
        clean_id = (
            _require_text(incident_id, "incident_id")
            if incident_id is not None
            else _generate_incident_id()
        )
        clean_status = status or "OPEN"
        if clean_status not in INCIDENT_STATUSES:
            raise ValidationError(
                f"Estado inválido {clean_status!r}; válidos: {', '.join(INCIDENT_STATUSES)}."
            )
        if self.repository.get_incident(clean_id) is not None:
            raise IncidentAlreadyExistsError(f"El incidente {clean_id} ya existe.")

        triage = classify_incident_report(clean_id, clean_text)
        incident = Incident(
            incident_id=clean_id,
            title=clean_title,
            component=triage.component,
            severity=triage.severity,
            status=clean_status,
            created_at=normalize_timestamp(created_at) if created_at else now_local(),
            recommended_team=triage.recommended_team,
            duplicate_group_key=triage.duplicate_group_key,
        )
        duplicates = self.repository.find_open_duplicates(
            triage.duplicate_group_key, exclude_incident_id=clean_id
        )
        self.repository.save_incident(incident)
        duplicate_ids = [dup.incident_id for dup in duplicates]
        return IncidentRegistration(
            incident=incident,
            triage=triage,
            is_duplicate=bool(duplicate_ids),
            duplicate_of=duplicate_ids,
        )

    def evaluate_incident_sla(
        self, incident_id: str, reference_time: Optional[datetime] = None
    ) -> SLAEvaluation:
        """Audita el SLA de un incidente registrado en un instante de referencia."""
        incident = self.repository.get_incident(_require_text(incident_id, "incident_id"))
        if incident is None:
            raise IncidentNotFoundError(f"El incidente {incident_id} no existe.")
        try:
            return evaluate_sla_status(incident, reference_time or now_local())
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
