---
name: bdd-acceptance
description: Redacta escenarios BDD Given/When/Then en lenguaje de negocio para specs/*/spec.md y los traduce 1:1 a pruebas pytest test_bdd_* con TestClient (FastAPI) y CliRunner (Typer). Úsala al ejecutar /speckit.specify o /speckit.clarify, al escribir criterios de aceptación o al crear tests/test_spec_<NNN>_*.py.
---

# Aceptación BDD en IncidentOps

## 1. Escribir escenarios en `spec.md` (estilo Dan North)

```markdown
### Escenario N — <comportamiento observable en una frase>
- **Given** <contexto de negocio: qué incidentes existen, en qué estado, a qué hora>
- **When** <una sola acción del actor: soporte registra / consulta / solicita>
- **Then** <resultado observable: respuesta, valores clave, código de salida>
```

Reglas:
- Vocabulario ubicuo del negocio: incidente, severidad P0–P3, SLA, horario hábil, duplicado abierto,
  equipo recomendado, interfaz web / terminal. **Prohibido** filtrar nombres de clases Python, módulos,
  tablas o columnas SQL.
- Los códigos HTTP (`201`, `404`, `422`, `503`) y nombres de campos del contrato público sí se permiten
  en el **Then**: son parte del contrato observable.
- Fechas y horas concretas (ISO 8601) para que el escenario sea determinista; indica el día de la semana
  cuando importe el horario hábil.
- Un escenario = un comportamiento. Incluye siempre: camino feliz, caso borde, error de entrada y la
  paridad web ↔ terminal.

## 2. Mapear cada escenario a una prueba (1:1)

- Archivo: `tests/test_spec_<NNN>_<slug>.py`. Función: `test_bdd_escenario_<n>_<slug>`.
- Usa las fixtures de `tests/conftest.py`: `client` (`TestClient(create_app(service))`), `runner`
  (`CliRunner`) y `service` con repositorio **aislado** (`sqlite:///:memory:` nuevo por prueba).
- Given → preparar datos vía `IncidentService` o vía la API; When → una llamada HTTP o `runner.invoke`;
  Then → `assert` sobre status/exit code y los campos del contrato mencionados en el escenario.
- La paridad CLI se prueba con `runner.invoke(cli_app, [...], env={"DATABASE_URL": ...})` o inyectando
  el mismo servicio; parsea `result.stdout` con `json.loads`.
- Nunca dependas del reloj real: pasa `reference_time`/`created_at` explícitos.

## 3. Verificar

```bash
uv run pytest -v   # cada escenario del spec debe aparecer como un test_bdd_* en PASSED
```
