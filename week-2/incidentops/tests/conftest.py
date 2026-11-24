"""Fixtures compartidas para las pruebas de aceptación BDD."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.application.services import IncidentService


@pytest.fixture
def service() -> IncidentService:
    return IncidentService()


@pytest.fixture
def client(service: IncidentService) -> TestClient:
    return TestClient(create_app(service))


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
