"""Casos de uso compartidos de IncidentOps.

Todos los adaptadores primarios (API REST, CLI y futuros como MCP) invocan estos métodos;
ninguna regla de negocio vive fuera de `src.domain`.
"""

from src.domain.models import TriageResult
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Entrada de negocio inválida (campos obligatorios vacíos o solo espacios)."""


def _require_text(value: str, field_name: str) -> str:
    if value is None or not value.strip():
        raise ValidationError(f"El campo '{field_name}' es obligatorio y no puede estar vacío.")
    return value.strip()


class IncidentService:
    """Fachada de casos de uso de incidentes."""

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Clasifica un reporte sin persistirlo (Hito 001)."""
        clean_id = _require_text(incident_id, "incident_id")
        clean_text = _require_text(raw_text, "raw_text")
        return classify_incident_report(clean_id, clean_text)
