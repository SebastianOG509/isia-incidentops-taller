# AGENTS.md — IncidentOps

Manual operativo del repositorio para agentes de código. Describe **cómo operar** el proyecto hoy;
las reglas innegociables viven en `docs/constitution.md` y las decisiones en `docs/adr/`.

## Estructura actual (Arquitectura Hexagonal, ADR-003)

```
data/sample_incidents.json        10 reportes de referencia (INC-1001..INC-1010)
docs/ROADMAP.md                   Hitos de producto H001–H004
docs/constitution.md              Constitución del proyecto
docs/adr/                         ADRs (000-template MADR estricto, 001, 002, 003)
specs/                            Especificaciones BDD (001 manual; 002+ generadas con Spec Kit)
.specify/memory/constitution.md   Constitución oficial de Spec Kit (manda sobre docs/constitution.md)
.opencode/commands/               Comandos /speckit.* ; .opencode/skills/ Agent Skills del proyecto
src/domain/                       Núcleo puro: models.py, triage_rules.py, sla_calculator.py
src/application/                  ports.py (IncidentRepositoryPort) y services.py (IncidentService)
src/adapters/inbound/             api/ (FastAPI), cli.py (Typer), presenters.py (serialización común)
src/adapters/outbound/            sqlite_repository.py y factory.py (create_repository por DATABASE_URL)
tests/                            Pruebas de aceptación BDD (test_spec_<NNN>_*.py)
```

## Comandos

Ejecutar siempre desde `week-2/incidentops/` con `uv`:

```bash
uv sync
uv run ruff check src/                            # fronteras hexagonales (TID251/TID252)
uv run pytest -v                                  # pruebas de aceptación BDD
uv run python -m src.domain.triage_rules          # auditoría 10/10 del triaje
uv run python -m src.domain.sla_calculator        # verificación determinista ADR-002
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
uv run python -m src.adapters.inbound.cli summary [--component X] [--reference-time ISO]
uv run python -m src.adapters.inbound.cli create --title "..." --raw-text "..." [--incident-id] [--created-at] [--status]
uv run python -m src.adapters.inbound.cli sla INC-XXXXXXXX [--reference-time ISO]
uv run uvicorn src.adapters.inbound.api.app:app --reload   # API en http://localhost:8000/docs
```

## Reglas de trabajo del agente

1. Alternar **Plan → Build**: analizar y proponer primero; editar solo tras aprobación humana.
2. Respetar `docs/constitution.md`; no añadir dependencias sin spec/plan/ADR que lo justifique.
3. Los adaptadores primarios solo delegan en `IncidentService`; nada de reglas de negocio fuera de `src/domain/`.
4. Toda decisión arquitectónica estructural se registra antes en `docs/adr/` usando `000-template.md`.
5. Una tarea está terminada solo cuando `uv run ruff check src/` y `uv run pytest -v` pasan al 100 %.
6. Flujo de cada hito: `/speckit.specify → clarify → plan → tasks → analyze → implement`.

Variables de entorno: `DATABASE_URL` (por defecto `sqlite:///:memory:`; usa `sqlite:///incidentops.db`
para que la CLI conserve datos entre invocaciones). Las horas con zona se normalizan a hora local UTC-05:00.
