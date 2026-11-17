# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: Sebastián Ortiz
**Fecha**: 2026-11-17
**Modelos / Asistentes Utilizados**: Claude Sonnet 5.5 (sesión principal en Claude Code: plan, implementación y verificación) y Claude Opus 5.5 (5 consultas independientes con contexto limpio, ejecutadas como subagentes de Claude Code: 3 de Self-Consistency para el triaje, 1 "Chat 1" de exploración del SLA y 1 "Chat 2" para redactar el ADR-002). Cada subagente arranca con ventana de contexto vacía y solo ve el prompt que se le pasa, que es el equivalente a "Nuevo chat". No se usaron otros chatbots.

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
  - El motor determinista implementa el consenso y además lo verifica con `assert` sobre los 10 casos.
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
- **Chat 1 (consulta independiente, Claude Opus 5.5, contexto limpio)**: le pasé la descripción de `evaluate_sla_status` original y de `SLA_POLICY_TABLE`, con la instrucción explícita de **no escribir código** y analizar:
  - el caso viernes 18:30 → lunes 08:30;
  - la creación en sábado y el cruce de varios fines de semana;
  - el problema de `requires_escalation` cuando el SLA ya venció;
  - 2-3 alternativas O(D) sin librerías pesadas.
- **Qué descubrió la exploración**:
  - **Viernes 18:30 → lunes 08:30**: el valor correcto es **30 min**. La versión original da **3720 min**, lo que marca `is_breached=True` y, por la cláusula `not is_breached`, deja `requires_escalation=False`. Son dos errores a la vez.
  - **Otros casos de referencia**: sábado 10:00 → lunes 12:00 = 240 (la original da 3000); sábado → sábado = 0; P3 del 2-nov al 16-nov (dos fines de semana) = 540 + 4×600 + 5×600 + 60 = 6000 (la original da 20160).
  - **Detalle de diseño**: si un ticket se crea fuera de horario, el reloj arranca en la siguiente apertura. Por eso el algoritmo debe *recortar contra la ventana de cada día*, no solo saltar fines de semana.
  - **Escalamiento**: un vencido siempre supera el 75%, así que basta con `abierto AND elapsed >= floor(0.75×SLA)`. "Abierto" debe exigir `status != RESOLVED` y `resolved_at is None`.
  - **Alternativas comparadas**: minuto a minuto (O(minutos)), recorte por día (O(D), elegida), fórmula cerrada O(1) y librerías (pandas BusinessHour, `numpy.busday_count`).
  - **Recomendación**: sumar en segundos y aplicar `// 60` una sola vez al final, para no acumular truncamientos por día.
- **Limitación**: el subagente tenía acceso de lectura al repositorio y notó que `sla_calculator.py` ya estaba corregido (el código se implementó antes en la sesión principal). Analizó la versión original como se le pidió y calculó los números a mano, pero la exploración no fue totalmente "a ciegas".
- **Resumen destilado (compaction, 10 líneas) producido por el Chat 1**, copiado tal cual al Chat 2:
  > 1. Requisito: P2/P3 solo cuentan L-V 08:00-18:00 (600 min/día); P0/P1 siguen 24/7.
  > 2. Casos de referencia: vie 18:30→lun 08:30 = 30; vie 17:00→lun 09:00 = 120; sáb 10:00→lun 12:00 = 240; P3 lun 2-nov→lun 16-nov 09:00 = 6000.
  > 3. Bug original: resta 24/7 infla minutos (3720 en vez de 30) → falsos incumplimientos.
  > 4. Bug de escalamiento: `not is_breached` apaga el escalamiento justo cuando el SLA vence.
  > 5. Descartado: iteración minuto a minuto (O(minutos), no cumple O(D)).
  > 6. Descartado: fórmula cerrada O(1) (demasiados casos borde, ilegible).
  > 7. Descartado: pandas/businesstime/numpy (dependencia pesada; busday_count no da minutos).
  > 8. Decisión: recorte día a día contra ventana hábil, O(D), solo datetime, helper puro, `// 60` al final.
  > 9. Decisión: requires_escalation = abierto AND elapsed >= floor(0.75×SLA) (incluye vencidos); is_breached = elapsed > SLA.
  > 10. Fuera de alcance: feriados y zonas horarias; los casos anteriores son pruebas de regresión.

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering*)
**Chat 2**: una consulta nueva (Claude Opus 5.5) con ventana vacía. Recibió solo:
- el `<lsp_context>` de `evaluate_sla_status` (código original);
- la plantilla `000-template.md`;
- el resumen destilado del Chat 1.

Se le prohibió leer cualquier otro archivo, de modo que no vio ni las alternativas discutidas en el Chat 1 ni el código ya corregido. Prompt utilizado (resumido en los bloques largos):

```xml
<context>
Código original (extraído con LSP) de src/sla_calculator.py:
SLA_POLICY_TABLE = { P0: 60 min 24x7, P1: 240 min 24x7, P2: 480 min hábil, P3: 1440 min hábil }
SLARule / Incident / SLAEvaluation (firmas)
def evaluate_sla_status(...)  <!-- cuerpo original completo -->
Referencias: src/incident_repository.py:146 y __main__ de src/sla_calculator.py.
</context>

<decision_summary>
<!-- las 10 líneas del resumen destilado del Chat 1 (sección 2.1) -->
</decision_summary>

<constraints>
- Sigue la estructura de 000-template.md.
- Título: "ADR-002: Cálculo de SLA en horario hábil y escalamiento preventivo". Fecha 2026-11-17. Autor: Sebastián Ortiz.
- Incluye un diagrama Mermaid válido (flowchart TD o stateDiagram-v2) que explique el cálculo y la transición a escalamiento.
- No cambiar la firma pública de evaluate_sla_status ni SLAEvaluation.
</constraints>

<task>
Devuelve como respuesta el Markdown completo del ADR.
</task>
```

- **Resultado**: el Chat 2 produjo el ADR que quedó guardado en `docs/adr/002-calculo-sla-horario-habil.md`, con 4 opciones evaluadas, un `flowchart TD` y un plan de verificación.
- **Ajustes manuales al guardarlo**:
  - En la condición de escalamiento, "abierto" pasó a incluir también `resolved_at is None` (lo había señalado el Chat 1 y el Chat 2 lo omitió).
  - El nombre del helper quedó `_business_minutes_between`, como en el código.
  - La sección de verificación ahora apunta al comando real.
- **Coherencia con el código**: la decisión del ADR del Chat 2 coincide con la implementación de `src/sla_calculator.py`: recorte por día, `// 60` al final, rama según `operates_24x7` y escalamiento sin `not is_breached`.
- **Resultado verificado** (`uv run python -m src.sla_calculator`): 9/9 casos exactos, entre ellos los 4 casos de referencia del resumen destilado (30, 120, 240 y 6000). P0 en el mismo intervalo sigue en 3840, y un P2 con 540 min (vencido) mantiene `requires_escalation=True`. `src.incident_repository` sigue funcionando.
- **Orden real del trabajo**: el código se implementó en la sesión principal **antes** de ejecutar los Chats 1 y 2 independientes. Estos se usaron después para contrastar el diseño con contexto limpio, y llegaron de forma independiente a la misma decisión y a los mismos valores esperados.

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
Observación real de esta semana: Claude Sonnet 5.5 (modelo estándar) en la sesión principal y Claude Opus 5.5 (modelo más capaz) en las 5 consultas independientes. No ejecuté la misma tarea con ambos modelos en condiciones idénticas, así que esto es una comparación cualitativa, no un benchmark.
1. **Modelo estándar (Sonnet 5.5)**: bastó para la implementación con especificación clara: tabla de reglas de triaje, helper de minutos hábiles, casos de prueba y mediciones con `tiktoken`. Sus 3 consultas de Self-Consistency, que pedían razonar "paso a paso dentro de `<analysis>`", fueron bloqueadas por los filtros de seguridad (falso positivo). Esto muestra que la formulación del prompt también afecta la disponibilidad, no solo la calidad.
2. **Modelo más capaz (Opus 5.5)**: en la exploración del SLA aportó matices que no estaban en la especificación:
   - el doble efecto del bug en el caso de las 18:30 (falso incumplimiento y escalamiento apagado);
   - sumar en segundos y truncar una sola vez;
   - el análisis de `resolved_at` además del `status`.

   En triaje, las 3 ejecuciones coincidieron 10/10 en severidad y equipo, y señalaron por su cuenta las asignaciones discutibles.
- **Dónde fue indispensable más razonamiento**: en la exploración del Reto 2 (bordes del calendario y la interacción entre `is_breached` y el escalamiento). **Dónde bastó el estándar**: en implementar y verificar una vez fijadas las reglas. En ambos retos la verificación determinista (`assert`) pesó más que el tipo de modelo.

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
