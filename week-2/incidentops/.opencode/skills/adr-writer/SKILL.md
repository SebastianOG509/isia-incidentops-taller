---
name: adr-writer
description: Redacta un Architecture Decision Record (ADR) en formato MADR estricto en docs/adr/NNN-titulo.md usando docs/adr/000-template.md. Úsala cuando haya que registrar o evaluar una decisión arquitectónica estructural y difícil de revertir (motor de base de datos, topología de despliegue, estilo de arquitectura, protocolo de integración) antes de cambiar la Constitución o especificar un hito. No la uses para requisitos funcionales (spec.md) ni para planes de tareas (plan.md).
---

# ADR Writer (MADR estricto)

## Antes de escribir

1. Lee `docs/adr/000-template.md` (estructura obligatoria), los ADR existentes en `docs/adr/` y
   `.specify/memory/constitution.md` (restricciones vigentes).
2. Identifica **la única decisión** a registrar. Si la petición contiene varias decisiones
   independientes, sepáralas en varios ADR y pregunta cuál redactar primero.
3. Comprueba que sea **estructural y difícil de revertir** (afecta fronteras, despliegue, datos o
   contratos entre componentes). Si se revierte cambiando un archivo, no es un ADR: dilo y detente.
4. Número = siguiente libre en `docs/adr/`; archivo `NNN-titulo-en-kebab-case.md`.

## Reglas de contenido

- **Metadatos**: `Estado` (Propuesto | Aceptado | Reemplazado por ADR-XXX), `Fecha` ISO, `Autor(es)`
  y `Reemplaza a`. Si la decisión invalida total o parcialmente una restricción de un ADR previo,
  nómbralo en `Reemplaza a` indicando **parcial** o **total** y qué parte exactamente.
- **No** añadas `Componentes Afectados`, rutas de archivos, listas de tareas, comandos ni una
  sección de `Verificación`: eso pertenece a `plan.md` / `tasks.md`.
- **Contexto**: problema, fuerzas y restricciones vigentes. No copies escenarios BDD ni requisitos de
  `spec.md`; refiérete a la necesidad de negocio en una frase.
- **Opciones**: mínimo **2 alternativas reales** que un equipo razonable elegiría, cada una con
  ventajas y desventajas auténticas. Prohibidas las opciones de relleno ("no hacer nada" solo vale si
  es de verdad viable) y los *strawmen* sin ventajas.
- **Decisión**: qué opción y **por qué** frente a las demás (qué fuerza pesó más).
- **Mermaid (opcional)**: solo diagramas **estructurales** (`flowchart` de capas, fronteras, contenedores
  o topología). Nunca flujos algorítmicos `if/else`, secuencias de llamadas ni pasos de proceso.
- **Consecuencias**: positivas y negativas/trade-offs honestos, incluyendo costos operativos.

## Inmutabilidad (append-only)

- Nunca edites la decisión de un ADR `Aceptado`. Si cambia, crea un ADR nuevo que lo reemplace.
- En el ADR reemplazado solo se permite actualizar el campo `Estado` (p. ej. "Aceptado *(parcialmente
  reemplazado por ADR-NNN)*").

## Después de escribir

1. Revisa la lista: 1 decisión · ≥2 opciones reales · sin rutas/tareas/BDD · Mermaid estructural ·
   `Reemplaza a` correcto.
2. Indica al usuario que el siguiente paso es enmendar la Constitución con `/speckit.constitution`
   antes de especificar el hito que dependa de esta decisión.
