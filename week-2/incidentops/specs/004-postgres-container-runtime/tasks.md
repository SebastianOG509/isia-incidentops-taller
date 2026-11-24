# Tasks: Persistencia Relacional Dedicada y Runtime en Contenedores

**Input**: `specs/004-postgres-container-runtime/` (spec.md, plan.md) · ADR-004
**Tests**: obligatorios, sin Docker. Formato: `- [ ] T### [P] [US#] descripción + ruta`.

## Phase 1: Setup

- [X] T001 `uv add "psycopg[binary]"` (pyproject.toml, uv.lock)

## Phase 2: Foundational

- [X] T002 Añadir `check_health()` a `IncidentRepositoryPort` en src/application/ports.py
- [X] T003 [P] `check_health()` (`SELECT 1`) en src/adapters/outbound/sqlite_repository.py
- [X] T004 [P] `PostgresIncidentRepository` (dict_row, `%s`, `ON CONFLICT DO UPDATE`, índices, esquema perezoso, `check_health`) en src/adapters/outbound/postgres_repository.py
- [X] T005 Esquema `postgresql://`/`postgres://` y error por esquema no soportado en src/adapters/outbound/factory.py

## Phase 3: US1 — Chequeo real de salud (P1) 🎯 MVP

- [X] T006 [US1] `IncidentService.check_health()` en src/application/services.py
- [X] T007 [US1] `HealthResponse` y `GET /health` (200/503) en src/adapters/inbound/api/
- [X] T008 [US1] Comando `health` (exit 0/1) en src/adapters/inbound/cli.py
- [X] T009 [US1] Escenarios 1 y 2 (incluye doble de prueba y CLI) en tests/test_spec_004_runtime_health.py

## Phase 4: US2 — Selección transparente (P1)

- [X] T010 [US2] Escenario 3: fábrica + cumplimiento de `IncidentRepositoryPort` por SQLite y PostgreSQL, timeout < 5 s y contrato real opcional (`TEST_POSTGRES_URL`) en tests/test_spec_004_runtime_health.py

## Phase 5: US3 — Orquestación (P2)

- [X] T011 [P] [US3] Dockerfile (python:3.12-slim + uv, `--frozen --no-dev`) y .dockerignore
- [X] T012 [P] [US3] docker-compose.yml (`db` con volumen y `pg_isready`; `api` con `DATABASE_URL`, `service_healthy`, healthcheck `/health`)
- [X] T013 [US3] Escenario 4: estructura de archivos Docker en tests/test_spec_004_runtime_health.py

## Phase 6: Polish

- [X] T014 [P] Actualizar AGENTS.md (health, Docker, `DATABASE_URL`)
- [X] T015 Verificar `uv run ruff check src/`, `uv run pytest -v`, CLI `health`, `docker compose config -q` y `docker compose up --build`

**Dependencias**: T002 → T003/T004 → T005 → T006 → T007/T008 → T009/T010; T011–T013 independientes de T006.
