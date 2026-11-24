---
name: hexagonal-architecture
description: Reglas de capas e imports de la Arquitectura Hexagonal de IncidentOps (ADR-003). Úsala al planificar o escribir código en src/ (domain, application, adapters), al añadir un endpoint REST, comando CLI, puerto o repositorio, o al corregir errores TID251/TID252 de `uv run ruff check src/`.
---

# Arquitectura Hexagonal en IncidentOps

## Qué puede importar cada capa

| Capa | Puede importar | NO puede importar |
| :--- | :--- | :--- |
| `src/domain/` | Solo biblioteca estándar y `src.domain.*` | fastapi, starlette, pydantic, typer, sqlite3, psycopg, ORMs, `src.application`, `src.adapters` |
| `src/application/` | Biblioteca estándar y `src.domain.*` | Frameworks HTTP/CLI, pydantic, drivers de BD, `src.adapters` |
| `src/adapters/inbound/` | fastapi, pydantic, typer, `src.application`, `src.domain.models`, `src.adapters.outbound.factory` | sqlite3, psycopg, repositorios concretos, `triage_rules`, `sla_calculator` |
| `src/adapters/outbound/` | Drivers de BD, `src.domain.models`, `src.application.ports` | Frameworks HTTP/CLI, `src.adapters.inbound` |

Imports siempre absolutos (`from src.domain.models import Incident`); nunca relativos hacia padres.

## Cómo añadir una capacidad

1. Regla de negocio nueva → función pura en `src/domain/`.
2. Necesidad de datos → método en `IncidentRepositoryPort` (`src/application/ports.py`, `typing.Protocol`)
   y su implementación en **cada** adaptador de `src/adapters/outbound/`.
3. Caso de uso → método en `IncidentService` (`src/application/services.py`) que orquesta dominio + puerto
   y lanza excepciones de aplicación (`ValidationError`, `IncidentNotFoundError`), nunca `HTTPException`.
4. Exponerlo en **ambos** adaptadores primarios (paridad obligatoria):
   - REST: DTO Pydantic en `api/schemas.py` + ruta en `api/app.py`; mapea `ValidationError → 422`,
     `IncidentNotFoundError → 404`.
   - CLI: subcomando Typer en `cli.py`; imprime JSON en stdout y mapea cualquier error a `typer.Exit(code=1)`.
5. Cablear el repositorio con `create_repository(database_url)` de `src.adapters.outbound.factory`,
   nunca instanciando la clase concreta en un adaptador primario.

## Verificación

```bash
uv run ruff check src/   # TID251 banned-api + TID252 por capa (ruff.toml jerárquicos)
uv run pytest -v
```

Las reglas viven en `pyproject.toml` (`select = ["E4","E7","E9","F","TID"]`) y en
`src/domain/ruff.toml`, `src/application/ruff.toml`, `src/adapters/inbound/ruff.toml` (cada uno con
`extend` hacia `pyproject.toml`). Ante un TID251, **mueve el código a la capa correcta**; no añadas
`# noqa` ni relajes la lista de módulos prohibidos.
