# Feature Specification: Ciclo de Vida de Incidentes, Duplicados y Auditoría de SLA

**Feature Branch**: `003-incident-lifecycle-sla`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "Necesitamos guardar los incidentes cuando llegan, avisar si ya había otro equivalente abierto, y consultar cómo va su SLA tanto por API como desde nuestra herramienta CLI."

## Clarifications

### Session 2026-11-24

- Q: ¿Qué campos exige el registro y cómo se rechazan los inválidos? → A: `title` y `raw_text` obligatorios; vacíos o solo espacios → `422` en web / código de salida `1` en terminal.
- Q: ¿Qué valores toman los campos opcionales omitidos? → A: `incident_id` = `INC-<HEX8>` autogenerado; `created_at` = instante actual; `status` = `OPEN`.
- Q: ¿Qué devuelve un registro exitoso? → A: `201 Created` (web) o JSON (terminal) con la clasificación completa, `is_duplicate` (booleano) y `duplicate_of` (lista de identificadores).
- Q: ¿Cuándo un incidente es "equivalente abierto"? → A: misma clave de equivalencia (`duplicate_group_key`) y estado `OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`; se excluyen los `RESOLVED` y el propio incidente recién creado.
- Q: ¿Cómo se consulta el SLA y qué errores existen? → A: `GET /api/v1/incidents/{incident_id}/sla` y comando `sla`, con `reference_time` ISO 8601 opcional (por defecto ahora); inexistente → `404`; `reference_time` anterior a la creación → `422`; ambos → código `1` en terminal.
- Q: ¿Cómo se interpretan horas con zona horaria frente al horario hábil? → A: Toda hora con zona se convierte a la hora local de operación (UTC-05:00, Bogotá, sin horario de verano) y se trata como hora local; las horas sin zona se asumen ya locales.
- Q: ¿Qué ocurre si se registra un identificador que ya existe? → A: Se rechaza con `409 Conflict` (código `1` en terminal); el registro nunca sobrescribe un incidente existente.
- Q: ¿Qué texto determina la clasificación? → A: Solo el texto del reporte (`raw_text`), igual que el triaje del Hito 001; el título es una etiqueta descriptiva.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar un incidente entrante (Priority: P1)

Soporte registra cada reporte que llega; el sistema lo clasifica (severidad, componente, equipo recomendado)
y lo conserva para su seguimiento.

**Why this priority**: sin registro persistente no hay duplicados ni auditoría de SLA.

**Independent Test**: registrar un reporte en un sistema vacío y verificar la clasificación devuelta.

**Acceptance Scenarios**:

1. **Escenario 1 — Registro inicial sin duplicados previos**: **Given** un sistema sin incidentes, **When**
   soporte registra el reporte "Caída de cobros" con el texto "La pasarela de pagos devuelve HTTP 502 Bad
   Gateway en todas las transacciones", **Then** recibe `201` con severidad `P0`, componente
   `payments-gateway`, equipo `Backend-Core`, estado `OPEN`, un identificador `INC-<HEX8>`,
   `is_duplicate=false` y `duplicate_of=[]`.
2. **Escenario 1b — Entradas inválidas**: **Given** un reporte con título `"   "` o texto vacío, **When**
   soporte intenta registrarlo, **Then** recibe `422` y nada queda registrado; **And Given** un incidente
   `INC-1001` ya registrado, **When** se registra otro con ese mismo identificador, **Then** recibe `409`.

---

### User Story 2 - Alertar duplicados abiertos (Priority: P1)

Al registrar un reporte, soporte sabe de inmediato si ya existe otro incidente equivalente sin resolver, para
no abrir dos frentes de trabajo sobre el mismo problema.

**Why this priority**: evita esfuerzo duplicado durante incidentes masivos (p. ej. caída de pagos).

**Independent Test**: registrar dos reportes del mismo problema y verificar que el segundo referencia al primero.

**Acceptance Scenarios**:

1. **Escenario 2 — Detección de duplicado abierto**: **Given** un incidente `INC-OPEN-01` abierto y un
   incidente `INC-RES-01` resuelto, ambos de caída de la pasarela de pagos por HTTP 502, **When** soporte
   registra un nuevo reporte del mismo problema, **Then** recibe `201` con `is_duplicate=true` y
   `duplicate_of=["INC-OPEN-01"]` (el resuelto no aparece).

---

### User Story 3 - Auditar el SLA de un incidente (Priority: P2)

Un líder de turno consulta cuánto SLA ha consumido un incidente en un instante dado y si requiere escalamiento.

**Why this priority**: permite auditar cumplimiento, pero depende de que el incidente exista (US1).

**Independent Test**: registrar un incidente con fecha conocida y consultarlo en un instante conocido.

**Acceptance Scenarios**:

1. **Escenario 3 — Auditoría determinista en horario hábil**: **Given** un incidente `P2` (cuenta de
   usuario bloqueada) registrado el viernes 2026-11-06T17:00:00, **When** se consulta su SLA con instante
   de referencia lunes 2026-11-09T09:00:00, **Then** obtiene `elapsed_minutes=120`, `allowed_minutes=480`,
   `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.
2. **Escenario 4 — Consultas inválidas**: **Given** que no existe `INC-NOPE0000`, **When** se consulta su
   SLA, **Then** recibe `404 Not Found`; **And Given** el incidente del Escenario 3, **When** se consulta con
   instante 2026-11-06T16:00:00 (anterior a su creación), **Then** recibe `422 Unprocessable Entity`.

---

### User Story 4 - Operación equivalente desde la terminal (Priority: P2)

Soporte registra incidentes y audita su SLA desde la terminal con el mismo resultado que la interfaz web.

**Why this priority**: paridad entre interfaces (Constitución, principio III).

**Independent Test**: ejecutar `create` y luego `sla` sobre el mismo almacenamiento.

**Acceptance Scenarios**:

1. **Escenario 5 — Paridad CLI**: **Given** un almacenamiento vacío, **When** soporte ejecuta `create` con
   identificador `INC-CLI00001`, el reporte de cuenta bloqueada y creación 2026-11-06T17:00:00, y luego `sla
   INC-CLI00001 --reference-time 2026-11-09T09:00:00`, **Then** ambos comandos terminan con código `0`,
   `create` imprime la clasificación (`P2`, `Security-IAM`, `is_duplicate=false`) y `sla` imprime
   `elapsed_minutes=120` y `remaining_minutes=360`; **And When** ejecuta `sla INC-NOPE0000`, **Then** termina
   con código `1`.

### Edge Cases

- Título o texto vacíos o solo espacios → `422` / código `1`.
- Incidentes equivalentes `RESOLVED` no cuentan como duplicados; el propio incidente tampoco.
- SLA de incidente inexistente → `404`; instante anterior a la creación → `422`.
- Horas con zona → se convierten a hora local UTC-05:00; sin zona → se asumen locales.
- Identificador ya existente → `409` / código `1`, sin sobrescribir.
- Estado inicial inválido (fuera de los cuatro estados del dominio) → `422`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST registrar de forma persistente cada incidente entrante con su clasificación.
- **FR-002**: El sistema MUST indicar en el registro si existe otro incidente equivalente abierto y cuáles.
- **FR-003**: El sistema MUST permitir consultar la evaluación de SLA de un incidente registrado en un
  instante de referencia.
- **FR-004**: Registro y consulta MUST estar disponibles por interfaz web y por terminal con igual resultado.
- **FR-005**: Las reglas de severidad, equivalencia y SLA MUST ser las del dominio (Constitución, principio I).
- **FR-006**: `title` y `raw_text` MUST ser obligatorios y no vacíos; `incident_id` (`INC-<HEX8>`),
  `created_at` (ahora) y `status` (`OPEN`) MUST tener valores por defecto.
- **FR-007**: Equivalente abierto MUST significar misma clave y estado `OPEN`/`IN_PROGRESS`/
  `ESCALATION_REQUIRED`, excluyendo `RESOLVED` y el propio incidente.
- **FR-008**: La consulta de SLA MUST aceptar un instante de referencia opcional y responder `404` si el
  incidente no existe y `422` si el instante es anterior a la creación.
- **FR-009**: Las horas con zona horaria MUST normalizarse a hora local UTC-05:00 antes de evaluar el SLA.
- **FR-010**: Registrar un identificador existente MUST rechazarse con `409` sin modificar el original.
- **FR-011**: La clasificación MUST derivarse únicamente del texto del reporte.

### Key Entities

- **Incidente registrado**: identificador, título, componente, severidad, estado, equipo recomendado, clave
  de equivalencia y fecha de creación (el texto del reporte se usa para clasificar, no se conserva).
- **Evaluación de SLA**: minutos transcurridos, permitidos y restantes; incumplimiento; escalamiento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los reportes registrados se recuperan con la misma clasificación con que se crearon.
- **SC-002**: Ningún incidente resuelto se reporta como duplicado abierto.
- **SC-003**: La evaluación de SLA de un instante fijo es idéntica en cada consulta y en ambas interfaces.

## Assumptions

- La edición de estado de un incidente (pasar a `RESOLVED`) queda fuera de alcance de este hito.
- La persistencia vigente es la definida por la Constitución (principio IV).
