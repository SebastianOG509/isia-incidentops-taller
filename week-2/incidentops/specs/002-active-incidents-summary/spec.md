# Feature Specification: Resumen de Incidentes Activos

**Feature Branch**: `002-active-incidents-summary`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "Necesitamos consultar el resumen de incidentes actualmente activos (OPEN e IN_PROGRESS) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente."

## Clarifications

### Session 2026-11-24

- Q: ¿Qué se responde si no hay activos o el filtro no coincide? → A: Respuesta exitosa con `total_active=0`, `breached_count=0` e `incidents=[]` (nunca error).
- Q: ¿Contra qué instante se miden los minutos transcurridos? → A: Instante de referencia opcional (`reference_time`, ISO 8601); por defecto, el instante actual.
- Q: ¿Cómo se expone la consulta en cada interfaz? → A: Web `GET /api/v1/incidents/summary?component=...`; terminal `summary [--component ...] [--reference-time ...]`.
- Q: ¿Qué escenarios de aceptación cierran el alcance? → A: Cuatro: resumen global excluyendo resueltos, filtrado por componente, caso vacío y consulta equivalente por terminal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Panorama global de incidentes activos (Priority: P1)

El equipo de Operaciones consulta, desde el dashboard web, cuántos incidentes siguen activos, cuántos ya
incumplieron su SLA y el detalle de cada uno, para priorizar el trabajo del turno.

**Why this priority**: es la vista mínima que justifica el hito; sin ella no hay seguimiento de SLA.

**Independent Test**: registrar incidentes activos y resueltos y verificar que el resumen solo cuenta los activos.

**Acceptance Scenarios**:

1. **Given** un P0 abierto de `payments-gateway` creado el lunes 2026-11-09 a las 08:00, un P2 en progreso
   de `reporting-api` creado ese mismo lunes a las 10:00 y un P1 resuelto, **When** Operaciones consulta el
   resumen con instante de referencia lunes 2026-11-09 a las 12:00, **Then** ve `total_active=2`,
   `breached_count=1` (el P0, con 240 min transcurridos y escalamiento requerido) y el detalle de ambos
   activos, sin el incidente resuelto.

---

### User Story 2 - Resumen filtrado por componente (Priority: P2)

Un líder técnico consulta solo los incidentes activos de su componente.

**Why this priority**: reduce ruido para cada equipo, pero el resumen global ya entrega valor por sí solo.

**Independent Test**: con incidentes activos en varios componentes, filtrar por uno y verificar el conteo.

**Acceptance Scenarios**:

1. **Given** los incidentes del Escenario 1, **When** se consulta el resumen filtrando por el componente
   `reporting-api` en el mismo instante, **Then** aparece solo el P2 (120 min hábiles transcurridos),
   con `total_active=1` y `breached_count=0`.
2. **Given** que no hay incidentes activos en el componente `frontend-ui`, **When** se consulta el resumen
   filtrando por ese componente, **Then** la respuesta es exitosa con `total_active=0`, `breached_count=0`
   e `incidents=[]`.

---

### User Story 3 - Consulta equivalente desde la terminal (Priority: P3)

Soporte obtiene el mismo resumen desde la terminal.

**Why this priority**: paridad entre interfaces exigida por la Constitución.

**Independent Test**: comparar el resumen de terminal con el de la interfaz web para los mismos datos.

**Acceptance Scenarios**:

1. **Given** los mismos incidentes del Escenario 1, **When** soporte consulta el resumen desde la terminal,
   **Then** obtiene el mismo resumen en formato estructurado.

### Edge Cases

- Sin activos o sin coincidencias para el filtro → respuesta exitosa con totales en cero y lista vacía.
- Sin instante de referencia → se usa el instante actual; con él, el resultado es determinista.
- Incidentes en `ESCALATION_REQUIRED` o `RESOLVED` no forman parte del resumen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST considerar activos únicamente los incidentes en estado `OPEN` o `IN_PROGRESS`.
- **FR-002**: El resumen MUST incluir el total de activos, el número de activos con SLA incumplido y el
  detalle de cada activo: identificador, título, componente, severidad, estado, minutos transcurridos y si
  requiere escalamiento.
- **FR-003**: Los minutos transcurridos, el incumplimiento y el escalamiento MUST calcularse con las reglas
  de SLA del dominio (24/7 para P0/P1, horario hábil para P2/P3, escalamiento al 75 %).
- **FR-004**: El resumen MUST poder filtrarse opcionalmente por componente.
- **FR-005**: El resumen MUST estar disponible por interfaz web y por terminal con el mismo resultado.
- **FR-006**: El instante de referencia MUST ser opcional; si se omite se usa el instante actual.
- **FR-007**: Un resumen sin coincidencias MUST responder con éxito, totales en cero y lista vacía.

### Key Entities

- **Incidente activo**: incidente en estado abierto o en progreso, con severidad, componente y fecha de creación.
- **Resumen de activos**: totales agregados más la lista de incidentes activos con su evaluación de SLA.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para un conjunto conocido de incidentes, el total de activos y de incumplidos coincide al 100 %
  con el cálculo manual de las reglas de SLA.
- **SC-002**: Ningún incidente resuelto aparece jamás en el resumen.
- **SC-003**: Web y terminal devuelven resúmenes idénticos para los mismos datos e instante de referencia.

## Assumptions

- No se requiere paginación en esta versión (volúmenes operativos de cientos de activos).
- `ESCALATION_REQUIRED` no se considera "activo" para este resumen, según la definición del requerimiento.
- Los datos se leen del almacenamiento de incidentes existente.
