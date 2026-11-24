"""Serialización compartida por los adaptadores primarios (garantiza paridad REST/CLI)."""

from dataclasses import asdict

from src.application.services import ActiveIncidentsSummary, IncidentRegistration
from src.domain.models import SLAEvaluation


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


def registration_to_dict(registration: IncidentRegistration) -> dict:
    incident, triage = registration.incident, registration.triage
    return {
        "incident_id": incident.incident_id,
        "title": incident.title,
        "status": incident.status,
        "created_at": incident.created_at.isoformat(),
        "severity": triage.severity,
        "component": triage.component,
        "recommended_team": triage.recommended_team,
        "duplicate_group_key": triage.duplicate_group_key,
        "rationale": triage.rationale,
        "is_duplicate": registration.is_duplicate,
        "duplicate_of": list(registration.duplicate_of),
    }


def sla_to_dict(evaluation: SLAEvaluation) -> dict:
    return asdict(evaluation)
