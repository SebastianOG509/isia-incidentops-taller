# IncidentOps — Semana 2 (SDD con Spec Kit, Arquitectura Hexagonal y PostgreSQL)

Evolución del proyecto semilla de la Semana 1 (`../../week-1/starter-project`) a través de los hitos
de [`docs/ROADMAP.md`](docs/ROADMAP.md), siguiendo Spec-Driven Development.

| Artefacto | Ubicación |
| :--- | :--- |
| Manual operativo del agente | [`AGENTS.md`](AGENTS.md) |
| Constitución (manual / oficial Spec Kit) | [`docs/constitution.md`](docs/constitution.md) · [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| ADRs (MADR estricto) | [`docs/adr/`](docs/adr/) — 001 SQLite, 002 SLA hábil, 003 Hexagonal, 004 PostgreSQL + Compose |
| Agent Skills | [`.opencode/skills/`](.opencode/skills/) — `hexagonal-architecture`, `bdd-acceptance`, `adr-writer` |
| Especificaciones | [`specs/`](specs/) — 001 (manual), 002–004 (`spec.md`, `plan.md`, `tasks.md`) |
| Bitácora crítica | [`SDD_LOG.md`](SDD_LOG.md) |

## Inicio rápido

```bash
uv sync
uv run ruff check src/
uv run pytest -v
uv run python -m src.adapters.inbound.cli --help
docker compose up --build   # api + db (PostgreSQL 16) → http://localhost:8000/health
```

Ver [`AGENTS.md`](AGENTS.md) para todos los comandos y variables de entorno.
