# Implementation Plan: Resumen de Incidentes Activos

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-active-incidents-summary/spec.md`

## Summary

Exponer por REST y CLI un resumen de incidentes `OPEN`/`IN_PROGRESS` con totales y evaluación de SLA por
incidente. Se introduce el primer puerto secundario (`IncidentRepositoryPort`), el adaptador SQLite
(extraído y optimizado desde `incident_repository.py` de la Semana 1: una sola consulta con
`INNER JOIN sla_policies` e índice `(component, status)`, sin N+1) y una fábrica que lo elige por `DATABASE_URL`.

## Technical Context

**Language/Version**: Python >=3.10 (uv)
**Primary Dependencies**: FastAPI, Pydantic v2, Typer (ya instaladas); Ruff (dev) para fronteras
**Storage**: `sqlite3` estándar; `DATABASE_URL` por defecto `sqlite:///:memory:`; fechas ISO 8601 en `TEXT`
**Testing**: pytest + `TestClient` + `CliRunner`, BD `:memory:` nueva por prueba
**Target Platform**: servicio local / terminal
**Project Type**: web-service + CLI (hexagonal)
**Performance Goals**: resumen de 10.000 filas en una sola consulta indexada (sin N+1)
**Constraints**: cálculo de SLA solo en `src/domain/sla_calculator.py`; sin ORM
**Scale/Scope**: cientos de incidentes activos; sin paginación (supuesto del spec)

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | SLA vía `evaluate_sla_status`; el adaptador no calcula SLA. ✅ |
| II. Hexagonal | Puerto `Protocol` en `application/ports.py`; SQLite en `adapters/outbound/`; Ruff jerárquico activo. ✅ |
| III. Paridad | `GET /api/v1/incidents/summary` y `summary` invocan `get_active_incidents_summary`. ✅ |
| IV. Persistencia sin ORM | SQL parametrizado `?` con `sqlite3`. ✅ |
| V. BDD | 4 escenarios ↔ 4+ `test_bdd_*` en `tests/test_spec_002_summary.py`. ✅ |

Post-diseño: sin violaciones; *Complexity Tracking* no aplica.

## Decisiones técnicas (research condensado)

- **Puerto mínimo por hito**: `IncidentRepositoryPort` declara solo `save_incident` y `list_active_incidents`
  (lo que consume H002). `get_incident`/`find_open_duplicates` llegan en H003 y `check_health` en H004.
  *Alternativa rechazada*: declarar los 5 métodos ya (YAGNI: métodos sin escenario que los pruebe).
- **Consulta optimizada**: `SELECT i.* FROM incidents i INNER JOIN sla_policies p ON p.severity = i.severity
  WHERE i.status IN ('OPEN','IN_PROGRESS') [AND i.component = ?] ORDER BY i.created_at`, apoyada en
  `idx_incidents_component_status (component, status)`. El `JOIN` garantiza que solo se resumen incidentes
  con política de SLA válida.
- **Concurrencia de prueba**: `sqlite3.connect(..., check_same_thread=False)` porque `TestClient` ejecuta
  la app en otro hilo.
- **Cableado**: `IncidentService(repository)`; los adaptadores primarios construyen el servicio con
  `create_repository(os.getenv("DATABASE_URL"))`. URL no soportada → `ValueError`.

## Modelo y contratos (data-model + contracts condensados)

- Aplicación: `IncidentSummaryItem(incident, evaluation)` y `ActiveIncidentsSummary(total_active,
  breached_count, incidents)` (dataclasses en `services.py`).
- REST `GET /api/v1/incidents/summary?component=&reference_time=` → `200` `ActiveIncidentsSummaryResponse
  {total_active, breached_count, incidents: [ActiveIncidentItem{incident_id, title, component, severity,
  status, elapsed_minutes, allowed_minutes, is_breached, requires_escalation}]}`.
- CLI `summary [--component TEXT] [--reference-time ISO]` → mismo JSON por stdout, exit `0`.

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── spec.md
├── plan.md      # este archivo (research, data-model y contracts condensados aquí)
├── tasks.md
└── checklists/requirements.md
```

### Source Code

```text
src/application/ports.py                    # NUEVO: IncidentRepositoryPort (Protocol)
src/application/services.py                 # + repositorio inyectado, get_active_incidents_summary
src/adapters/outbound/sqlite_repository.py  # NUEVO: SQLiteIncidentRepository
src/adapters/outbound/factory.py            # NUEVO: create_repository(database_url)
src/adapters/inbound/api/{schemas,app}.py   # + ActiveIncidentItem, ActiveIncidentsSummaryResponse, ruta
src/adapters/inbound/cli.py                 # + comando summary
pyproject.toml + src/*/ruff.toml            # Ruff jerárquico (ya configurado en Iteración 2.2)
tests/conftest.py                           # servicio con SQLite :memory: aislado
tests/test_spec_002_summary.py              # NUEVO
```

**Structure Decision**: proyecto único hexagonal (ADR-003), sin carpetas nuevas fuera de las capas existentes.
