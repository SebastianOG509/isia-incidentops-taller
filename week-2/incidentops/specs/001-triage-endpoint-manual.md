# Especificación 001 — Triaje Multi-Interfaz (SDD manual)

- **Hito**: H001 (`docs/ROADMAP.md`)
- **Fecha**: 2026-11-24
- **Estado**: Aprobada

## Requerimiento crudo

> "Necesitamos exponer el motor de triaje como servicio HTTP para que el frontend lo consuma y también como
> comando CLI para que soporte pueda probar reportes rápido desde terminal."

## Decisiones acordadas en la elicitación

- **Operación stateless**: el triaje no se guarda; ambas interfaces invocan un único caso de uso compartido.
- **Interfaz web**: `POST /api/v1/incidents/triage` con `{"incident_id": str, "raw_text": str}`; responde
  `200 OK` con la clasificación completa (severidad, componente, equipo recomendado, clave de duplicado,
  justificación y ratio de consistencia).
- **Interfaz de terminal**: subcomando `triage --incident-id ... --raw-text ...` que imprime el mismo resultado
  en JSON (código de salida `0`).
- **Entradas inválidas**: identificador o texto vacíos o solo con espacios → `422 Unprocessable Entity` en web;
  mensaje de error y código de salida `1` en terminal.

## Escenarios de aceptación (BDD)

### Escenario 1 — Caída crítica de la pasarela de pagos
- **Given** un reporte `INC-1001` que indica que la pasarela de pagos devuelve HTTP 502 Bad Gateway en todas
  las transacciones y ningún comercio puede cobrar
- **When** soporte solicita su triaje por la interfaz web
- **Then** recibe `200` con severidad `P0`, componente `payments-gateway`, equipo `Backend-Core` y clave de
  duplicado `payments-gateway:http-502`

### Escenario 2 — Cuenta individual bloqueada con urgencia declarada
- **Given** un reporte de un usuario cuya cuenta quedó bloqueada y que dice necesitar acceso "hoy"
- **When** se solicita su triaje por la interfaz web
- **Then** recibe `200` con severidad `P2` y equipo `Security-IAM`, sin elevarse a `P0` por la urgencia declarada

### Escenario 3 — Entradas vacías
- **Given** un reporte con texto `"   "` o con identificador `""`
- **When** se solicita su triaje por la interfaz web
- **Then** recibe `422 Unprocessable Entity` y no se produce ninguna clasificación

### Escenario 4 — Paridad desde la terminal
- **Given** el mismo reporte de caída de la pasarela de pagos del Escenario 1
- **When** soporte ejecuta `triage --incident-id INC-1001 --raw-text "..."`
- **Then** la terminal imprime JSON válido con severidad `P0` y equipo `Backend-Core`, y termina con código `0`

> **Nota de alineación con el dominio**: la guía del curso menciona la clave
> `payments-gateway:http-502-outage`; el motor de triaje vigente (Semana 1, auditado 10/10) produce
> `payments-gateway:http-502` porque la clave agrupa por **síntoma**, no por severidad (así una degradación
> P1 y una caída P0 del mismo síntoma se detectan como duplicadas). Se conserva la clave del dominio.
