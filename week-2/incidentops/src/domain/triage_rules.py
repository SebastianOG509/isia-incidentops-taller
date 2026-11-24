"""Reglas de triaje de incidentes basadas en señales de IMPACTO (no en palabras sueltas).

Cada regla declara grupos de señales: la regla aplica si TODOS los grupos se cumplen,
y un grupo se cumple si aparece AL MENOS UNO de sus términos. Las reglas se evalúan
de mayor a menor severidad, así que el impacto más crítico detectado gana.
Para extender el triaje basta con añadir una TriageRule a TRIAGE_RULES.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.domain.models import SeverityLevel, TeamName, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"

ComponentName = Literal[
    "payments-gateway",
    "auth-identity",
    "database-cluster",
    "reporting-api",
    "frontend-ui",
    "infra-certificates",
]

SignalGroup = tuple[str, ...]


def normalize_text(raw_text: str) -> str:
    """Pasa a minúsculas y elimina tildes para comparar términos de forma robusta."""
    decomposed = unicodedata.normalize("NFKD", raw_text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


@dataclass(frozen=True)
class TriageRule:
    """Regla declarativa de triaje. Los términos se escriben en minúsculas y sin tildes."""

    name: str
    severity: SeverityLevel
    component: ComponentName
    team: TeamName
    symptom_category: str
    impact_signals: tuple[SignalGroup, ...]
    rationale: str

    def matches(self, normalized_text: str) -> bool:
        return all(
            any(term in normalized_text for term in group) for group in self.impact_signals
        )

    @property
    def duplicate_group_key(self) -> str:
        return f"{self.component}:{self.symptom_category}"


# --- Vocabulario de señales reutilizable -------------------------------------------
PAYMENT_TERMS: SignalGroup = ("pago", "pagar", "cobr", "pasarela", "tarjeta")
HTTP_502_TERMS: SignalGroup = ("502", "bad gateway")
TOTAL_OUTAGE_TERMS: SignalGroup = ("todas", "todos", "ningun", "cayo", "caida")
SLOWNESS_TERMS: SignalGroup = ("tarda", "lento", "lenta", "lentitud")
LARGE_DATASET_TERMS: SignalGroup = ("10,000", "10.000", "10000", "miles de")

_RULES: tuple[TriageRule, ...] = (
    # ---------------- P0: caída total de flujo crítico / exposición de datos ---------
    TriageRule(
        name="cross-tenant-exposure",
        severity="P0",
        component="auth-identity",
        team="Security-IAM",
        symptom_category="cross-tenant-data-exposure",
        impact_signals=(
            ("otra organizacion", "otro cliente", "otra empresa", "otro tenant"),
            ("visualiz", "expon", "exposicion", "filtr"),
        ),
        rationale="Datos de un cliente visibles para otro: riesgo legal inmediato.",
    ),
    TriageRule(
        name="payments-total-outage",
        severity="P0",
        component="payments-gateway",
        team="Backend-Core",
        symptom_category="http-502",
        impact_signals=(PAYMENT_TERMS, HTTP_502_TERMS, TOTAL_OUTAGE_TERMS),
        rationale="Caída total del flujo de cobro: pérdida de ingresos inmediata.",
    ),
    # ---------------- P1: degradación grave con riesgo de caída -----------------------
    TriageRule(
        name="payments-partial-errors",
        severity="P1",
        component="payments-gateway",
        team="Backend-Core",
        symptom_category="http-502",
        impact_signals=(PAYMENT_TERMS, HTTP_502_TERMS),
        rationale="Errores 502 en pagos sin evidencia de caída total: riesgo de caída.",
    ),
    TriageRule(
        name="database-saturation",
        severity="P1",
        component="database-cluster",
        team="Data-DBA",
        symptom_category="connection-saturation",
        impact_signals=(
            ("postgresql", "base de datos", "pool de conexiones"),
            ("timeout", "saturad", "agotad"),
        ),
        rationale="BD saturada con timeouts: aún responde pero puede caer.",
    ),
    # ---------------- P2: un solo usuario o lentitud sin errores ----------------------
    TriageRule(
        name="single-account-locked",
        severity="P2",
        component="auth-identity",
        team="Security-IAM",
        symptom_category="account-locked",
        impact_signals=(("cuenta", "usuario"), ("bloquead",)),
        rationale="Un único usuario afectado; la urgencia declarada no eleva el impacto.",
    ),
    TriageRule(
        name="slow-export",
        severity="P2",
        component="reporting-api",
        team="Backend-Core",
        symptom_category="slow-export",
        impact_signals=(
            ("exportacion", "exportar"),
            SLOWNESS_TERMS + ("pensando", "segundos"),
        ),
        rationale="Exportación lenta pero completa: impacto acotado, sin errores.",
    ),
    TriageRule(
        name="slow-large-dataset",
        severity="P2",
        component="reporting-api",
        team="Data-DBA",
        symptom_category="slow-large-dataset",
        impact_signals=(SLOWNESS_TERMS, LARGE_DATASET_TERMS),
        rationale="Consultas lentas sobre volúmenes grandes, sin errores.",
    ),
    # ---------------- P3: cosmético o mantenimiento programado ------------------------
    TriageRule(
        name="cosmetic-change",
        severity="P3",
        component="frontend-ui",
        team="Backend-Core",
        symptom_category="cosmetic-change",
        impact_signals=(("color", "boton", "estilo", "diseno", "resalta"),),
        rationale="Cambio cosmético de UI sin impacto operativo.",
    ),
    TriageRule(
        name="scheduled-certificate-rotation",
        severity="P3",
        component="infra-certificates",
        team="Platform-SRE",
        symptom_category="certificate-expiry",
        impact_signals=(
            ("certificado", "tls"),
            ("vencer", "expir", "rotacion"),
            ("staging", "programad"),
        ),
        rationale="Rotación programada con margen en entorno no productivo.",
    ),
)

# Orden por severidad (P0 primero); sorted es estable y respeta el orden declarado.
TRIAGE_RULES: tuple[TriageRule, ...] = tuple(sorted(_RULES, key=lambda r: r.severity))

FALLBACK_RULE = TriageRule(
    name="unclassified",
    severity="P2",
    component="reporting-api",
    team="Backend-Core",
    symptom_category="unclassified",
    impact_signals=(),
    rationale="Sin señales de impacto reconocidas: requiere revisión manual.",
)


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte aplicando la primera regla de impacto que coincide."""
    text = normalize_text(raw_text)
    rule = next((r for r in TRIAGE_RULES if r.matches(text)), None)
    matched = rule is not None
    rule = rule or FALLBACK_RULE

    return TriageResult(
        incident_id=incident_id,
        severity=rule.severity,
        component=rule.component,
        recommended_team=rule.team,
        duplicate_group_key=rule.duplicate_group_key,
        rationale=f"[{rule.name}] {rule.rationale}",
        consistency_ratio=1.0 if matched else 0.0,
    )


# --- Auditoría contra el consenso de Self-Consistency -------------------------------
EXPECTED_TRIAGE: dict[str, tuple[SeverityLevel, TeamName]] = {
    "INC-1001": ("P0", "Backend-Core"),
    "INC-1002": ("P2", "Security-IAM"),
    "INC-1003": ("P2", "Data-DBA"),
    "INC-1004": ("P3", "Backend-Core"),
    "INC-1005": ("P1", "Data-DBA"),
    "INC-1006": ("P0", "Backend-Core"),
    "INC-1007": ("P0", "Security-IAM"),
    "INC-1008": ("P2", "Data-DBA"),
    "INC-1009": ("P2", "Backend-Core"),
    "INC-1010": ("P3", "Platform-SRE"),
}

EXPECTED_DUPLICATE_GROUPS: set[frozenset[str]] = {
    frozenset({"INC-1001", "INC-1006"}),
    frozenset({"INC-1003", "INC-1008"}),
}


def _run_triage_audit() -> None:
    incidents = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    results = [classify_incident_report(item["id"], item["raw_text"]) for item in incidents]

    print(f"{'ID':<10}{'SEV':<5}{'COMPONENTE':<20}{'EQUIPO':<14}CLAVE")
    for r in results:
        print(
            f"{r.incident_id:<10}{r.severity:<5}{r.component:<20}"
            f"{r.recommended_team:<14}{r.duplicate_group_key}"
        )

    by_id = {r.incident_id: r for r in results}
    assert set(by_id) == set(EXPECTED_TRIAGE), "El dataset no coincide con los IDs esperados"
    for incident_id, (severity, team) in EXPECTED_TRIAGE.items():
        got = (by_id[incident_id].severity, by_id[incident_id].recommended_team)
        assert got == (severity, team), f"{incident_id}: esperado {(severity, team)}, obtenido {got}"

    groups: dict[str, set[str]] = defaultdict(set)
    for r in results:
        groups[r.duplicate_group_key].add(r.incident_id)
    detected = {frozenset(ids) for ids in groups.values() if len(ids) > 1}
    assert detected == EXPECTED_DUPLICATE_GROUPS, f"Duplicados inesperados: {detected}"

    print("\nOK: 10/10 clasificaciones y grupos de duplicados coinciden con el consenso.")


if __name__ == "__main__":
    _run_triage_audit()
