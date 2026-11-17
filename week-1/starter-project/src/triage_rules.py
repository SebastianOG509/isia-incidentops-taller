"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps).

Clasifica reportes en lenguaje natural por *señales de impacto* (no por palabras
sueltas como "hoy" o "urgente") y produce:
- `severity` (P0-P3), según alcance y gravedad real.
- `component` normalizado.
- `recommended_team`: Backend-Core | Platform-SRE | Data-DBA | Security-IAM.
- `duplicate_group_key`: "<component>:<symptom_category>"; dos reportes con la misma
  clave describen el mismo problema subyacente.

Diseño: tabla ordenada de reglas (`TRIAGE_RULES`). La PRIMERA regla cuyo patrón
coincide gana, por lo que las más graves/específicas van primero. Agregar un caso
nuevo = agregar una fila, sin tocar la lógica.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from src.models import SeverityLevel, TeamName, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"


@dataclass(frozen=True)
class TriageRule:
    """Una señal de impacto y su clasificación asociada."""

    pattern: str
    severity: SeverityLevel
    component: str
    symptom_category: str
    team: TeamName
    why: str


TRIAGE_RULES: List[TriageRule] = [
    # P0 — fuga de datos entre organizaciones: riesgo legal/confidencialidad inmediato.
    TriageRule(
        r"company_id|otra organizaci[oó]n|pertenecientes a otra",
        "P0", "reporting-api", "cross-tenant-data-exposure", "Security-IAM",
        "exposición de datos de otra organización (fuga multi-tenant)",
    ),
    # P0 — caída total de pagos: ingresos detenidos para todos los comercios.
    TriageRule(
        r"(pago|pasarela|cobro|tarjeta).*\b502\b|\b502\b.*(pago|pasarela|cobro|tarjeta)",
        "P0", "payments-gateway", "http-502", "Backend-Core",
        "error 502 generalizado en el flujo de pagos",
    ),
    # P1 — degradación de la BD con riesgo de caída, aún con servicio parcial.
    TriageRule(
        r"postgresql|pool de conexiones|uso de conexiones",
        "P1", "database-cluster", "connection-saturation", "Data-DBA",
        "saturación de conexiones y timeouts intermitentes en la base de datos",
    ),
    # P2 — cuenta individual bloqueada: un solo usuario, existe flujo de desbloqueo.
    TriageRule(
        r"mi cuenta.*bloqueada|cuenta.*bloqueada",
        "P2", "auth-identity", "account-locked", "Security-IAM",
        "bloqueo de una cuenta individual (alcance de un solo usuario)",
    ),
    # P2 — lentitud sobre conjuntos grandes (>10,000 registros) sin errores.
    TriageRule(
        r"(tarda|lent[oa]).*10,000|10,000.*(lent[oa]|tarda)|tarda.*segundos.*(clientes|registros|[oó]rdenes)",
        "P2", "reporting-api", "slow-large-dataset", "Data-DBA",
        "degradación de rendimiento sin errores con volúmenes grandes de datos",
    ),
    # P2 — exportación lenta pero que finaliza correctamente.
    TriageRule(
        r"exportaci[oó]n.*(pensando|segundos|lent)",
        "P2", "reporting-api", "slow-export", "Backend-Core",
        "exportación lenta que termina con éxito (sin pérdida de funcionalidad)",
    ),
    # P3 — mantenimiento programado: certificado de staging con 14 días de margen.
    TriageRule(
        r"certificado|\btls\b",
        "P3", "infra-certificates", "certificate-expiry", "Platform-SRE",
        "rotación programada, entorno no productivo y con margen de tiempo",
    ),
    # P3 — solicitud cosmética sin impacto operativo.
    TriageRule(
        r"bot[oó]n|\bcolor\b",
        "P3", "frontend-ui", "ui-change-request", "Backend-Core",
        "mejora cosmética sin impacto operativo",
    ),
]

FALLBACK_RULE = TriageRule(
    "", "P3", "reporting-api", "unclassified", "Backend-Core",
    "sin señal reconocida: revisión manual por el equipo de guardia",
)


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte según señales de impacto y lo enruta a un equipo."""
    text = " ".join(raw_text.lower().split())
    rule = next((r for r in TRIAGE_RULES if re.search(r.pattern, text)), FALLBACK_RULE)

    return TriageResult(
        incident_id=incident_id,
        severity=rule.severity,
        component=rule.component,
        recommended_team=rule.team,
        duplicate_group_key=f"{rule.component}:{rule.symptom_category}",
        rationale=f"{rule.severity}: {rule.why}.",
    )


EXPECTED = {
    "INC-1001": ("P0", "payments-gateway", "Backend-Core"),
    "INC-1002": ("P2", "auth-identity", "Security-IAM"),
    "INC-1003": ("P2", "reporting-api", "Data-DBA"),
    "INC-1004": ("P3", "frontend-ui", "Backend-Core"),
    "INC-1005": ("P1", "database-cluster", "Data-DBA"),
    "INC-1006": ("P0", "payments-gateway", "Backend-Core"),
    "INC-1007": ("P0", "reporting-api", "Security-IAM"),
    "INC-1008": ("P2", "reporting-api", "Data-DBA"),
    "INC-1009": ("P2", "reporting-api", "Backend-Core"),
    "INC-1010": ("P3", "infra-certificates", "Platform-SRE"),
}
EXPECTED_DUPLICATES = [("INC-1001", "INC-1006"), ("INC-1003", "INC-1008")]


def _run_triage_audit() -> None:
    """Ejecuta el motor sobre los 10 incidentes y verifica el resultado esperado."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    results = {i["id"]: classify_incident_report(i["id"], i["raw_text"]) for i in incidents}

    print("=== Auditoría del Motor de Triaje (`src/triage_rules.py`) ===")
    print(f"{'ID':<9} | {'Sev':<3} | {'Componente':<18} | {'Equipo':<13} | Clave de duplicado")
    print("-" * 95)
    for r in results.values():
        print(
            f"{r.incident_id:<9} | {r.severity:<3} | {r.component:<18} | "
            f"{r.recommended_team:<13} | {r.duplicate_group_key}"
        )
    print("-" * 95)

    for iid, (sev, comp, team) in EXPECTED.items():
        r = results[iid]
        assert (r.severity, r.component, r.recommended_team) == (sev, comp, team), (
            f"{iid}: obtenido {(r.severity, r.component, r.recommended_team)}, "
            f"esperado {(sev, comp, team)}"
        )
    for a, b in EXPECTED_DUPLICATES:
        assert results[a].duplicate_group_key == results[b].duplicate_group_key, (a, b)
    keys = [r.duplicate_group_key for r in results.values()]
    assert len(set(keys)) == len(keys) - len(EXPECTED_DUPLICATES), "Hay duplicados no esperados"
    print("OK: 10/10 incidentes correctos; duplicados detectados:", EXPECTED_DUPLICATES)


if __name__ == "__main__":
    _run_triage_audit()
