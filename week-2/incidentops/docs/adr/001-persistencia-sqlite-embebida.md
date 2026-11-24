# ADR-001: Persistencia embebida con `sqlite3` de la biblioteca estándar

- **Estado**: Aceptado *(parcialmente reemplazado por ADR-004)*
- **Fecha**: 2026-11-05 *(registrado retroactivamente el 2026-11-24 para documentar la restricción heredada del proyecto semilla de la Semana 1)*
- **Autor(es)**: Sebastián Ortiz González
- **Reemplaza a**: —

---

## 1. Contexto y Problema

El proyecto semilla de IncidentOps necesita almacenar incidentes y políticas de SLA para laboratorios locales y benchmarks reproducibles (10.000 registros). La decisión estructural es **qué motor de persistencia adopta el sistema**. Restricciones: entorno académico sin infraestructura compartida, ejecución con un solo comando (`uv run`) y mínimo número de dependencias externas.

---

## 2. Opciones Consideradas

1. **Opción A — `sqlite3` embebido de la biblioteca estándar**:
   - *Ventajas*: cero dependencias ni servicios externos; base `:memory:` ideal para pruebas aisladas y deterministas; SQL real (índices, `JOIN`) para enseñar optimización.
   - *Desventajas*: un solo escritor concurrente; no representa un despliegue productivo multi-instancia.
2. **Opción B — Servidor relacional dedicado (PostgreSQL) con driver externo**:
   - *Ventajas*: concurrencia real, paridad con producción, herramientas operativas maduras.
   - *Desventajas*: exige un servicio corriendo y una dependencia externa desde el primer día; eleva la fricción del laboratorio.

---

## 3. Decisión Arquitectónica

Se adopta la **Opción A**: persistencia únicamente con `sqlite3` de la biblioteca estándar, sin ORM ni drivers externos. Prima la reproducibilidad local y la ausencia de dependencias sobre la paridad productiva, que aún no es un requisito.

---

## 4. Consecuencias y Trade-offs

- **Positivas**: arranque instantáneo, pruebas herméticas con `:memory:`, cero configuración.
- **Negativas / Trade-offs**: cualquier despliegue con base de datos dedicada exigirá un nuevo ADR que reemplace esta restricción.
