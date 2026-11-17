# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: Sebastián Ortiz
**Fecha**: 2026-11-17
**Modelos / Asistentes Utilizados**: Claude Sonnet 5.5 (sesión de orquestación en Claude Code: plan, aplicación de archivos, verificación en terminal y mediciones) y Claude Opus 5.5 en 7 consultas independientes con contexto limpio, ejecutadas como subagentes de Claude Code:
- 3 de Self-Consistency para el triaje;
- 1 de generación del código del Reto 1;
- 1 "Chat 1" de exploración del SLA;
- 1 "Chat 2" para el ADR-002;
- 1 de generación de `sla_calculator.py` a partir del ADR.

Cada subagente arranca con la ventana de contexto vacía y solo ve el prompt y los archivos de contexto que se le indican, que es el equivalente a "Nuevo chat". No se usaron otros chatbots.

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
- **Cómo se hizo**: lancé **3 consultas independientes** (Claude Opus 5.5, contexto limpio cada una, sin ver el código del motor ni las otras respuestas) con el mismo prompt: leer `data/sample_incidents.json`, escribir primero una justificación por ticket (alcance y riesgo, con foco en INC-1001/1006, 1002, 1003/1008, 1007 y 1009, que es el razonamiento previo de Chain-of-Thought) y después la tabla de severidad, componente, equipo y clave de duplicado.
  - Un primer intento con Sonnet 5.5, que pedía razonar "paso a paso dentro de `<analysis>`", fue bloqueado por los filtros de seguridad de la API en las 3 ejecuciones (falso positivo). Reformulé la petición como "Justificación por ticket" y lo repetí con Opus 5.5.
- **Resultado de Self-Consistency (votación 3 de 3)**:

| Ticket | Consulta 1 | Consulta 2 | Consulta 3 | Consenso | Motor final |
| :--- | :---: | :---: | :---: | :---: | :---: |
| INC-1001 | P0 Backend-Core | P0 Backend-Core | P0 Backend-Core | 3/3 | P0 Backend-Core |
| INC-1002 | P2 Security-IAM | P2 Security-IAM | P2 Security-IAM | 3/3 | P2 Security-IAM |
| INC-1003 | P2 Data-DBA | P2 Data-DBA | P2 Data-DBA | 3/3 | P2 Data-DBA |
| INC-1004 | P3 Backend-Core | P3 Backend-Core | P3 Backend-Core | 3/3 | P3 Backend-Core |
| INC-1005 | P1 Data-DBA | P1 Data-DBA | P1 Data-DBA | 3/3 | P1 Data-DBA |
| INC-1006 | P0 Backend-Core | P0 Backend-Core | P0 Backend-Core | 3/3 | P0 Backend-Core |
| INC-1007 | P0 Security-IAM | P0 Security-IAM | P0 Security-IAM | 3/3 | P0 Security-IAM |
| INC-1008 | P2 Data-DBA | P2 Data-DBA | P2 Data-DBA | 3/3 | P2 Data-DBA |
| INC-1009 | P2 Backend-Core | P2 Backend-Core | P2 Backend-Core | 3/3 | P2 Backend-Core |
| INC-1010 | P3 Platform-SRE | P3 Platform-SRE | P3 Platform-SRE | 3/3 | P3 Platform-SRE |

  - **Duplicados**: las 3 consultas identificaron exactamente los pares INC-1001↔1006 (502 en pagos con tarjeta) e INC-1003↔1008 (lentitud con más de 10,000 registros). Dos de ellas explicaron por qué INC-1009 **no** es duplicado: otro flujo (exportación a Excel) y otro orden de magnitud (unos 20 s frente a 3 a 4.5 s).
  - **Dónde hubo variación**: solo en los nombres de componente y en el texto de la clave (`payment-gateway:availability-http502` frente a `payment-gateway:outage-http502`; `auth`, `auth-login`). Era esperable porque el prompt no fijaba un vocabulario de componentes. Conclusión de ingeniería: el motor debe **normalizar** los componentes a un catálogo cerrado (`payments-gateway`, `auth-identity`, `reporting-api`, etc.), porque si no la clave de duplicado deja de ser comparable entre ejecuciones.
  - **Justificaciones compartidas** por las 3 consultas, que pasaron a ser las reglas de dominio del motor:
    - **INC-1002**: es un solo usuario y el bloqueo es el control de acceso funcionando; "hoy mismo" no amplía el alcance → P2.
    - **INC-1009**: la exportación termina bien; el miedo a que "falle más tarde" es especulativo → P2.
    - **INC-1007**: es una exposición de datos entre clientes por manipular `company_id` (IDOR) → P0 Security-IAM, aunque el tono del ticket sea tranquilo.
  - **Asignaciones de equipo marcadas como discutibles por las propias consultas**: INC-1001/1006 (Platform-SRE si el 502 viene del balanceador), INC-1003/1008 (Backend-Core si la causa es código de aplicación) e INC-1004 (no hay equipo de frontend). Las mantuve como el consenso.
- **Del consenso al código (paso 1.3 del taller, "Nuevo chat")**: con el consenso ya fijado abrí una **consulta nueva y limpia** (Claude Opus 5.5). Solo recibió el `<lsp_context>` de `classify_incident_report` (1,069 tokens), los 10 incidentes y el prompt estructurado de abajo. Devolvió `models.py` y `triage_rules.py` completos, que copié al proyecto local y verifiqué en terminal.
- **Prompt estructurado utilizado** (texto real enviado; el `<lsp_context>` se adjuntó como archivo de contexto):

```xml
<role>
Eres un ingeniero de software senior de IncidentOps, experto en triaje de incidentes y en Python limpio.
</role>

<context>
<!-- bloque <lsp_context> de classify_incident_report generado con
     uv run python -m src.context_audit --symbol classify_incident_report (1,069 tokens) -->
El módulo define PROJECT_ROOT, SAMPLE_DATA_PATH y _run_triage_audit() en __main__.
Imports con prefijo `src.`; Python >= 3.10; solo librería estándar.
</context>

<domain_rules>
Severidad según IMPACTO, nunca por palabras sueltas como "hoy" o "urgente":
- P0: caída total de un flujo crítico o exposición de datos de un cliente a otro. Por qué: pérdida de ingresos o riesgo legal inmediato.
- P1: degradación grave con riesgo de caída (p. ej. BD con 94% de conexiones y timeouts). Por qué: aún responde pero puede caer.
- P2: un solo usuario afectado, o lentitud sin errores. Por qué: impacto acotado y con alternativa.
- P3: cambio cosmético o mantenimiento programado con margen. Por qué: sin impacto operativo.
Equipos válidos (exactamente uno): Backend-Core (lógica de negocio, pagos, exportaciones, UI), Platform-SRE (infraestructura, certificados), Data-DBA (base de datos y rendimiento de consultas sobre volúmenes grandes), Security-IAM (identidad, control de acceso, exposición de datos).
Componentes: catálogo cerrado y normalizado: payments-gateway, auth-identity, database-cluster, reporting-api, frontend-ui, infra-certificates.
duplicate_group_key = "<component>:<symptom_category>" en minúsculas con guiones; mismo problema subyacente => misma clave.
Resultado del análisis previo de Self-Consistency (3 consultas, consenso 3/3): 1001 P0 Backend-Core; 1002 P2 Security-IAM; 1003 P2 Data-DBA; 1004 P3 Backend-Core; 1005 P1 Data-DBA; 1006 P0 Backend-Core; 1007 P0 Security-IAM; 1008 P2 Data-DBA; 1009 P2 Backend-Core; 1010 P3 Platform-SRE. Duplicados: 1001↔1006 y 1003↔1008; 1009 NO es duplicado (otro flujo).
</domain_rules>

<examples>
<example>Reporte: "Error 502 al pagar con tarjeta en todos los comercios" → P0, payments-gateway, Backend-Core, payments-gateway:http-502</example>
<example>Reportes A "El dashboard tarda 4.5 s con más de 10,000 órdenes" y B "El listado tarda más de 3 s con más de 10,000 registros" → ambos P2, reporting-api, Data-DBA, reporting-api:slow-large-dataset (duplicados)</example>
<example>Reporte: "Mi cuenta está bloqueada, necesito entrar hoy" → P2, auth-identity, Security-IAM, auth-identity:account-locked ("hoy" no eleva la severidad)</example>
</examples>

<task>
Refactoriza src/models.py y src/triage_rules.py:
1. models.py: añade TeamName (Literal de los 4 equipos) y a TriageResult los campos recommended_team y duplicate_group_key.
2. triage_rules.py: reemplaza los if/elif por una estructura de reglas legible y extensible basada en señales de impacto; mantén la firma de classify_incident_report.
3. _run_triage_audit: imprime id, severidad, componente, equipo y clave, y verifica con assert los 10 resultados y los pares de duplicados.
Devuelve los DOS archivos completos.
</task>
```

- **Revisión humana antes de copiar**: el modelo avisó que no tenía el `models.py` original completo y lo **reconstruyó**. Al revisarlo encontré dos alucinaciones: `IncidentStatus` sin el valor `ESCALATION_REQUIRED`, y las dataclasses sin `frozen=True`. Por eso **no copié** su `models.py` entero: sobre el original añadí solo `TeamName` y los dos campos nuevos. `triage_rules.py` se copió sin cambios. Diseño generado:
  - reglas declarativas `TriageRule` con grupos de señales (todas las condiciones con AND entre grupos y OR dentro de cada grupo);
  - normalización de tildes;
  - orden por severidad;
  - `FALLBACK_RULE` con `consistency_ratio=0.0` para lo no reconocido.
- **Diferencia con el consenso**: para INC-1007 el modelo eligió el componente `auth-identity` ("fallo de control de acceso"); las consultas de Self-Consistency usaron un componente de reportes. Severidad y equipo coinciden (P0, Security-IAM), así que lo acepté.
- **Resultado verificado** (`uv run python -m src.triage_rules`): **10/10** en severidad y equipo, duplicados exactamente {1001, 1006} y {1003, 1008}, sin grupos espurios. Antes: INC-1002 e INC-1009 salían P0 e INC-1007 P3.

---

## 2. Flujo Explorar → Destilar → Ejecutar en Contexto Limpio (Reto 2: SLA en horario hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Objetivo explorado**: cálculo de SLA en horario hábil (P2/P3, L–V 08:00–18:00) vs. 24/7 (P0/P1) y escalamiento al 75%.
- **Chat 1 (Claude Opus 5.5, contexto limpio, sobre el código ORIGINAL)**: le pasé solo el `<lsp_context>` de `evaluate_sla_status` (1,133 tokens) y el requisito, con la instrucción explícita de **no escribir código todavía**. Le pedí analizar:
  - el caso viernes 18:30 → lunes 08:30;
  - la creación en sábado y el cruce de varios fines de semana;
  - el comportamiento de `requires_escalation` tras vencer el SLA;
  - 2-3 alternativas O(D).

  El modelo confirmó que solo leyó ese archivo.
- **Qué descubrió la exploración**:
  - **Viernes 18:30 → lunes 08:30**: correcto = **30 min**. La versión actual da **3720**, con `is_breached=True` y `requires_escalation=False`: un falso incumplimiento y además sin escalamiento.
  - **Casos que propuso por su cuenta**: sábado → domingo = 0; sábado 10:00 → lunes 10:00 = 120; miércoles 17:00 → jueves 09:00 = 120 (cruza la noche); lunes 07:00 → 07:59 = 0; P3 viernes 17:00 → lunes 16 09:00 = 3120 (cruza varios fines de semana); viernes 14:00 → lunes 10:00 = 360 (alcanza exactamente el 75% de P2).
  - **Escalamiento**: `not is_breached` apaga el escalamiento al vencer; como incumplir implica haber pasado el 75%, la regla correcta es "abierto AND elapsed ≥ umbral".
  - **Preguntas abiertas que el modelo dejó explícitas**: ¿el incumplimiento empieza con `>` o con `>=`?; ¿qué indica que un incidente está resuelto, `status` o `resolved_at`?; ¿`remaining_minutes` puede ser negativo?; ¿hay zonas horarias o festivos?
  - **Alternativas**: minuto a minuto (O(D×1440), descartada), recorrido día a día con intersección de ventana (O(D), elegida), fórmula cerrada O(1) (frágil, descartada) y pandas/numpy (pesadas, y `busday_count` cuenta días, no minutos; descartadas).
- **Verificación humana de la salida del modelo**: comprobé a mano todos los minutos hábiles esperados y son correctos. Encontré **un error** en la columna "versión actual (24/7)": para viernes 14:00 → lunes 10:00 el modelo escribió 3960, pero el valor real es **4080** (68 h). Ese número no pasó al resumen.
- **Decisiones humanas** sobre las preguntas abiertas (línea 5 del resumen): conservé el comportamiento actual donde el taller no pide cambiarlo:
  - `is_breached` sigue con `>`;
  - "abierto" significa `status != RESOLVED` **y** `resolved_at is None`;
  - `remaining_minutes` puede ser negativo;
  - fechas naive y sin festivos.
- **Resumen destilado (compactación, 10 líneas)** producido por el Chat 1, con la línea 5 completada con esas decisiones, y llevado tal cual al Chat 2:
  > 1. Requisito: P0/P1 cuentan 24/7; P2/P3 solo L-V 08:00-18:00 (600 min/día, fines de semana = 0).
  > 2. Bug actual: P2 vie 18:30 → lun 08:30 devuelve 3720 min (incumplido); lo correcto es 30.
  > 3. Casos de prueba: sáb→dom = 0; sáb 10:00→lun 10:00 = 120; P3 vie 17:00→lun+10d 09:00 = 3120; vie 14:00→lun 10:00 = 360 (alcanza 75% en P2).
  > 4. Bug de escalamiento: `not is_breached` apaga el escalamiento tras vencer. Nueva regla: abierto AND elapsed >= int(max*0.75), que incluye los incumplidos.
  > 5. Acordado: is_breached sigue con `>`; abierto = status != "RESOLVED" y resolved_at is None; remaining_minutes puede ser negativo; datetimes naive en una zona; sin festivos.
  > 6. Descartado: iteración minuto a minuto (O(D×1440)).
  > 7. Descartado: fórmula cerrada O(1) (frágil, poco legible).
  > 8. Descartado: pandas/numpy/businesstimedelta (dependencias pesadas; busday_count cuenta días, no minutos).
  > 9. Decisión: función pura `_business_minutes_between(start, end)`, recorre día a día intersectando con la ventana, suma segundos, convierte a minutos una sola vez; O(D), solo stdlib.
  > 10. evaluate_sla_status usa 24/7 si operates_24x7, si no la función hábil; probar casos 2-3 y los bordes 08:00/18:00.

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering*)
**Chat 2: ADR.** Una consulta nueva (Claude Opus 5.5) con ventana vacía, equivalente a `/clear`. Solo recibió:
- el `<lsp_context>` de `evaluate_sla_status`;
- la plantilla `docs/adr/000-template.md`;
- el resumen destilado.

No vio ni las alternativas exploradas en detalle ni la conversación del Chat 1. Prompt:

```xml
<context>
<!-- bloque <lsp_context> de evaluate_sla_status (1,133 tokens) + docs/adr/000-template.md -->
</context>

<decision_summary>
<!-- las 10 líneas del resumen destilado de la sección 2.1 -->
</decision_summary>

<constraints>
- Sigue la estructura de 000-template.md (Contexto y Problema, Opciones Consideradas, Decisión con diagrama, Consecuencias e Impacto).
- Título: "ADR-002: Cálculo de SLA en horario hábil y escalamiento preventivo". Estado: Aceptado. Fecha: 2026-11-17. Autor: Sebastián Ortiz. Componentes: src/sla_calculator.py.
- Incluye al menos un diagrama Mermaid válido (flowchart TD o stateDiagram-v2) que explique el cálculo y la transición a escalamiento.
- No cambiar la firma pública de evaluate_sla_status ni los campos de SLAEvaluation.
- Conciso: sin repetir el código completo.
</constraints>

<task>
Redacta el ADR completo en Markdown, listo para guardarse en docs/adr/002-calculo-sla-horario-habil.md.
</task>
```

- **Resultado**: el ADR se guardó **sin cambios de contenido** en `docs/adr/002-calculo-sla-horario-habil.md`; solo quité los corchetes de plantilla en "Componentes". Incluye:
  - 4 opciones evaluadas;
  - un `flowchart TD` con el cálculo y la transición a escalamiento;
  - una tabla de verificación con 10 casos.
- **Ambigüedad que detectó el propio Chat 2**: el resumen decía "lun+10d", que puede leerse como "lunes + 10 días" (un jueves, 4920 min) o como "el lunes 10 días después del viernes" (3120 min). El Chat 2 lo hizo explícito y eligió la segunda lectura, la correcta según el Chat 1. Es un ejemplo de que la compactación puede perder precisión.

**Paso 2.3: código a partir del ADR aprobado.** Otra consulta limpia (Claude Opus 5.5) recibió:
- el ADR-002;
- el `<lsp_context>`;
- el `sla_calculator.py` original.

La tarea fue implementar exactamente la decisión del ADR y convertir su tabla de verificación en `assert`. Devolvió el archivo completo, más una lista de las ambigüedades del ADR que tuvo que resolver: las horas del caso "sáb → dom", el resultado esperado del caso "día completo" y cómo cubrir "P0/P1 cualquier rango" con dos casos. Lo copié sin cambios.

- **Resultado verificado en terminal** (`uv run python -m src.sla_calculator`): **11/11 casos OK en la primera ejecución**, entre ellos:
  - viernes 18:30 → lunes 08:30 = 30;
  - P3 en varias semanas = 3120;
  - umbral exacto del 75% (360) con escalamiento;
  - bordes de apertura y cierre = 0;
  - día completo = 600 (incumplido y escalado);
  - P0 24/7 = 3840 sin cambio;
  - resuelto medido hasta `resolved_at` y sin escalamiento.

  `uv run python -m src.incident_repository` sigue funcionando.

**Orden real y trazabilidad.** Una primera versión de esta entrega se hizo en orden incorrecto: el código se escribió antes de la exploración. Al detectarlo restauré el código original (commit `300290d`) y rehice todo en el orden del taller. El historial de git muestra la secuencia:
1. restauración;
2. Reto 1 desde el prompt estructurado;
3. ADR-002 desde el Chat 2;
4. `sla_calculator.py` desde el ADR.

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
Usé Claude Sonnet 5.5 (modelo estándar) en la sesión de orquestación: plan, aplicación de archivos, verificación y mediciones con `tiktoken`. Usé Claude Opus 5.5 (modelo más capaz) en las consultas de análisis y generación. No ejecuté la misma tarea con ambos modelos en condiciones idénticas, así que esta es una comparación cualitativa, no un benchmark.
1. **Modelo estándar (Sonnet 5.5)**: bastó para tareas mecánicas y verificables: restaurar archivos, aplicar el código, ejecutar pruebas, medir tokens y revisar a mano los números de los modelos. Sus 3 consultas de Self-Consistency, que pedían razonar "paso a paso dentro de `<analysis>`", fueron bloqueadas por los filtros de seguridad (falso positivo). La formulación del prompt también afecta la disponibilidad, no solo la calidad.
2. **Modelo más capaz (Opus 5.5)**:
   - **Exploración (Chat 1)**: propuso casos borde no pedidos (cruce nocturno entre semana, antes de la apertura, umbral exacto del 75%) y dejó explícitas 4 decisiones pendientes en lugar de suponerlas. Aun así se equivocó en un número auxiliar (3960 en lugar de 4080).
   - **ADR (Chat 2)**: detectó la ambigüedad de "lun+10d".
   - **Código del Reto 1**: alucinó partes de `models.py` que no podía ver, aunque lo advirtió.
- **Dónde fue indispensable más razonamiento**: en la exploración del Reto 2 (bordes del calendario y la interacción entre `is_breached` y el escalamiento) y en la generación del motor de reglas. **Dónde bastó el estándar**: en orquestar, aplicar y verificar. En ambos retos, lo que atrapó los errores de los modelos fue la verificación determinista (`assert`) y la revisión humana, no el tamaño del modelo.

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

Nota: tras la refactorización (más código y archivos nuevos: ADR, bitácora) las mismas mediciones dan 12,829 / 2,693 / 791 tokens (triage) y 12,829 / 6,971 / 1,169 (SLA), por lo que el ahorro relativo del LSP sube a 93.8% y 90.9%: la fuerza bruta crece con el proyecto, el LSP casi no.

### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Medido para los 10 incidentes con `o200k_base`:

| Formato | Caracteres | Tokens | vs. JSON indentado |
| :--- | :---: | :---: | :---: |
| JSON indentado (`indent=2`) | 2,942 | 878 | 0% |
| JSON compacto | 2,641 | 728 | −17.1% |
| YAML | 2,579 | 755 | −14.0% |
| CSV delimitado por `\|` | 2,171 | 617 | −29.7% |

**Elección**: para datos tabulares homogéneos (incidentes, logs) usaría **CSV**: 29.7% menos tokens que JSON indentado y buena legibilidad para el modelo. Para estructuras anidadas o heterogéneas, JSON compacto (no el indentado). Los espacios de indentación y las llaves repetidas son costo sin información.
