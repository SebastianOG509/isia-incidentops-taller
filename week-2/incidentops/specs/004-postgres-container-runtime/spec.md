# Feature Specification: Persistencia Relacional Dedicada y Runtime en Contenedores

**Feature Branch**: `004-postgres-container-runtime`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "Necesitamos preparar el servicio para ejecutarse en contenedores junto con una base de datos relacional dedicada en producción y exponer un chequeo real de salud de conectividad." (Decisión arquitectónica previa: ADR-004.)

## Clarifications

### Session 2026-11-24

- Q: ¿Cuál es el contrato del chequeo de salud? → A: Web `GET /health` y comando `health`: ejecutan `SELECT 1` real; sano → `200` con `{"status": "ok", "database": "connected"}`; fallo → `503` con `{"status": "error", "database": "unavailable"}`.
- Q: ¿Cómo se elige el motor? → A: Por `DATABASE_URL`: `postgresql://...` → PostgreSQL; `sqlite:///...` o variable ausente (por defecto `:memory:`) → SQLite; cualquier otro esquema → error de configuración al arrancar.
- Q: ¿Qué compone la orquestación? → A: Imagen `python:3.12-slim` con `uv`, `.dockerignore` limpio y Compose con `db` (`postgres:16-alpine`, volumen persistente, healthcheck `pg_isready`) y `api` (`DATABASE_URL` hacia `db`, `depends_on` con `service_healthy`, healthcheck sobre `/health`).
- Q: ¿Cuánto se espera a la base antes de declararla no disponible? → A: 3 segundos de timeout de conexión.
- Q: ¿Qué código de salida usa la terminal si la base no está disponible? → A: Imprime el JSON de error y termina con código `1` (paridad con `503`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chequeo real de salud (Priority: P1)

El equipo de Plataforma (y el orquestador de contenedores) pregunta al servicio si está sano, y la respuesta
refleja una consulta real a la base de datos configurada, no solo que el proceso esté vivo.

**Why this priority**: sin chequeo real, el orquestador enruta tráfico a un servicio sin base de datos.

**Independent Test**: consultar la salud con la base disponible y con la base caída.

**Acceptance Scenarios**:

1. **Escenario 1 — Salud operativa**: **Given** una base de datos configurada y accesible, **When**
   Plataforma consulta `GET /health` o ejecuta el comando `health`, **Then** se ejecuta una consulta real
   `SELECT 1` y recibe `200` / código `0` con `{"status": "ok", "database": "connected"}`.
2. **Escenario 2 — Fallo de conectividad**: **Given** que la persistencia no logra conectarse (su chequeo
   de salud resulta negativo), **When** Plataforma consulta `GET /health`, **Then** recibe
   `503 Service Unavailable` con `{"status": "error", "database": "unavailable"}`, y el comando `health`
   imprime el mismo JSON y termina con código `1`.

---

### User Story 2 - Selección transparente del motor (Priority: P1)

Desarrollo usa una base embebida sin contenedores y producción usa la base relacional dedicada, cambiando
solo la configuración de conexión.

**Why this priority**: mantiene pruebas rápidas y despliegue productivo con el mismo código.

**Independent Test**: arrancar con distintas configuraciones de conexión y verificar el motor elegido.

**Acceptance Scenarios**:

1. **Escenario 3 — Selección transparente**: **Given** `DATABASE_URL=postgresql://...`, **When** el
   servicio arranca, **Then** usa el motor PostgreSQL; **Given** `DATABASE_URL=sqlite:///...` o la variable
   ausente, **Then** usa SQLite (en memoria por defecto) para desarrollo y pruebas sin contenedores; en
   ambos casos el motor ofrece exactamente las mismas operaciones; **Given** un esquema no soportado,
   **Then** el arranque falla con un error de configuración.

---

### User Story 3 - Orquestación reproducible (Priority: P2)

Plataforma levanta servicio y base de datos con un solo comando, en el orden correcto y con datos que
sobreviven a reinicios.

**Why this priority**: necesario para producción, pero verificable después de US1/US2.

**Independent Test**: validar la definición de orquestación y levantarla en una máquina con contenedores.

**Acceptance Scenarios**:

1. **Escenario 4 — Orquestación en 2 contenedores**: **Given** el repositorio con su imagen (`python:3.12-slim`
   + `uv`), `.dockerignore` y definición de Compose, **When** Plataforma valida la definición y la levanta,
   **Then** existen los servicios `db` (`postgres:16-alpine`, volumen persistente, chequeo `pg_isready`) y
   `api` (conexión apuntando a `db`, arranque condicionado a `db` sana y chequeo sobre `/health`), y
   `http://localhost:8000/health` responde `200`.

### Edge Cases

- Esquema de conexión no soportado → error de configuración al arrancar (no se cae a SQLite en silencio).
- Base que no responde en 3 segundos → se declara no disponible (`503` / código `1`).
- Cualquier excepción del driver durante el chequeo → no disponible, nunca un error `500`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El servicio MUST exponer un chequeo de salud que ejecute una consulta real sobre la base configurada.
- **FR-002**: El chequeo MUST estar disponible por interfaz web y terminal (Constitución, principio III).
- **FR-003**: El motor MUST elegirse únicamente por la configuración de conexión (ADR-004).
- **FR-004**: Ambos motores MUST ofrecer exactamente las mismas operaciones de persistencia.
- **FR-005**: La orquestación MUST definir dos servicios (aplicación y base) con datos persistentes.
- **FR-006**: Un fallo de conectividad MUST producir `503` (web) / código `1` (terminal) con el JSON de error, en ≤ 3 s de espera de conexión.

### Non-Functional Requirements

- **RNF-001 (Portabilidad)**: la suite de pruebas MUST ejecutarse sin daemon de contenedores ni base dedicada.
- **RNF-002 (Disponibilidad)**: el servicio MUST arrancar solo cuando la base esté sana, y su propio estado
  de salud MUST ser observable por el orquestador.
- **RNF-003 (Durabilidad)**: los datos MUST sobrevivir a la recreación del contenedor de base de datos.
- **RNF-004 (Reproducibilidad)**: la imagen MUST construirse con las dependencias bloqueadas del proyecto
  y excluir artefactos locales (entornos virtuales, cachés, bases locales).
- **RNF-005 (Seguridad)**: toda consulta MUST ser parametrizada; las credenciales MUST provenir de configuración.
- **RNF-006 (Paridad temporal)**: ambos motores MUST devolver marcas de tiempo idénticas (ADR-004).

### Key Entities

- **Estado de salud**: estado del servicio y estado de la conexión con la base de datos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con la base caída, el chequeo de salud responde "no disponible" en menos de 5 segundos.
- **SC-002**: El 100 % de las pruebas existentes (Hitos 001–003) siguen pasando sin contenedores.
- **SC-003**: Un solo comando levanta el entorno completo y el chequeo de salud responde sano.

## Assumptions

- Credenciales de ejemplo para entorno local en la orquestación; los secretos productivos se inyectan fuera del repositorio.
- Una sola réplica del servicio en esta versión.
