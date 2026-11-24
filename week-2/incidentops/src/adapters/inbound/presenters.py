"""Serialización compartida por los adaptadores primarios (garantiza paridad REST/CLI)."""

from src.application.services import ActiveIncidentsSummary


def summary_to_dict(summary: ActiveIncidentsSummary) -> dict:
    return {
        "total_active": summary.total_active,
        "breached_count": summary.breached_count,
        "incidents": [
            {
                "incident_id": item.incident.incident_id,
                "title": item.incident.title,
                "component": item.incident.component,
                "severity": item.incident.severity,
                "status": item.incident.status,
                "elapsed_minutes": item.evaluation.elapsed_minutes,
                "allowed_minutes": item.evaluation.allowed_minutes,
                "is_breached": item.evaluation.is_breached,
                "requires_escalation": item.evaluation.requires_escalation,
            }
            for item in summary.incidents
        ],
    }
