# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`)

**Estudiante(s)**: `Sebastián Ortiz González`
**Fecha**: `2026-11-24`
**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `Con autorización del monitor, el flujo se ejecutó en Claude Code (no en OpenCode) con un único modelo, Claude Opus 5.5, para todas las fases. Spec Kit se inicializó con --integration opencode y cada /speckit.* se ejecutó siguiendo literalmente su plantilla en .opencode/commands/speckit.*.md (scripts setup-plan.sh, resolve-template.sh, feature.json). Las decisiones abiertas de clarify las tomó el estudiante; las fijadas por las guías se integraron como respuestas acordadas.`

---

## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze`

### 1.1 Feature `003-incident-lifecycle-sla`
- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:
  1. **Zona horaria vs. horario hábil**: la guía pide "normalizar naive/aware" pero no dice *a qué*. Convertir a UTC habría movido un reporte de las 17:00 de Bogotá a las 22:00 y lo habría sacado del horario hábil (SLA de 0 min en vez de 60). Decisión: toda marca con zona se convierte a hora local fija UTC-05:00 (Colombia no tiene horario de verano, así que `datetime.timezone` basta y no se depende de `tzdata`). Quedó probado con `test_normalizacion_naive_y_aware_dan_el_mismo_sla` (`22:00Z` ≡ `17:00` local → 120 min).
  2. **Identificador repetido**: la guía hace opcional `incident_id` pero no dice qué pasa si ya existe. Como el puerto expone `save_incident` como *upsert*, un `POST` con un ID existente habría **sobrescrito** silenciosamente el `created_at` del incidente y borrado su historial de SLA. Decisión: `409 Conflict` / exit `1`; la regla vive en el caso de uso, no en el adaptador.
  3. **Qué texto clasifica**: `title` + `raw_text` o solo `raw_text`. Elegí solo `raw_text` para que `triage` (H001) y `create` (H003) clasifiquen idéntico el mismo reporte.
  4. Casos borde adicionales que ya fijaba la guía y que convertí en escenarios: duplicado con un `RESOLVED` del mismo síntoma (no cuenta), exclusión del propio ID recién creado, `reference_time < created_at` → `422`, estado inicial fuera de los cuatro del dominio → `422`.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - **B1 (MEDIUM) — inconsistencia spec↔plan**: la entidad "Incidente registrado" del spec incluía "texto del reporte", pero el plan (siguiendo la guía) extiende `Incident` solo con `recommended_team` y `duplicate_group_key`. Corregí el spec para declarar que el texto clasifica pero no se conserva.
  - **B2 (MEDIUM) — deriva temporal entre hitos**: el resumen de H002 usaba `datetime.now()` (reloj del host; dentro de Docker sería UTC) mientras H003 usaba hora local UTC-05:00. El mismo incidente habría mostrado SLA distintos en `/summary` y en `/sla`. Se unificó en `now_local()` del dominio.
  - **B3 (LOW) — terminología**: "activo" (H002: `OPEN`/`IN_PROGRESS`) ≠ "abierto" (H003: además `ESCALATION_REQUIRED`). Se aceptó porque ambos los define negocio, pero quedó explícito en cada spec y como constantes separadas.
  - Cobertura: FR-001…FR-011 con tarea; 6 escenarios ↔ 7 pruebas.

### 1.2 Feature `004-postgres-container-runtime`
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**:
  1. **Timeout de conexión (RNF de disponibilidad)**: sin él, `GET /health` con la base caída podía colgarse el timeout por defecto de libpq y el healthcheck de Compose marcaría la API como colgada en lugar de "no disponible". Decisión: `connect_timeout=3` (SC-001 < 5 s, verificado por prueba).
  2. **Código de salida de `health` en la CLI**: imprimir error con exit `0` lo habría hecho inútil para scripts. Decisión: JSON de error + exit `1` (paridad con `503`).
  3. **Arranque con la base caída**: si el adaptador PostgreSQL creaba el esquema en el constructor, la API ni siquiera arrancaría y nunca podría responder `503`. Diseño: esquema perezoso en la primera operación de datos.
  4. **Esquema no soportado en `DATABASE_URL`** (p. ej. `mysql://`): error de configuración explícito en lugar de caer a SQLite en silencio (un despliegue mal configurado escribiría en memoria y perdería datos).
  5. RNF explícitos: portabilidad (suite sin Docker), durabilidad (volumen), reproducibilidad (`uv sync --frozen`), seguridad (SQL parametrizado), paridad temporal (`TEXT` ISO 8601). `/speckit.analyze` marcó que RNF-003 (durabilidad) y el `SELECT 1` real contra PostgreSQL **no pueden** probarse en la suite sin violar RNF-001; se cubrieron con una prueba de contrato opcional (`TEST_POSTGRES_URL`) y verificación manual en contenedores (sección 4).

---

## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos)

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) |
| :--- | :--- | :--- |
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | Un solo archivo (`specs/001-triage-endpoint-manual.md`) mezcla escenarios con decisiones de contrato HTTP/CLI; el plan y las tareas quedaron solo en la conversación, sin versionar. Si hoy alguien pregunta *por qué* `ValidationError` vive en `services.py`, no hay artefacto que lo diga. | `spec.md` (qué/por qué), `plan.md` (cómo, con *Constitution Check*) y `tasks.md` (T### con ruta y dependencias) separados y versionados. Hubo que vigilar la frontera: el spec de 004 tiende a filtrar nombres técnicos (`pg_isready`, `python:3.12-slim`) porque el propio hito es técnico; los dejé solo en *Clarifications* como contrato acordado. |
| **Gestión de ambigüedades (`/speckit.clarify`)** | Dependió de recordar pedir "hazme preguntas antes de escribir". No quedó registro de las preguntas, solo de las respuestas incorporadas al spec. | Marcadores `[NEEDS CLARIFICATION]` (máx. 3) + sección `## Clarifications / Session` con `Q → A`. Las preguntas más valiosas no fueron las que la guía ya respondía, sino las que **no** respondía (zona horaria, ID repetido, timeout): ahí el comando forzó una decisión humana antes de codificar. |
| **Consistencia contra la Constitución (`/speckit.analyze`)** | Ninguna garantía automática: la revisión contra `docs/constitution.md` fue mental. | `analyze` encontró inconsistencias reales que habrían llegado a código (B1 spec↔plan, B2 deriva temporal entre hitos). Ruff (`TID251`) convirtió la Constitución en una verificación ejecutable: probé que `import sqlite3`/`fastapi`/`src.adapters` en `src/domain/` falla el lint. |
| **Riesgo de verbosidad / exceso de Markdown** | Bajo: un archivo corto; el riesgo era el opuesto (información perdida en el chat). | Alto: `specify init` generó 9 comandos, plantillas y scripts, y `/speckit.plan` pide además `research.md`, `data-model.md`, `contracts/` y `quickstart.md` por hito (≈ 7 archivos × 3 hitos). Los condensé dentro de `plan.md` y eliminé secciones de plantilla sin contenido. |

- **Análisis basado en MartinFowler.com (Birgitta Böckeler)**:
  1. **Nivel**: ubico IncidentOps en **Spec-first con anclaje parcial (camino a Spec-anchored)**. Es *spec-first* porque cada hito arrancó por `spec.md` antes de una línea de código. Tiene rasgos de *spec-anchored* porque las specs quedan versionadas por feature y cada escenario está atado 1:1 a un `test_bdd_*`, así que romper el comportamiento rompe la suite. Pero **no es plenamente spec-anchored**: el hallazgo B2 cambió el comportamiento de H002 (de `datetime.now()` a hora local) desde el ciclo de H003, y `specs/002-.../spec.md` no se enmendó; nada en el flujo obligó a volver a esa spec. Y definitivamente **no es spec-as-source**: el código se escribe y revisa a mano, y regenerarlo desde las specs no daría el mismo resultado (p. ej. la migración `ALTER TABLE` o el esquema perezoso no están en ninguna spec).
  2. **Técnicas contra las "montañas de Markdown"**:
     - `docs/ROADMAP.md` es una sola tabla de 4 filas en lenguaje de negocio; ningún hito adelanta rutas ni librerías.
     - En `plan` condensé *research/data-model/contracts* en secciones de `plan.md` (decisión registrada en cada plan) y en `tasks` limité cada hito a 13–16 tareas con ruta concreta.
     - Recorté alcance inventado: el prompt docente de plan de H002 pedía declarar 5 métodos del puerto; declaré solo los 2 que H002 usa y el puerto creció por hito hasta 5 (cada método nace con la prueba que lo ejercita).
     - Leí y corregí lo que el agente proponía en lugar de aprobarlo: la clave `payments-gateway:http-502-outage` de la guía no coincide con el dominio (que agrupa por síntoma, `http-502`); y el ejemplo CLI de la guía (`"HTTP 502 Bad Gateway en pasarela de pagos"`) da **P1**, no P0, porque no hay evidencia de caída *total*. Lo dejé documentado en la spec 001 en vez de "arreglar" el dominio para que coincidiera.
     - Lo que de verdad evita aprobar a ciegas son las verificaciones deterministas: `ruff check src/` y `pytest -v` con escenarios con fechas fijas (viernes 17:00 → lunes 09:00 = 120 min) en vez de "el SLA se calcula correctamente".

---

## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning*

- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-architecture`, `bdd-acceptance`, `adr-writer`)**: los *commands* son **flujos** que el humano dispara explícitamente y que producen un artefacto concreto en un momento concreto (`/speckit.plan` → `plan.md`). Las *skills* son **conocimiento** que el agente carga bajo demanda: al inicio solo se indexan `name` y `description` (por eso la `description` dice *qué hace y cuándo usarla*), y el cuerpo completo se lee solo cuando la tarea lo amerita (*progressive disclosure*), sin inflar `AGENTS.md` en cada turno. Son ortogonales: `bdd-acceptance` se usó *dentro* de `/speckit.specify` y al escribir pruebas; `hexagonal-architecture` dentro de `/speckit.plan` y al corregir imports; `adr-writer` *fuera* del pipeline, porque un ADR no es una feature.
  **Orden causal ADR → Constitución → Hito**: la Constitución solo puede *adoptar* decisiones ya justificadas. En clase, ADR-003 comparó capas acopladas vs. hexagonal antes de que `docs/constitution.md` exigiera puertos y adaptadores. En el Reto 2 el orden fue imprescindible: la Constitución v1.0.0 decía "solo `sqlite3`, sin ORM, cambiar de motor exige un ADR previo". Si se hubiera especificado H004 primero, `/speckit.plan` debía fallar el *Constitution Check* (o, peor, el agente lo habría "justificado" en *Complexity Tracking*). Por eso: ADR-004 (reemplaza **parcialmente** a ADR-001) → `/speckit.constitution` v1.1.0 (principio IV ampliado, `psycopg` permitido solo en `adapters/outbound/`) → `specify/plan` de 004, que ya pasó el gate sin excepciones.
- **Valor de la Arquitectura Hexagonal**: H004 lo demostró con números: agregar PostgreSQL tocó **0 líneas** de `src/domain/`, añadió un archivo (`postgres_repository.py`), agregó una rama en `factory.py` y sumó `check_health()` al puerto y al servicio. FastAPI y Typer no se enteraron del motor porque ambos piden el repositorio a `create_repository(DATABASE_URL)` y llaman a `IncidentService`. La paridad REST/CLI se volvió casi gratis al compartir `presenters.py`: la prueba de H002 compara el JSON de la API y el de la CLI con un `==`. Que el puerto sea `typing.Protocol` permitió el doble `FailingRepository` para probar el `503` sin tocar producción. Futuros adaptadores: un servidor MCP sería un tercer adaptador primario sobre los mismos 5 casos de uso; otro motor sería otro adaptador que pase la misma prueba de "expone exactamente las operaciones del puerto".
- **Uso intencional de *Reasoning / Extended Thinking***: con un único modelo (Opus 5.5) no pude contrastar modelos, así que la reflexión es sobre *dónde rindió pensar más despacio*. Aportó más en **`/speckit.clarify`** (detectar que "normalizar naive/aware" escondía una decisión de negocio sobre el horario hábil, o que el upsert del puerto permitía sobrescribir historial) y en **`/speckit.analyze`** (B2 solo aparece si se cruzan dos hitos distintos). En `/speckit.plan` sirvió para decisiones con consecuencias diferidas (esquema perezoso para poder responder `503`). En **`/speckit.implement`** el trabajo era mecánico y completamente determinado por `tasks.md` + pruebas: ahí un modelo rápido habría bastado, y la verificación real la hicieron Ruff y pytest, no el razonamiento.

---

## 4. Evidencia de Verificación Determinista
- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**:
```text
$ uv run ruff check src/
All checks passed!

# Prueba negativa de las fronteras (archivo temporal en src/domain/, luego borrado):
TID251 `sqlite3` is banned: El dominio no conoce la persistencia (ADR-003).
TID251 `fastapi` is banned: El dominio no conoce HTTP (ADR-003).
TID251 `fastapi` is banned: El dominio no conoce HTTP (ADR-003).
TID251 `src.adapters` is banned: El dominio no depende de adaptadores (ADR-003).
Found 8 errors.
```
- **Salida completa de `uv run pytest -v`**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Sebas\Maestria\Ingeniería de Software Asistida por IA\week-2\incidentops
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 31 items

tests/test_spec_001_triage.py::test_bdd_escenario_1_caida_critica_pasarela_pagos PASSED [  3%]
tests/test_spec_001_triage.py::test_bdd_escenario_2_cuenta_bloqueada_sin_falso_p0 PASSED [  6%]
tests/test_spec_001_triage.py::test_bdd_escenario_3_entradas_vacias_retornan_422 PASSED [  9%]
tests/test_spec_001_triage.py::test_bdd_escenario_4_paridad_cli PASSED   [ 12%]
tests/test_spec_001_triage.py::test_bdd_escenario_4b_cli_entrada_vacia_sale_con_1 PASSED [ 16%]
tests/test_spec_002_summary.py::test_bdd_escenario_1_resumen_global_excluye_resueltos PASSED [ 19%]
tests/test_spec_002_summary.py::test_bdd_escenario_2_filtro_por_componente PASSED [ 22%]
tests/test_spec_002_summary.py::test_bdd_escenario_3_resumen_vacio PASSED [ 25%]
tests/test_spec_002_summary.py::test_bdd_escenario_4_paridad_cli PASSED  [ 29%]
tests/test_spec_002_summary.py::test_sqlite_cumple_incident_repository_port PASSED [ 32%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_1_registro_inicial_sin_duplicados PASSED [ 35%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_1b_entradas_invalidas_y_id_repetido PASSED [ 38%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_2_duplicado_abierto_ignora_resueltos PASSED [ 41%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_3_auditoria_sla_horario_habil PASSED [ 45%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_4_sla_inexistente_404_y_tiempo_anterior_422 PASSED [ 48%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_escenario_5_paridad_cli_create_y_sla PASSED [ 51%]
tests/test_spec_003_lifecycle_sla.py::test_normalizacion_naive_y_aware_dan_el_mismo_sla PASSED [ 54%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_1_health_operativo_api PASSED [ 58%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_1_health_operativo_cli PASSED [ 61%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_2_health_503_con_doble_de_prueba PASSED [ 64%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_2_health_cli_sale_con_1_si_la_base_no_responde PASSED [ 67%]
tests/test_spec_004_runtime_health.py::test_postgres_inalcanzable_se_reporta_en_menos_de_5_segundos PASSED [ 70%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_seleccion_de_motor_por_database_url[None-SQLiteIncidentRepository] PASSED [ 74%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_seleccion_de_motor_por_database_url[-SQLiteIncidentRepository] PASSED [ 77%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_seleccion_de_motor_por_database_url[sqlite:///:memory:-SQLiteIncidentRepository] PASSED [ 80%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_seleccion_de_motor_por_database_url[postgresql://u:p@db:5432/incidentops-PostgresIncidentRepository] PASSED [ 83%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_seleccion_de_motor_por_database_url[postgres://u:p@db:5432/incidentops-PostgresIncidentRepository] PASSED [ 87%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_3_esquema_no_soportado_falla_al_arrancar PASSED [ 90%]
tests/test_spec_004_runtime_health.py::test_ambos_adaptadores_exponen_exactamente_las_operaciones_del_puerto PASSED [ 93%]
tests/test_spec_004_runtime_health.py::test_contrato_postgres_real_paridad_temporal_y_duplicados SKIPPED [ 96%]
tests/test_spec_004_runtime_health.py::test_bdd_escenario_4_estructura_de_archivos_docker PASSED [100%]

================== 30 passed, 1 skipped, 1 warning in 6.39s ===================

# El único SKIPPED es la prueba de contrato contra PostgreSQL real (requiere TEST_POSTGRES_URL,
# por RNF-001 la suite no exige Docker). Ejecutada aparte contra un postgres:16-alpine temporal:
$ TEST_POSTGRES_URL=postgresql://test:test@127.0.0.1:55432/test uv run pytest tests/test_spec_004_runtime_health.py -k postgres_real -v
tests/test_spec_004_runtime_health.py::test_contrato_postgres_real_paridad_temporal_y_duplicados PASSED [100%]
# (El warning es una deprecación de Starlette sobre httpx, ajena al proyecto.)
```
- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose up --build`)**:
```text
$ uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en todas las transacciones de la pasarela de pagos"
{
  "incident_id": "INC-1001",
  "severity": "P0",
  "component": "payments-gateway",
  "recommended_team": "Backend-Core",
  "duplicate_group_key": "payments-gateway:http-502",
  "rationale": "[payments-total-outage] Caída total del flujo de cobro: pérdida de ingresos inmediata.",
  "consistency_ratio": 1.0
}
$ export DATABASE_URL=sqlite:///.../evid.db
$ uv run python -m src.adapters.inbound.cli create --incident-id INC-CLI00001 --title "Cuenta bloqueada" --raw-text "mi cuenta aparece bloqueada" --created-at 2026-11-06T17:00:00
{
  "incident_id": "INC-CLI00001",
  "title": "Cuenta bloqueada",
  "status": "OPEN",
  "created_at": "2026-11-06T17:00:00",
  "severity": "P2",
  "component": "auth-identity",
  "recommended_team": "Security-IAM",
  "duplicate_group_key": "auth-identity:account-locked",
  "rationale": "[single-account-locked] Un único usuario afectado; la urgencia declarada no eleva el impacto.",
  "is_duplicate": false,
  "duplicate_of": []
}
$ uv run python -m src.adapters.inbound.cli sla INC-CLI00001 --reference-time 2026-11-09T09:00:00
{
  "incident_id": "INC-CLI00001",
  "severity": "P2",
  "elapsed_minutes": 120,
  "allowed_minutes": 480,
  "remaining_minutes": 360,
  "is_breached": false,
  "requires_escalation": false
}
$ uv run python -m src.adapters.inbound.cli summary --reference-time 2026-11-09T09:00:00
{
  "total_active": 1,
  "breached_count": 0,
  "incidents": [
    {
      "incident_id": "INC-CLI00001",
      "title": "Cuenta bloqueada",
      "component": "auth-identity",
      "severity": "P2",
      "status": "OPEN",
      "elapsed_minutes": 120,
      "allowed_minutes": 480,
      "is_breached": false,
      "requires_escalation": false
    }
  ]
}
$ uv run python -m src.adapters.inbound.cli health
{
  "status": "ok",
  "database": "connected"
}
(exit 0)
$ DATABASE_URL=postgresql://incidentops:incidentops@127.0.0.1:1/incidentops uv run python -m src.adapters.inbound.cli health
{
  "status": "error",
  "database": "unavailable"
}
(exit 1)

$ docker compose config -q && echo "Compose OK"
Compose OK

$ docker compose up --build -d
 Volume incidentops_pgdata Created
 Network incidentops_default Created
 Container incidentops-db-1 Created
 Container incidentops-api-1 Created
 Container incidentops-db-1 Started
 Container incidentops-db-1 Waiting
 Container incidentops-db-1 Healthy
 Container incidentops-api-1 Starting
 Container incidentops-api-1 Started

$ docker compose ps
NAME                IMAGE                COMMAND                  SERVICE   STATUS                        PORTS
incidentops-api-1   incidentops-api      "uvicorn src.adapter…"   api       Up About a minute (healthy)   0.0.0.0:8000->8000/tcp
incidentops-db-1    postgres:16-alpine   "docker-entrypoint.s…"   db        Up 47 seconds (healthy)       5432/tcp

$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","database":"connected"}

# Flujo real sobre PostgreSQL dentro de Compose:
$ curl -X POST localhost:8000/api/v1/incidents -d '{"incident_id":"INC-DOCKER01","title":"Cuenta bloqueada","raw_text":"mi cuenta aparece bloqueada","created_at":"2026-11-06T17:00:00"}'
{"incident_id":"INC-DOCKER01",...,"severity":"P2","recommended_team":"Security-IAM","is_duplicate":false,"duplicate_of":[]}
$ curl "localhost:8000/api/v1/incidents/INC-DOCKER01/sla?reference_time=2026-11-09T09:00:00"
{"incident_id":"INC-DOCKER01","severity":"P2","elapsed_minutes":120,"allowed_minutes":480,"remaining_minutes":360,"is_breached":false,"requires_escalation":false}

# 503 real y durabilidad (RNF-003): se elimina el contenedor db y se recrea sobre el mismo volumen
$ docker compose rm -sf db && curl -w "%{http_code} " localhost:8000/health
503 {"status":"error","database":"unavailable"}
$ docker compose up -d db && curl localhost:8000/health
{"status":"ok","database":"connected"}
$ curl "localhost:8000/api/v1/incidents/INC-DOCKER01/sla?reference_time=2026-11-09T09:00:00"
{"incident_id":"INC-DOCKER01","severity":"P2","elapsed_minutes":120,"allowed_minutes":480,"remaining_minutes":360,"is_breached":false,"requires_escalation":false}
```
