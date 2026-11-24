# Constitución de IncidentOps

Principios innegociables que todo hito (`docs/ROADMAP.md`) debe respetar. Las decisiones aquí adoptadas
están justificadas en `docs/adr/`; cambiarlas exige primero un ADR nuevo.

## 1. Dominio determinista único

- **Severidades y SLA** (ADR-002): P0 = 60 min y P1 = 240 min en reloj 24/7; P2 = 480 min y P3 = 1440 min
  contados solo en horario hábil (lunes a viernes, 08:00–18:00).
- **Escalamiento preventivo**: un incidente abierto requiere escalamiento al consumir el **75 %** de su SLA,
  aunque ya lo haya incumplido. Incumplido = tiempo transcurrido **estrictamente mayor** al permitido.
- **Equipos válidos**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- **Estados**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` (abiertos) y `RESOLVED` (cerrado).
- **Clave de duplicados**: `componente:categoría-de-síntoma`, producida únicamente por el motor de triaje.
- Estas reglas existen **una sola vez**, en `src/domain/`. Ninguna capa externa las reimplementa.

## 2. Arquitectura Hexagonal (ADR-003)

- `src/domain/`: núcleo puro; solo biblioteca estándar. Sin frameworks, HTTP, drivers de BD ni imports de otras capas.
- `src/application/`: casos de uso compartidos (`IncidentService`) y puertos secundarios (`typing.Protocol`);
  solo biblioteca estándar y `src.domain`.
- `src/adapters/inbound/`: adaptadores primarios (API REST y CLI; preparado para un futuro MCP). Delegan
  siempre en `IncidentService` y **nunca** contienen reglas de negocio ni importan drivers o repositorios concretos.
- `src/adapters/outbound/`: adaptadores secundarios intercambiables que implementan los puertos.
- **Paridad**: toda capacidad expuesta por una interfaz primaria se expone en las demás invocando el mismo caso de uso.

## 3. Gobernanza técnica y calidad

- Python `>=3.10` gestionado exclusivamente con `uv`.
- API REST con **FastAPI + Pydantic v2**; CLI con **Typer**.
- Persistencia con **`sqlite3` estándar, sin ORMs** (ADR-001). Cualquier cambio de motor de BD requiere su propio ADR previo.
- Toda funcionalidad nace de una especificación BDD (`Given / When / Then`) en lenguaje de negocio, y cada
  escenario tiene una prueba de aceptación automatizada con `pytest` (`uv run pytest -v`).
- No se agregan dependencias sin que un artefacto aprobado (spec, plan o ADR) lo justifique.
