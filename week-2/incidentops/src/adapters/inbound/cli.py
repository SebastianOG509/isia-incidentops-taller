"""Adaptador primario CLI (Typer). Paridad con la API: invoca los mismos casos de uso."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional

import typer

from src.adapters.inbound.presenters import summary_to_dict
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError

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


@app.callback()
def main() -> None:
    """IncidentOps: triaje y SLA de incidentes desde la terminal."""


if __name__ == "__main__":
    app()
