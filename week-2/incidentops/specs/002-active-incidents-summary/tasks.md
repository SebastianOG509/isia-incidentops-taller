# Tasks: Resumen de Incidentes Activos

**Input**: `specs/002-active-incidents-summary/` (spec.md, plan.md)
**Tests**: obligatorios (Constitución, principio V). Formato: `- [ ] T### [P] [US#] descripción + ruta`.

## Phase 1: Foundational (bloquea todas las historias)

- [X] T001 Definir `IncidentRepositoryPort` (`save_incident`, `list_active_incidents`) en src/application/ports.py
- [X] T002 Implementar `SQLiteIncidentRepository` (esquema, `sla_policies`, índice `(component, status)`, JOIN) en src/adapters/outbound/sqlite_repository.py
- [X] T003 [P] Implementar `create_repository(database_url)` en src/adapters/outbound/factory.py
- [X] T004 Inyectar repositorio en `IncidentService` y cablear adaptadores con la fábrica en src/application/services.py, src/adapters/inbound/api/app.py, src/adapters/inbound/cli.py
- [X] T005 Fixture de servicio con SQLite `:memory:` aislado en tests/conftest.py

## Phase 2: User Story 1 — Panorama global (P1) 🎯 MVP

- [X] T006 [US1] `get_active_incidents_summary(component_filter, reference_time)` en src/application/services.py
- [X] T007 [US1] `ActiveIncidentItem` y `ActiveIncidentsSummaryResponse` en src/adapters/inbound/api/schemas.py
- [X] T008 [US1] Ruta `GET /api/v1/incidents/summary` en src/adapters/inbound/api/app.py
- [X] T009 [US1] `test_bdd_escenario_1_resumen_global_excluye_resueltos` en tests/test_spec_002_summary.py

## Phase 3: User Story 2 — Filtro por componente (P2)

- [X] T010 [US2] `test_bdd_escenario_2_filtro_por_componente` y `test_bdd_escenario_3_resumen_vacio` en tests/test_spec_002_summary.py

## Phase 4: User Story 3 — Paridad terminal (P3)

- [X] T011 [US3] Comando `summary [--component] [--reference-time]` en src/adapters/inbound/cli.py
- [X] T012 [US3] `test_bdd_escenario_4_paridad_cli` en tests/test_spec_002_summary.py

## Phase 5: Polish

- [X] T013 [P] Prueba de cumplimiento de `IncidentRepositoryPort` por `SQLiteIncidentRepository` en tests/test_spec_002_summary.py
- [X] T014 [P] Actualizar AGENTS.md (estructura, `ruff check`, comando `summary`)
- [X] T015 Verificar `uv run ruff check src/` y `uv run pytest -v`

**Dependencias**: Phase 1 → Phases 2-4 (US2/US3 reutilizan T006) → Phase 5.
