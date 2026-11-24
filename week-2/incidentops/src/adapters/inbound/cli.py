"""Adaptador primario CLI (Typer). Paridad con la API: invoca los mismos casos de uso."""

import json
from dataclasses import asdict

import typer

from src.application.services import IncidentService, ValidationError

app = typer.Typer(help="IncidentOps CLI", no_args_is_help=True)


def _service() -> IncidentService:
    return IncidentService()


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


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


@app.callback()
def main() -> None:
    """IncidentOps: triaje y SLA de incidentes desde la terminal."""


if __name__ == "__main__":
    app()
