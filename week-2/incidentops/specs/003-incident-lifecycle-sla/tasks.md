# Tasks: Ciclo de Vida de Incidentes, Duplicados y Auditoría de SLA

**Input**: `specs/003-incident-lifecycle-sla/` (spec.md, plan.md)
**Tests**: obligatorios. Formato: `- [ ] T### [P] [US#] descripción + ruta`.

## Phase 1: Foundational

- [X] T001 [P] Extender `Incident` (`recommended_team`, `duplicate_group_key`) y añadir `OPEN_STATUSES`/`INCIDENT_STATUSES` en src/domain/models.py
- [X] T002 [P] `BUSINESS_TZ`, `normalize_timestamp`, `now_local` y normalización en `evaluate_sla_status` en src/domain/sla_calculator.py
- [X] T003 Añadir `get_incident` y `find_open_duplicates` a `IncidentRepositoryPort` en src/application/ports.py
- [X] T004 Columnas, índice `idx_incidents_dup_key`, migración aditiva, `save_incident`, `get_incident`, `find_open_duplicates` en src/adapters/outbound/sqlite_repository.py

## Phase 2: US1 + US2 — Registro y duplicados (P1) 🎯 MVP

- [X] T005 [US1] `create_incident`, `IncidentRegistration`, `IncidentAlreadyExistsError` en src/application/services.py
- [X] T006 [US1] `CreateIncidentRequest`, `IncidentCreatedResponse` y `POST /api/v1/incidents` (201/409/422) en src/adapters/inbound/api/
- [X] T007 [US1] Escenarios 1 y 1b en tests/test_spec_003_lifecycle_sla.py
- [X] T008 [US2] Escenario 2 (duplicado abierto, ignora RESOLVED) en tests/test_spec_003_lifecycle_sla.py

## Phase 3: US3 — Auditoría de SLA (P2)

- [X] T009 [US3] `evaluate_incident_sla`, `IncidentNotFoundError` y "ahora" = `now_local()` también en el resumen H002 (hallazgo B2 de analyze) en src/application/services.py
- [X] T010 [US3] `SLAEvaluationResponse` y `GET /api/v1/incidents/{incident_id}/sla` (200/404/422) en src/adapters/inbound/api/
- [X] T011 [US3] Escenarios 3 y 4 en tests/test_spec_003_lifecycle_sla.py

## Phase 4: US4 — Paridad terminal (P2)

- [X] T012 [US4] Comandos `create` y `sla` + serializadores comunes en src/adapters/inbound/cli.py y presenters.py
- [X] T013 [US4] Escenario 5 en tests/test_spec_003_lifecycle_sla.py

## Phase 5: Polish

- [X] T014 [P] Prueba de normalización naive/aware (mismo instante ⇒ mismo SLA) en tests/test_spec_003_lifecycle_sla.py
- [X] T015 [P] Actualizar AGENTS.md con `create`/`sla`
- [X] T016 Verificar `uv run ruff check src/` y `uv run pytest -v` (sin regresiones en 001/002)

**Dependencias**: T001–T004 → T005 → (T006–T008) ; T009 → T010–T011 ; T012 tras T005 y T009.
