# Implementation Plan: Persistencia Relacional Dedicada y Runtime en Contenedores

**Branch**: `004-postgres-container-runtime` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-postgres-container-runtime/spec.md` · Decisión: ADR-004

## Summary

Añadir `PostgresIncidentRepository` (psycopg, sin ORM) que cumple el mismo `IncidentRepositoryPort` que
SQLite, seleccionarlo por `DATABASE_URL` en la fábrica, exponer `check_health()` como caso de uso por
`GET /health` y comando `health`, y empaquetar todo en Docker Compose (`api` + `db`).

## Technical Context

**Language/Version**: Python >=3.10 local; imagen `python:3.12-slim`
**Primary Dependencies**: `psycopg[binary]` (nuevo, ADR-004); `uv` 0.11 copiado desde `ghcr.io/astral-sh/uv`
**Storage**: SQLite (dev/pruebas) y PostgreSQL 16 (producción); fechas `TEXT` ISO 8601 en ambos
**Testing**: pytest sin Docker; prueba de contrato PostgreSQL contra servidor real **solo** si existe
`TEST_POSTGRES_URL` (se salta si no)
**Constraints**: `connect_timeout=3`; ningún adaptador primario importa `psycopg` (Ruff TID251)
**Scale/Scope**: una réplica de `api`

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | Sin cambios en `src/domain/`. ✅ |
| II. Hexagonal | `psycopg` solo en `adapters/outbound/`; inbound usa `factory` + `IncidentService.check_health()`. ✅ |
| III. Paridad | `GET /health` 200/503 ⇔ `health` exit 0/1, mismo JSON. ✅ |
| IV. Dual sin ORM (v1.1.0) | `dict_row`, `%s`, `ON CONFLICT DO UPDATE`, mismos índices, fechas `TEXT`. ✅ |
| V. BDD | 4 escenarios ↔ `tests/test_spec_004_runtime_health.py`; suite corre sin Docker (RNF-001). ✅ |

## Decisiones técnicas (research condensado)

- **Conexión por operación** (`with psycopg.connect(url, row_factory=dict_row, connect_timeout=3)`): tolera
  reinicios de `db` sin reconectar manualmente; volumen de tráfico bajo (una réplica). *Rechazado*: pool
  (`psycopg_pool`) → dependencia extra sin necesidad medida.
- **Esquema perezoso**: `CREATE TABLE/INDEX IF NOT EXISTS` y siembra de `sla_policies` en la primera
  operación de datos, no en el constructor; así la API arranca y responde `503` aunque la base esté caída.
- **`check_health()`**: `SELECT 1`; captura `psycopg.Error`/`OSError` → `False` (nunca `500`).
  SQLite implementa lo mismo con `sqlite3.Error`.
- **Fábrica**: `postgresql://` o `postgres://` → PostgreSQL; `sqlite:///` o vacío → SQLite; otro → `ValueError`.
- **Imagen**: `uv sync --frozen --no-dev` con caché de capas (copiar `pyproject.toml`/`uv.lock` antes que `src/`);
  healthcheck con `python -c urllib...` porque `python:3.12-slim` no trae `curl`.
- **Prueba 503**: doble de prueba (`FailingRepository` con `check_health() -> False`) inyectado en
  `create_app`, más una prueba real contra un puerto PostgreSQL cerrado que verifica el timeout (< 5 s, SC-001).

## Modelo y contratos

- Puerto: `+ check_health() -> bool` (completa los 5 métodos).
- REST `GET /health` → `200 HealthResponse{status:"ok", database:"connected"}` | `503 {status:"error", database:"unavailable"}`.
- CLI `health` → mismo JSON; exit `0` | `1`.
- Compose: `db` (`postgres:16-alpine`, `POSTGRES_USER/PASSWORD/DB=incidentops`, volumen `pgdata`, `pg_isready`),
  `api` (build local, `DATABASE_URL=postgresql://incidentops:incidentops@db:5432/incidentops`, puerto 8000,
  `depends_on: db: condition: service_healthy`, healthcheck `/health`).

## Project Structure

```text
src/application/ports.py                     # + check_health
src/application/services.py                  # + check_health
src/adapters/outbound/postgres_repository.py # NUEVO
src/adapters/outbound/sqlite_repository.py   # + check_health
src/adapters/outbound/factory.py             # + esquema postgresql://
src/adapters/inbound/api/{schemas,app}.py    # + HealthResponse, GET /health
src/adapters/inbound/cli.py                  # + health
Dockerfile, .dockerignore, docker-compose.yml # NUEVOS
tests/test_spec_004_runtime_health.py        # NUEVO
```

**Structure Decision**: un adaptador secundario nuevo; artefactos de runtime en la raíz del proyecto.
