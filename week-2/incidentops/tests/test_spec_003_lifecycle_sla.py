"""Pruebas de aceptación de specs/003-incident-lifecycle-sla/spec.md."""

import json
import re
from datetime import datetime

from src.adapters.inbound.cli import app as cli_app

PAYMENTS_OUTAGE = (
    "La pasarela de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones"
)
ACCOUNT_LOCKED = (
    "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. "
    "Necesito acceder hoy mismo."
)
FRIDAY_17 = "2026-11-06T17:00:00"
MONDAY_09 = "2026-11-09T09:00:00"


def test_bdd_escenario_1_registro_inicial_sin_duplicados(client):
    response = client.post(
        "/api/v1/incidents", json={"title": "Caída de cobros", "raw_text": PAYMENTS_OUTAGE}
    )

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"INC-[0-9A-F]{8}", body["incident_id"])
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["status"] == "OPEN"
    assert body["is_duplicate"] is False
    assert body["duplicate_of"] == []


def test_bdd_escenario_1b_entradas_invalidas_y_id_repetido(client, service):
    blank_title = client.post("/api/v1/incidents", json={"title": "   ", "raw_text": "x"})
    blank_text = client.post("/api/v1/incidents", json={"title": "t", "raw_text": ""})
    bad_status = client.post(
        "/api/v1/incidents", json={"title": "t", "raw_text": "x", "status": "CLOSED"}
    )
    assert (blank_title.status_code, blank_text.status_code, bad_status.status_code) == (
        422, 422, 422,
    )
    assert service.repository.list_active_incidents() == []

    payload = {"incident_id": "INC-1001", "title": "Cobros", "raw_text": PAYMENTS_OUTAGE}
    assert client.post("/api/v1/incidents", json=payload).status_code == 201
    conflict = client.post("/api/v1/incidents", json={**payload, "title": "Otro"})
    assert conflict.status_code == 409
    assert service.repository.get_incident("INC-1001").title == "Cobros"


def test_bdd_escenario_2_duplicado_abierto_ignora_resueltos(client, service):
    service.create_incident("Cobros caídos", PAYMENTS_OUTAGE, incident_id="INC-OPEN-01")
    service.create_incident(
        "Cobros caídos (ayer)", PAYMENTS_OUTAGE, incident_id="INC-RES-01", status="RESOLVED"
    )

    response = client.post(
        "/api/v1/incidents", json={"title": "Otra vez cobros", "raw_text": PAYMENTS_OUTAGE}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_duplicate"] is True
    assert body["duplicate_of"] == ["INC-OPEN-01"]


def test_bdd_escenario_3_auditoria_sla_horario_habil(client, service):
    service.create_incident(
        "Cuenta bloqueada", ACCOUNT_LOCKED, incident_id="INC-P2-0001",
        created_at=datetime.fromisoformat(FRIDAY_17),
    )

    response = client.get(
        "/api/v1/incidents/INC-P2-0001/sla", params={"reference_time": MONDAY_09}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P2"
    assert body["elapsed_minutes"] == 120
    assert body["allowed_minutes"] == 480
    assert body["remaining_minutes"] == 360
    assert body["is_breached"] is False
    assert body["requires_escalation"] is False


def test_bdd_escenario_4_sla_inexistente_404_y_tiempo_anterior_422(client, service):
    service.create_incident(
        "Cuenta bloqueada", ACCOUNT_LOCKED, incident_id="INC-P2-0001",
        created_at=datetime.fromisoformat(FRIDAY_17),
    )

    missing = client.get("/api/v1/incidents/INC-NOPE0000/sla")
    before_creation = client.get(
        "/api/v1/incidents/INC-P2-0001/sla", params={"reference_time": "2026-11-06T16:00:00"}
    )

    assert missing.status_code == 404
    assert before_creation.status_code == 422


def test_bdd_escenario_5_paridad_cli_create_y_sla(runner, file_db_url):
    env = {"DATABASE_URL": file_db_url}
    created = runner.invoke(
        cli_app,
        ["create", "--incident-id", "INC-CLI00001", "--title", "Cuenta bloqueada",
         "--raw-text", ACCOUNT_LOCKED, "--created-at", FRIDAY_17],
        env=env,
    )
    assert created.exit_code == 0, created.output
    created_body = json.loads(created.stdout)
    assert created_body["severity"] == "P2"
    assert created_body["recommended_team"] == "Security-IAM"
    assert created_body["is_duplicate"] is False

    audited = runner.invoke(
        cli_app, ["sla", "INC-CLI00001", "--reference-time", MONDAY_09], env=env
    )
    assert audited.exit_code == 0, audited.output
    sla_body = json.loads(audited.stdout)
    assert sla_body["elapsed_minutes"] == 120
    assert sla_body["remaining_minutes"] == 360

    missing = runner.invoke(cli_app, ["sla", "INC-NOPE0000"], env=env)
    assert missing.exit_code == 1


def test_normalizacion_naive_y_aware_dan_el_mismo_sla(client, service):
    service.create_incident(
        "Cuenta bloqueada", ACCOUNT_LOCKED, incident_id="INC-TZ-00001",
        created_at=datetime.fromisoformat("2026-11-06T22:00:00+00:00"),  # = vie 17:00 Bogotá
    )

    naive = client.get("/api/v1/incidents/INC-TZ-00001/sla", params={"reference_time": MONDAY_09})
    aware = client.get(
        "/api/v1/incidents/INC-TZ-00001/sla",
        params={"reference_time": "2026-11-09T14:00:00+00:00"},  # = lun 09:00 Bogotá
    )

    assert naive.status_code == aware.status_code == 200
    assert naive.json() == aware.json()
    assert naive.json()["elapsed_minutes"] == 120
