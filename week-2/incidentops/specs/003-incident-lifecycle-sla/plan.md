# Implementation Plan: Ciclo de Vida de Incidentes, Duplicados y Auditoría de SLA

**Branch**: `003-incident-lifecycle-sla` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-incident-lifecycle-sla/spec.md`

## Summary

Registrar incidentes clasificados por el motor de triaje, detectar equivalentes abiertos por clave de
duplicado y auditar su SLA en un instante de referencia, por REST (`POST /api/v1/incidents`,
`GET /api/v1/incidents/{incident_id}/sla`) y CLI (`create`, `sla`), extendiendo dominio, puerto, servicio y
adaptador SQLite sin romper H001/H002.

## Technical Context

**Language/Version**: Python >=3.10 (uv)
**Primary Dependencies**: FastAPI, Pydantic v2, Typer (sin dependencias nuevas)
**Storage**: `sqlite3`; nuevas columnas `recommended_team`, `duplicate_group_key`; índice
`idx_incidents_dup_key (duplicate_group_key, status)`
**Testing**: pytest + `TestClient` + `CliRunner` (archivo SQLite temporal para la paridad CLI)
**Project Type**: web-service + CLI (hexagonal)
**Constraints**: zona de operación fija UTC-05:00 (`datetime.timezone`, sin `tzdata`); dominio solo stdlib
**Scale/Scope**: detección de duplicados en una consulta indexada

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | Clasificación y clave vía `classify_incident_report`; SLA y normalización temporal en `sla_calculator.py`; estados abiertos como constante del dominio. ✅ |
| II. Hexagonal | Puerto crece con `get_incident`/`find_open_duplicates`; errores de aplicación (`IncidentNotFoundError`, `IncidentAlreadyExistsError`) mapeados a HTTP solo en el adaptador. ✅ |
| III. Paridad | `create`/`sla` ⇔ rutas REST, misma serialización en `presenters.py`; `404/409/422` ⇔ exit `1`. ✅ |
| IV. Sin ORM | SQL parametrizado; migración aditiva con `ALTER TABLE` si la BD ya existía. ✅ |
| V. BDD | 6 escenarios ↔ `tests/test_spec_003_lifecycle_sla.py`. ✅ |

Post-diseño: sin violaciones.

## Decisiones técnicas (research condensado)

- **Normalización temporal** (FR-009): `BUSINESS_TZ = timezone(timedelta(hours=-5))` y
  `normalize_timestamp(dt)` en el dominio: aware → `astimezone(BUSINESS_TZ).replace(tzinfo=None)`;
  naive → sin cambios. `evaluate_sla_status` normaliza `created_at`, `resolved_at` y `reference_time`;
  así comparar naive con aware nunca lanza `TypeError`. "Ahora" = `now_local()` del dominio.
- **Duplicados** (FR-007): `OPEN_STATUSES = ("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")` en
  `models.py`; `find_open_duplicates(key, exclude_incident_id)` filtra en SQL con el índice compuesto.
  Se consulta **antes** de guardar y además excluye el propio ID.
- **Conflicto** (FR-010): el servicio consulta `get_incident` antes de guardar → `IncidentAlreadyExistsError`.
  `save_incident` sigue siendo upsert (contrato del puerto), la regla de no sobrescribir vive en el caso de uso.
- **Clasificación** (FR-011): solo `raw_text`; `title` se persiste como etiqueta. `raw_text` no se persiste
  (el contrato de `Incident` no lo incluye; queda fuera de alcance).
- **Estado inicial**: validado contra los cuatro estados del dominio (Pydantic `Literal` en REST,
  `ValidationError` del servicio en CLI).

## Modelo y contratos (data-model + contracts condensados)

- `Incident` + `recommended_team: Optional[TeamName] = None`, `duplicate_group_key: Optional[str] = None`.
- Aplicación: `IncidentRegistration(incident, triage, is_duplicate, duplicate_of)`.
- REST `POST /api/v1/incidents` — `CreateIncidentRequest{title, raw_text, incident_id?, created_at?, status?}`
  → `201 IncidentCreatedResponse{incident_id, title, status, created_at, severity, component,
  recommended_team, duplicate_group_key, rationale, is_duplicate, duplicate_of}`; `409`; `422`.
- REST `GET /api/v1/incidents/{incident_id}/sla?reference_time=` → `200 SLAEvaluationResponse{incident_id,
  severity, elapsed_minutes, allowed_minutes, remaining_minutes, is_breached, requires_escalation}`; `404`; `422`.
- CLI `create --title --raw-text [--incident-id] [--created-at] [--status]` y `sla INCIDENT_ID [--reference-time]`.

## Project Structure

```text
src/domain/models.py                        # + campos de Incident, OPEN_STATUSES, INCIDENT_STATUSES
src/domain/sla_calculator.py                # + BUSINESS_TZ, normalize_timestamp, now_local
src/application/ports.py                    # + get_incident, find_open_duplicates
src/application/services.py                 # + create_incident, evaluate_incident_sla, errores
src/adapters/outbound/sqlite_repository.py  # + columnas, índice, migración, 2 métodos
src/adapters/inbound/api/{schemas,app}.py   # + 3 DTOs y 2 rutas
src/adapters/inbound/{cli,presenters}.py    # + create, sla y serializadores
tests/test_spec_003_lifecycle_sla.py        # NUEVO
```

**Structure Decision**: mismas capas; sin archivos de documentación adicionales (research/data-model/contracts
condensados aquí por concisión).
