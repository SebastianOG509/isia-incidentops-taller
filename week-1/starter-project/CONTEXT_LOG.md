# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: Sebastián Ortiz
**Fecha**: 2026-11-17
**Modelos / Asistentes Utilizados**: Claude Sonnet 5.5 (Claude Code, una única sesión con modo plan). No se consultaron otros chatbots ni se ejecutaron chats independientes en paralelo; donde la guía sugiere "Nuevo chat" lo dejo indicado como limitación en cada sección.

---

## 1. De Prompts Pobres a Técnicas Clásicas de *Prompt Engineering* (Reto 1: `src/triage_rules.py`)

### 1.1 Diagnóstico de un Prompt Pobre y Ambiguo
> *"El archivo `triage_rules.py` funciona mal con algunos tickets del JSON. Agrégale el equipo recomendado y una clave para duplicados, y no pongas P0 cuando no sea urgente."*

1. **Ambigüedad de valores válidos**: no enumera los equipos (`Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`) ni el formato de la clave; el modelo inventaría nombres como "backend" o "dba-team", y una clave libre impide comparar duplicados.
2. **Restricción negativa difusa**: "no pongas P0 cuando no sea urgente" define el criterio con la misma palabra ("urgente") que causó el bug (el motor lo trata como palabra suelta). No dice qué es P0, y una instrucción negativa no dice qué hacer en su lugar. Mejor: "P0 = caída total o fuga de datos con impacto en múltiples clientes".
3. **Sin contexto ni justificación de dominio**: no explica por qué INC-1002 (cuenta individual) o INC-1009 (exportación lenta que termina) no son críticos, ni por qué INC-1007 (fuga multi-tenant) sí lo es. Sin el "porqué" el modelo no generaliza.
4. **Falta de ejemplos canónicos**: no muestra ningún par de duplicados ni la salida esperada (Few-Shot).
5. **Referencia vaga a los datos**: "algunos tickets" sin IDs ni criterio de éxito verificable (¿cuántos de 10 deben quedar bien?).
6. **Sin contexto de código**: no incluye `TriageResult` ni la firma de `classify_incident_report`, por lo que el modelo no sabe qué campos añadir ni dónde.

### 1.2 Uso de *Self-Consistency*, *Chain-of-Thought* y *Few-Shot Prompting*
- **Chain-of-Thought / Self-Consistency (qué hice realmente)**: razoné en una sola sesión, caso por caso, sobre alcance, riesgo y agrupación (`<analysis>` implícito) para los casos ambiguos. No ejecuté múltiples consultas independientes en chats nuevos, así que no hay votación real entre ejecuciones; lo sustituí por una verificación determinista (asserts sobre los 10 casos) que es más fuerte que el consenso. Conclusiones del análisis:
  - **INC-1002**: alcance de un solo usuario y con flujo de desbloqueo → P2 (no P0 pese a "hoy").
  - **INC-1009**: la exportación termina con éxito; "hoy" es contexto del usuario, no impacto → P2.
  - **INC-1007**: acceso a facturas de otra organización cambiando `company_id` → P0, Security-IAM, aunque no diga "urgente".
  - **Duplicados**: 1001/1006 = mismo síntoma (HTTP 502 en pagos con tarjeta) → `payments-gateway:http-502`; 1003/1008 = lentitud sin error con >10,000 registros → `reporting-api:slow-large-dataset`. INC-1009 es lentitud, pero de otra causa (exportación) → clave distinta `slow-export`, para no fusionar problemas diferentes.
- **Prompt mejorado** (estructurado; el bloque `<lsp_context>` real se obtiene con `uv run python -m src.context_audit --symbol classify_incident_report` y se pega en `<context>`):

```xml
<role>
Eres un ingeniero SRE senior que hace triaje de incidentes para IncidentOps.
</role>

<context>
<!-- pegar aquí el <lsp_context> de classify_incident_report (794-1069 tokens) -->
</context>

<domain_rules>
Severidad (el criterio es el IMPACTO, nunca palabras sueltas como "hoy" o "urgente"):
- P0: caída total de un flujo crítico o fuga de datos entre clientes. Por qué: pérdida de ingresos o riesgo legal inmediato para muchos usuarios.
- P1: degradación grave con riesgo de caída (p. ej. BD con 94% de conexiones y timeouts). Por qué: el servicio aún responde pero puede caer pronto.
- P2: un solo usuario afectado, o lentitud sin errores. Por qué: hay workaround y el impacto es acotado.
- P3: mejoras cosméticas o mantenimiento programado con margen. Por qué: sin impacto operativo.
Equipos válidos (usa exactamente uno): Backend-Core (lógica de negocio y pagos), Platform-SRE (infra, certificados), Data-DBA (base de datos y rendimiento de consultas), Security-IAM (identidad y seguridad).
duplicate_group_key = "<component>:<symptom_category>" en minúsculas con guiones; dos reportes con la misma clave son el mismo problema subyacente.
</domain_rules>

<examples>
<example>
Reporte: "Error 502 al pagar con tarjeta en todos los comercios"
Salida: severity=P0, component=payments-gateway, recommended_team=Backend-Core, duplicate_group_key=payments-gateway:http-502
</example>
<example>
Reporte A: "El dashboard tarda 4.5 s con más de 10,000 órdenes" / Reporte B: "El listado tarda más de 3 s con más de 10,000 registros"
Salida (ambos): severity=P2, component=reporting-api, recommended_team=Data-DBA, duplicate_group_key=reporting-api:slow-large-dataset  (duplicados)
</example>
<example>
Reporte: "Mi cuenta está bloqueada, necesito entrar hoy"
Salida: severity=P2, component=auth-identity, recommended_team=Security-IAM, duplicate_group_key=auth-identity:account-locked  ("hoy" NO eleva la severidad)
</example>
</examples>

<task>
Primero razona dentro de <analysis> sobre alcance, riesgo y duplicados de cada incidente.
Luego refactoriza src/triage_rules.py y src/models.py: añade recommended_team y duplicate_group_key a TriageResult, reemplaza los if/elif por una tabla ordenada de reglas, y haz que `uv run python -m src.triage_rules` clasifique correctamente los 10 incidentes de data/sample_incidents.json.
</task>
```

**Resultado verificado** (`uv run python -m src.triage_rules`): 10/10 correctos, claves iguales en los pares 1001/1006 y 1003/1008, sin duplicados espurios. Antes: INC-1002 e INC-1009 salían P0 e INC-1007 P3.

---

## 2. Flujo Explorar → Destilar → Ejecutar en Contexto Limpio (Reto 2: SLA en horario hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Objetivo explorado**: cálculo de SLA en horario hábil (P2/P3, L–V 08:00–18:00) vs. 24/7 (P0/P1) y escalamiento al 75%.
- **Síntesis de exploración**: partí del `<lsp_context>` de `evaluate_sla_status` y del plan sin escribir código. Hipótesis inicial: restar tiempo calendario y descontar noches/fines de semana (descartada: frágil). Casos borde descubiertos: viernes 18:30 → lunes 08:30 (30 min, el reloj arranca en la apertura), creación en sábado (0 min hasta el lunes), cruce de varios fines de semana, mismo día dentro/fuera de ventana, y el defecto de que `requires_escalation` se apagaba tras vencer el SLA (`not is_breached`). Se compararon: iteración día a día (elegida), fórmula cerrada (descartada: off-by-one), librería externa (descartada: dependencia pesada).
- **Resumen destilado (≤10 líneas)**, que es lo que llevé a la fase de ejecución:
  > 1. P0/P1 → minutos calendario; P2/P3 → solo L–V 08:00–18:00 (máx. 600/día).
  > 2. Algoritmo: recorrer los días entre creación y fin; en días hábiles sumar la intersección con la ventana. O(D), solo stdlib.
  > 3. Descartado: fórmula cerrada por semanas (frágil), `numpy.busday_count` / librerías (dependencia, no cuenta minutos).
  > 4. Creado fuera de ventana o en fin de semana aporta 0 min hasta la siguiente apertura.
  > 5. `requires_escalation = no resuelto AND elapsed >= int(allowed × 0.75)`; NO excluye vencidos.
  > 6. `is_breached = elapsed > allowed` sin cambios; resuelto nunca escala.
  > 7. Sin festivos ni zonas horarias (datetimes naive); documentarlo como trade-off.
  > 8. Mantener firma de `evaluate_sla_status` y `SLAEvaluation`.
  > 9. Verificar ≥5 casos con minutos exactos mediante asserts.
  > 10. Documentar en ADR-002 con diagrama Mermaid.
- **Limitación honesta**: la exploración y la ejecución ocurrieron en la misma sesión de Claude Code, no en dos chats separados. La separación se aplicó por orden de trabajo (ADR escrito y aprobado antes que el código, con el ADR como fuente de verdad), sin la ventaja de ventana de contexto limpia.

### 2.2 Ejecución con Contexto Curado (*Context Engineering*)
Prompt estructurado equivalente al usado para la fase de ejecución (el ADR y el código resultantes están en `docs/adr/002-calculo-sla-horario-habil.md` y `src/sla_calculator.py`):

```xml
<context>
<!-- <lsp_context> de evaluate_sla_status (≈1154 tokens) + contenido de docs/adr/000-template.md -->
</context>

<decision_summary>
<!-- el resumen destilado de 10 líneas de la sección 2.1 -->
</decision_summary>

<constraints>
- Solo librería estándar; determinista; O(D) en días.
- No cambiar la firma de evaluate_sla_status ni los campos de SLAEvaluation.
- ADR con Mermaid válido (flowchart TD y/o stateDiagram-v2).
</constraints>

<task>
1) Redacta docs/adr/002-calculo-sla-horario-habil.md siguiendo el template.
2) Refactoriza src/sla_calculator.py según el ADR y deja en __main__ al menos 5 casos borde con minutos esperados exactos (asserts).
</task>
```

**Resultado verificado** (`uv run python -m src.sla_calculator`): 9/9 casos exactos, p. ej. viernes 17:00 → lunes 09:00 en P2 = 120 min (antes 3840); P0 en el mismo intervalo sigue 3840; P2 con 540 min (vencido) mantiene `requires_escalation=True`. `src.incident_repository` sigue funcionando.

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
No ejecuté la misma tarea en dos modelos distintos, por lo que lo siguiente es análisis razonado, no una medición:
1. **Modelo rápido/estándar**: suficiente para tareas acotadas con especificación clara: aplicar la tabla de reglas de triaje, escribir el ADR desde un resumen ya acordado, volcar el código del ADR. Riesgo: tiende a omitir casos borde si el prompt es de una línea.
2. **Modelo de razonamiento extendido**: aporta valor en la exploración de casos borde del SLA (cruces de fin de semana, interacción entre `is_breached` y escalamiento) y en decidir si INC-1009 es duplicado de INC-1003/1008.
- **Indispensable el razonamiento**: diseño del Reto 2 (bordes del calendario). **Bastó el rápido**: Reto 1 una vez fijadas las reglas de dominio. En ambos, la verificación determinista (asserts) pesó más que el tipo de modelo.

### 3.2 Matriz de Decisión Arquitectónica

| Escenario / Requerimiento | Paradigma Elegido | Justificación Técnica (Determinismo, Costo, Latencia, Riesgo de Alucinación) |
| :--- | :--- | :--- |
| 1. Contabilizar minutos hábiles y verificar el umbral del 75% del SLA | Código Determinista | Regla exacta y auditable; resultado reproducible, costo y latencia casi nulos; un LLM puede alucinar aritmética y no es contractualmente defendible. |
| 2. Explorar casos borde y redactar un ADR antes de modificar consultas SQL | Asistente GenAI en Chat | Tarea creativa y exploratoria con humano en el circuito; el riesgo de alucinación se mitiga revisando y verificando con pruebas. |
| 3. Detectar anomalías numéricas en millones de métricas de CPU/RAM por minuto | ML Clásico | Series numéricas de alto volumen: modelos estadísticos/ML (z-score, isolation forest) son baratos, rápidos y sin alucinaciones; un LLM sería lento y costoso. |
| 4. Clasificar reportes en lenguaje natural abierto cuando las reglas no cubren nuevos patrones | LLM en Tiempo de Ejecución (con reglas deterministas como primera capa y revisión humana de baja confianza) | Texto libre y patrones cambiantes superan las regex; se acepta costo/latencia y riesgo de error, mitigado con salida estructurada validada, `consistency_ratio` (self-consistency) y fallback a las reglas. |

---

## 4. Economía de Tokens y Curaduría de Contexto con `tiktoken` (LSP vs. `grep`/`read` vs. `glob`/`read`)

### 4.1 Medición Empírica en *IncidentOps*
Medido con `tiktoken o200k_base` sobre el proyecto **original, antes de modificar** (8 archivos), que es el contexto que se habría pegado en los prompts de los Pasos 1 y 2.

**Símbolo `classify_incident_report` (Paso 1):**

| Estrategia de Recolección de Contexto | Alcance | Caracteres | Tokens | % de Reducción vs. Fuerza Bruta |
| :--- | :--- | :---: | :---: | :---: |
| **1. Fuerza Bruta (`glob` + `read` todo)** | 8 archivos | 32,718 | 8,219 | 0% (línea base) |
| **2. Búsqueda Textual (`grep` + `read` `.py`)** | 2 archivos `.py` | 5,522 | 1,412 | 82.8% |
| **3. Semántica vía LSP** | Definición + tipos + referencias | 3,987 | 1,069 | 87.0% |

**Símbolo `evaluate_sla_status` (Paso 2):**

| Estrategia de Recolección de Contexto | Alcance | Caracteres | Tokens | % de Reducción vs. Fuerza Bruta |
| :--- | :--- | :---: | :---: | :---: |
| **1. Fuerza Bruta (`glob` + `read` todo)** | 8 archivos | 32,718 | 8,219 | 0% (línea base) |
| **2. Búsqueda Textual (`grep` + `read` `.py`)** | 4 archivos `.py` | 24,015 | 5,821 | 29.2% |
| **3. Semántica vía LSP** | Definición + tipos + referencias | 4,412 | 1,133 | 86.2% |

**Ahorro en los prompts de los Pasos 1 y 2:** pegando solo `<lsp_context>` se usaron 1,069 + 1,133 = 2,202 tokens en lugar de 16,438 (fuerza bruta): **14,236 tokens ahorrados (86.6%)**, y 2,202 frente a 7,233 con grep+read (69.6% menos). El mayor beneficio de LSP aparece en `evaluate_sla_status`, porque `grep` arrastra `incident_repository.py` completo (casi 5,000 tokens de ruido para este reto). Además, menos ruido reduce el riesgo de *context rot*.

Nota: tras la refactorización (más código y archivos nuevos: ADR, bitácora) las mismas mediciones dan 11,359 / 2,231 / 794 tokens (triage) y 11,359 / 6,662 / 1,154 (SLA), por lo que el ahorro relativo del LSP sube a 93.0% y 89.8%: la fuerza bruta crece con el proyecto, el LSP casi no.

### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Medido para los 10 incidentes con `o200k_base`:

| Formato | Caracteres | Tokens | vs. JSON indentado |
| :--- | :---: | :---: | :---: |
| JSON indentado (`indent=2`) | 2,942 | 878 | 0% |
| JSON compacto | 2,641 | 728 | −17.1% |
| YAML | 2,579 | 755 | −14.0% |
| CSV delimitado por `\|` | 2,171 | 617 | −29.7% |

**Elección**: para datos tabulares homogéneos (incidentes, logs) usaría **CSV**: 29.7% menos tokens que JSON indentado y buena legibilidad para el modelo. Para estructuras anidadas o heterogéneas, JSON compacto (no el indentado). Los espacios de indentación y las llaves repetidas son costo sin información.
