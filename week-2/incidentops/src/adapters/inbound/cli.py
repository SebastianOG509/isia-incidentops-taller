"""Adaptador primario CLI (Typer). Paridad con la API: invoca los mismos casos de uso."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional

import typer

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

app = typer.Typer(help="IncidentOps CLI", no_args_is_help=True)


def _service() -> IncidentService:
    return IncidentService(create_repository(os.getenv("DATABASE_URL")))


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _parse_datetime(value: Optional[str], option: str) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _fail(f"{option} debe ser una fecha ISO 8601 válida: {value!r}")


@app.command()
def triage(
    incident_id: str = typer.Option(..., "--incident-id", help="Identificador del reporte"),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto libre del reporte"),
) -> None:
    """Clasifica un reporte sin persistirlo e imprime el resultado en JSON."""
    try:
        result = _service().triage_incident(incident_id, raw_text)
    except ValidationError as exc:
        _fail(str(exc))
    _emit(asdict(result))


@app.command()
def summary(
    component: Optional[str] = typer.Option(None, "--component", help="Filtrar por componente"),
    reference_time: Optional[str] = typer.Option(
        None, "--reference-time", help="Instante ISO 8601 de evaluación (por defecto: ahora)"
    ),
) -> None:
    """Resume los incidentes activos (OPEN/IN_PROGRESS) con su SLA."""
    reference = _parse_datetime(reference_time, "--reference-time")
    result = _service().get_active_incidents_summary(component, reference)
    _emit(summary_to_dict(result))


@app.command()
def create(
    title: str = typer.Option(..., "--title", help="Título del incidente"),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto libre del reporte"),
    incident_id: Optional[str] = typer.Option(
        None, "--incident-id", help="Identificador (por defecto INC-<HEX8>)"
    ),
    created_at: Optional[str] = typer.Option(
        None, "--created-at", help="Creación ISO 8601 (por defecto: ahora)"
    ),
    status: str = typer.Option("OPEN", "--status", help="Estado inicial"),
) -> None:
    """Registra un incidente clasificado e informa si duplica uno abierto."""
    created = _parse_datetime(created_at, "--created-at")
    try:
        registration = _service().create_incident(
            title=title, raw_text=raw_text, incident_id=incident_id,
            created_at=created, status=status,
        )
    except (ValidationError, IncidentAlreadyExistsError) as exc:
        _fail(str(exc))
    _emit(registration_to_dict(registration))


@app.command()
def sla(
    incident_id: str = typer.Argument(..., help="Identificador del incidente"),
    reference_time: Optional[str] = typer.Option(
        None, "--reference-time", help="Instante ISO 8601 de evaluación (por defecto: ahora)"
    ),
) -> None:
    """Audita el SLA de un incidente registrado."""
    reference = _parse_datetime(reference_time, "--reference-time")
    try:
        evaluation = _service().evaluate_incident_sla(incident_id, reference)
    except (IncidentNotFoundError, ValidationError) as exc:
        _fail(str(exc))
    _emit(sla_to_dict(evaluation))


@app.command()
def health() -> None:
    """Chequeo real de conectividad con la base configurada (exit 0 sano / 1 no disponible)."""
    healthy = _service().check_health()
    _emit(health_to_dict(healthy))
    if not healthy:
        raise typer.Exit(code=1)


@app.callback()
def main() -> None:
    """IncidentOps: triaje y SLA de incidentes desde la terminal."""


if __name__ == "__main__":
    app()
