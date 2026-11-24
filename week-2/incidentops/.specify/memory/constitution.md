<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: principio IV ampliado por ADR-004)
- Principios modificados: IV. Persistencia Intercambiable sin ORM → IV. Persistencia Dual SQLite/PostgreSQL sin ORM
- Secciones modificadas: Restricciones Tecnológicas (+ psycopg[binary], Docker Compose)
- Secciones añadidas / eliminadas: ninguna
- Fuentes: docs/adr/004-persistencia-postgresql-y-runtime-contenedores.md (reemplaza parcialmente ADR-001)
- TODOs diferidos: ninguno
-->
# IncidentOps Constitution

## Core Principles

### I. Núcleo de Dominio Determinista Único

Las reglas de negocio viven **una sola vez** en `src/domain/` (`models.py`, `triage_rules.py`,
`sla_calculator.py`) y MUST producir el mismo resultado para la misma entrada.

- SLA (ADR-002): P0 = 60 min y P1 = 240 min en reloj 24/7; P2 = 480 min y P3 = 1440 min solo en
  horario hábil (L-V 08:00–18:00). Incumplido = transcurrido estrictamente mayor al permitido.
- Escalamiento preventivo al 75 % del SLA para incidentes abiertos, aun si ya incumplieron.
- Equipos válidos: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- Estados: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` (abiertos) y `RESOLVED`.
- La clave de duplicados (`componente:síntoma`) la produce exclusivamente el motor de triaje.

*Razón*: duplicar reglas en API, CLI o SQL genera divergencias silenciosas de severidad o SLA.

### II. Arquitectura Hexagonal Estricta (ADR-003)

- `src/domain/` MUST importar solo la biblioteca estándar; ningún framework, HTTP, driver de BD,
  ORM ni otra capa del proyecto.
- `src/application/` contiene `ports.py` (puertos secundarios como `typing.Protocol`) y
  `services.py` (`IncidentService`); MUST importar solo biblioteca estándar y `src.domain`.
- `src/adapters/inbound/` (FastAPI, Typer y futuros como MCP) MUST delegar en `IncidentService` y
  MUST NOT importar drivers de BD ni repositorios concretos; obtiene el repositorio mediante
  `src.adapters.outbound.factory`.
- `src/adapters/outbound/` implementa los puertos y es intercambiable vía `DATABASE_URL`.
- Las fronteras se verifican estáticamente con Ruff (`uv run ruff check src/`, reglas `TID251`
  banned-api y `TID252` ban-relative-imports en `ruff.toml` jerárquicos por capa).

*Razón*: las fronteras que no se verifican automáticamente se degradan.

### III. Paridad de Adaptadores Primarios

Toda capacidad expuesta por REST MUST existir también en la CLI (y viceversa), invocando el mismo
método de `IncidentService`, con la misma validación y semántica de error
(`422` en REST ⇔ código de salida `1` en CLI; `404` ⇔ código `1`).

### IV. Persistencia Dual SQLite/PostgreSQL sin ORM (ADR-004)

La persistencia usa SQL explícito y parametrizado, **sin ORMs**. Hay dos adaptadores secundarios que
MUST cumplir el mismo `IncidentRepositoryPort` (incluido `check_health()`):
- **SQLite** (`sqlite3` estándar): desarrollo local y pruebas; `sqlite:///:memory:` por defecto.
- **PostgreSQL** (`psycopg[binary]`, `dict_row`, parámetros `%s`, `INSERT ... ON CONFLICT DO UPDATE`):
  producción en contenedores.

El adaptador se elige **solo** en `src.adapters.outbound.factory.create_repository(DATABASE_URL)`:
`postgresql://...` → PostgreSQL; `sqlite:///...` o variable ausente → SQLite. Las marcas de tiempo se
guardan como texto ISO 8601 en hora local de operación en ambos motores (paridad temporal). Añadir otro
motor MUST estar precedido por un ADR aceptado y una enmienda de esta Constitución.

### V. Especificación BDD y Verificación Determinista (NON-NEGOTIABLE)

Toda funcionalidad nace de un `spec.md` con escenarios `Given / When / Then` en lenguaje de
negocio (sin nombres de clases ni tablas). Cada escenario MUST tener al menos una prueba de
aceptación `test_bdd_*` que use `TestClient` y/o `CliRunner` sobre almacenamiento aislado.
Ninguna tarea se considera terminada si `uv run ruff check src/` o `uv run pytest -v` fallan.

## Restricciones Tecnológicas

- Python `>=3.10` gestionado exclusivamente con `uv` (`uv add`, `uv run`, `uv.lock` versionado).
- REST: FastAPI + Pydantic v2. CLI: Typer. Pruebas: pytest + httpx. Análisis estático: Ruff.
- Driver PostgreSQL: `psycopg[binary]` (ADR-004); su import solo se permite en `src/adapters/outbound/`.
- Runtime de producción: Docker Compose con servicios `api` (`python:3.12-slim` + `uv`) y `db`
  (`postgres:16-alpine`, volumen persistente); la suite de pruebas MUST seguir ejecutándose sin Docker.
- Toda dependencia nueva MUST estar justificada por un spec, plan o ADR aprobado.

## Flujo de Desarrollo

1. Decisión estructural nueva → ADR (`docs/adr/000-template.md`) → enmienda de esta Constitución.
2. Hito → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` →
   `/speckit.analyze` → `/speckit.implement`.
3. Curaduría humana de `spec.md`, `plan.md` y `tasks.md` antes de implementar (concisión, sin
   requisitos inventados fuera de esta Constitución).

## Governance

Esta Constitución prevalece sobre cualquier otra práctica del repositorio. Las enmiendas requieren
un ADR que las justifique, actualización de versión semántica (MAJOR: eliminación o redefinición
de principios; MINOR: principio o sección nuevos o ampliados; PATCH: redacción) y revisión de
`plan.md` vigentes. Cada `/speckit.plan` y `/speckit.analyze` MUST verificar el cumplimiento de
estos principios. La guía operativa del agente está en `AGENTS.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-24 | **Last Amended**: 2026-11-24
