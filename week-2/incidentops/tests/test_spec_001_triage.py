"""Pruebas de aceptación de specs/001-triage-endpoint-manual.md (1 escenario = 1 prueba)."""

import json

from src.adapters.inbound.cli import app as cli_app

PAYMENTS_OUTAGE = (
    "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones "
    "con tarjeta de crédito desde hace 12 minutos. Ningún comercio puede cobrar."
)
ACCOUNT_LOCKED = (
    "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. "
    "Necesito acceder hoy mismo porque debo enviar el informe de cierre a la junta directiva."
)


def test_bdd_escenario_1_caida_critica_pasarela_pagos(client):
    response = client.post(
        "/api/v1/incidents/triage", json={"incident_id": "INC-1001", "raw_text": PAYMENTS_OUTAGE}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == "payments-gateway:http-502"


def test_bdd_escenario_2_cuenta_bloqueada_sin_falso_p0(client):
    response = client.post(
        "/api/v1/incidents/triage", json={"incident_id": "INC-1002", "raw_text": ACCOUNT_LOCKED}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P2"
    assert body["recommended_team"] == "Security-IAM"


def test_bdd_escenario_3_entradas_vacias_retornan_422(client):
    blank_text = client.post(
        "/api/v1/incidents/triage", json={"incident_id": "INC-1", "raw_text": "   "}
    )
    blank_id = client.post(
        "/api/v1/incidents/triage", json={"incident_id": "", "raw_text": PAYMENTS_OUTAGE}
    )
    assert blank_text.status_code == 422
    assert blank_id.status_code == 422


def test_bdd_escenario_4_paridad_cli(runner):
    result = runner.invoke(
        cli_app, ["triage", "--incident-id", "INC-1001", "--raw-text", PAYMENTS_OUTAGE]
    )
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["severity"] == "P0"
    assert body["recommended_team"] == "Backend-Core"


def test_bdd_escenario_4b_cli_entrada_vacia_sale_con_1(runner):
    result = runner.invoke(cli_app, ["triage", "--incident-id", "INC-1", "--raw-text", "  "])
    assert result.exit_code == 1
