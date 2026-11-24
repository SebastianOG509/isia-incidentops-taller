# AGENTS.md — IncidentOps

Manual operativo del repositorio para agentes de código. Describe **cómo operar** el proyecto hoy;
las reglas innegociables viven en `docs/constitution.md` y las decisiones en `docs/adr/`.

## Estructura actual (Arquitectura Hexagonal, ADR-003)

```
data/sample_incidents.json        10 reportes de referencia (INC-1001..INC-1010)
docs/ROADMAP.md                   Hitos de producto H001–H004
docs/constitution.md              Constitución del proyecto
docs/adr/                         ADRs (000-template MADR estricto, 001, 002, 003)
specs/                            Especificaciones BDD por hito
src/domain/                       Núcleo puro: models.py, triage_rules.py, sla_calculator.py
src/application/services.py       IncidentService (casos de uso compartidos)
src/adapters/inbound/api/         FastAPI: schemas.py, app.py (create_app)
src/adapters/inbound/cli.py       CLI Typer
tests/                            Pruebas de aceptación BDD (test_spec_<NNN>_*.py)
```

## Comandos

Ejecutar siempre desde `week-2/incidentops/` con `uv`:

```bash
uv sync
uv run pytest -v                                  # pruebas de aceptación BDD
uv run python -m src.domain.triage_rules          # auditoría 10/10 del triaje
uv run python -m src.domain.sla_calculator        # verificación determinista ADR-002
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
uv run uvicorn src.adapters.inbound.api.app:app --reload   # API en http://localhost:8000/docs
```

## Reglas de trabajo del agente

1. Alternar **Plan → Build**: analizar y proponer primero; editar solo tras aprobación humana.
2. Respetar `docs/constitution.md`; no añadir dependencias sin spec/plan/ADR que lo justifique.
3. Los adaptadores primarios solo delegan en `IncidentService`; nada de reglas de negocio fuera de `src/domain/`.
4. Toda decisión arquitectónica estructural se registra antes en `docs/adr/` usando `000-template.md`.
5. Una tarea está terminada solo cuando `uv run pytest -v` pasa al 100 %.
