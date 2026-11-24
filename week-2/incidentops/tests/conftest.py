"""Fixtures compartidas para las pruebas de aceptación BDD (almacenamiento aislado por prueba)."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService


@pytest.fixture
def service() -> IncidentService:
    """Servicio sobre SQLite `:memory:` nuevo en cada prueba."""
    return IncidentService(create_repository("sqlite:///:memory:"))


@pytest.fixture
def client(service: IncidentService) -> TestClient:
    return TestClient(create_app(service))


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def file_db_url(tmp_path) -> str:
    """URL SQLite en archivo temporal: permite compartir datos entre el Given y un proceso CLI."""
    return f"sqlite:///{(tmp_path / 'incidentops.db').as_posix()}"
