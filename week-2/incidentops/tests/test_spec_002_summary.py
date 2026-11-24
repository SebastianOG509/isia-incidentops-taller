"""Pruebas de aceptación de specs/002-active-incidents-summary/spec.md."""

import json
from datetime import datetime

from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident

REFERENCE = "2026-11-09T12:00:00"  # lunes


def _seed(repository) -> None:
    """Given común: P0 abierto, P2 en progreso, P1 resuelto y uno escalado (no activo)."""
    for incident in (
        Incident("INC-A1", "Caída de cobros", "payments-gateway", "P0", "OPEN",
                 datetime(2026, 11, 9, 8, 0)),
        Incident("INC-A2", "Exportación lenta", "reporting-api", "P2", "IN_PROGRESS",
                 datetime(2026, 11, 9, 10, 0)),
        Incident("INC-A3", "Timeouts BD", "database-cluster", "P1", "RESOLVED",
                 datetime(2026, 11, 9, 7, 0), resolved_at=datetime(2026, 11, 9, 9, 0)),
        Incident("INC-A4", "Fuga de datos", "auth-identity", "P0", "ESCALATION_REQUIRED",
                 datetime(2026, 11, 9, 9, 0)),
    ):
        repository.save_incident(incident)


def test_bdd_escenario_1_resumen_global_excluye_resueltos(client, service):
    _seed(service.repository)

    response = client.get("/api/v1/incidents/summary", params={"reference_time": REFERENCE})

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 2
    assert body["breached_count"] == 1
    by_id = {item["incident_id"]: item for item in body["incidents"]}
    assert set(by_id) == {"INC-A1", "INC-A2"}  # sin RESOLVED ni ESCALATION_REQUIRED
    assert by_id["INC-A1"]["elapsed_minutes"] == 240
    assert by_id["INC-A1"]["is_breached"] is True
    assert by_id["INC-A1"]["requires_escalation"] is True


def test_bdd_escenario_2_filtro_por_componente(client, service):
    _seed(service.repository)

    response = client.get(
        "/api/v1/incidents/summary",
        params={"component": "reporting-api", "reference_time": REFERENCE},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["total_active"] == 1
    assert body["breached_count"] == 0
    assert body["incidents"][0]["incident_id"] == "INC-A2"
    assert body["incidents"][0]["elapsed_minutes"] == 120


def test_bdd_escenario_3_resumen_vacio(client, service):
    _seed(service.repository)

    response = client.get(
        "/api/v1/incidents/summary",
        params={"component": "frontend-ui", "reference_time": REFERENCE},
    )

    assert response.status_code == 200
    assert response.json() == {"total_active": 0, "breached_count": 0, "incidents": []}


def test_bdd_escenario_4_paridad_cli(runner, client, service, file_db_url):
    _seed(create_repository(file_db_url))
    _seed(service.repository)
    api_body = client.get(
        "/api/v1/incidents/summary", params={"reference_time": REFERENCE}
    ).json()

    result = runner.invoke(
        cli_app, ["summary", "--reference-time", REFERENCE], env={"DATABASE_URL": file_db_url}
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == api_body


def test_sqlite_cumple_incident_repository_port():
    assert isinstance(SQLiteIncidentRepository(":memory:"), IncidentRepositoryPort)
