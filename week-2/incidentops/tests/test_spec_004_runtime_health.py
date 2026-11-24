"""Pruebas de aceptación de specs/004-postgres-container-runtime/spec.md.

Corren sin daemon Docker (RNF-001). La prueba de contrato contra un PostgreSQL real solo se
ejecuta si se define `TEST_POSTGRES_URL` (p. ej. con `docker compose up db`).
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNREACHABLE_PG = "postgresql://incidentops:incidentops@127.0.0.1:1/incidentops"


class FailingRepository(SQLiteIncidentRepository):
    """Doble de prueba: persistencia cuyo chequeo de salud falla."""

    def check_health(self) -> bool:
        return False


# --- Escenario 1: salud operativa ------------------------------------------------
def test_bdd_escenario_1_health_operativo_api(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_bdd_escenario_1_health_operativo_cli(runner):
    result = runner.invoke(cli_app, ["health"], env={"DATABASE_URL": "sqlite:///:memory:"})

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "database": "connected"}


# --- Escenario 2: fallo de conectividad -------------------------------------------
def test_bdd_escenario_2_health_503_con_doble_de_prueba():
    client = TestClient(create_app(IncidentService(FailingRepository(":memory:"))))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_bdd_escenario_2_health_cli_sale_con_1_si_la_base_no_responde(runner):
    result = runner.invoke(cli_app, ["health"], env={"DATABASE_URL": UNREACHABLE_PG})

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"status": "error", "database": "unavailable"}


def test_postgres_inalcanzable_se_reporta_en_menos_de_5_segundos():
    started = time.monotonic()
    healthy = PostgresIncidentRepository(UNREACHABLE_PG).check_health()

    assert healthy is False
    assert time.monotonic() - started < 5  # SC-001


# --- Escenario 3: selección transparente por DATABASE_URL --------------------------
@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (None, SQLiteIncidentRepository),
        ("", SQLiteIncidentRepository),
        ("sqlite:///:memory:", SQLiteIncidentRepository),
        ("postgresql://u:p@db:5432/incidentops", PostgresIncidentRepository),
        ("postgres://u:p@db:5432/incidentops", PostgresIncidentRepository),
    ],
)
def test_bdd_escenario_3_seleccion_de_motor_por_database_url(database_url, expected):
    repository = create_repository(database_url)

    assert isinstance(repository, expected)
    assert isinstance(repository, IncidentRepositoryPort)


def test_bdd_escenario_3_esquema_no_soportado_falla_al_arrancar():
    with pytest.raises(ValueError, match="no soportada"):
        create_repository("mysql://u:p@db/incidentops")


def test_ambos_adaptadores_exponen_exactamente_las_operaciones_del_puerto():
    port_methods = {
        name for name in vars(IncidentRepositoryPort)
        if not name.startswith("_") and callable(getattr(IncidentRepositoryPort, name))
    }
    assert port_methods == {
        "save_incident", "get_incident", "find_open_duplicates",
        "list_active_incidents", "check_health",
    }
    for adapter in (SQLiteIncidentRepository, PostgresIncidentRepository):
        assert port_methods <= set(dir(adapter)), adapter.__name__


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="requiere TEST_POSTGRES_URL")
def test_contrato_postgres_real_paridad_temporal_y_duplicados():
    repository = PostgresIncidentRepository(os.environ["TEST_POSTGRES_URL"])
    service = IncidentService(repository)
    suffix = datetime.now().strftime("%H%M%S%f")
    created = datetime(2026, 11, 6, 17, 0)

    first = service.create_incident(
        "Cuenta bloqueada", "mi cuenta aparece bloqueada", incident_id=f"INC-PG{suffix}",
        created_at=created,
    )
    assert repository.check_health() is True
    assert repository.get_incident(first.incident.incident_id).created_at == created
    evaluation = service.evaluate_incident_sla(
        first.incident.incident_id, datetime(2026, 11, 9, 9, 0)
    )
    assert evaluation.elapsed_minutes == 120
    second = service.create_incident("Otra", "mi cuenta aparece bloqueada")
    assert first.incident.incident_id in second.duplicate_of
    repository.save_incident(
        Incident(**{**vars(first.incident), "status": "RESOLVED"})
    )
    repository.save_incident(Incident(**{**vars(second.incident), "status": "RESOLVED"}))


# --- Escenario 4: orquestación reproducible en 2 contenedores -----------------------
def test_bdd_escenario_4_estructura_de_archivos_docker():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    for excluded in (".venv/", "__pycache__", "*.db", ".git/"):
        assert excluded in dockerignore
    for expected in (
        "db:", "image: postgres:16-alpine", "pgdata:/var/lib/postgresql/data", "pg_isready",
        "api:", "DATABASE_URL: postgresql://incidentops:incidentops@db:5432/incidentops",
        "condition: service_healthy", "http://localhost:8000/health",
    ):
        assert expected in compose, expected
