"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

Reglas (ver docs/adr/002-calculo-sla-horario-habil.md):
- P0/P1 (`operates_24x7=True`): minutos en calendario continuo.
- P2/P3 (`operates_24x7=False`): solo minutos dentro de Lunes-Viernes 08:00-18:00.
- Escalamiento preventivo: incidente no resuelto con elapsed >= 75% del SLA (incluye vencidos).
"""

from datetime import datetime, time, timedelta
from typing import Dict

from src.models import Incident, SLAEvaluation, SLARule, SeverityLevel

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

BUSINESS_START = time(8, 0)
BUSINESS_END = time(18, 0)


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _business_minutes_between(start: datetime, end: datetime) -> int:
    """Minutos entre `start` y `end` dentro de Lunes-Viernes 08:00-18:00. O(D) en días."""
    total_seconds = 0.0
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5:  # 0=lunes ... 4=viernes
            window_start = max(start, datetime.combine(day, BUSINESS_START))
            window_end = min(end, datetime.combine(day, BUSINESS_END))
            if window_end > window_start:
                total_seconds += (window_end - window_start).total_seconds()
        day += timedelta(days=1)
    return int(total_seconds // 60)


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        elapsed_minutes = int((end_time - incident.created_at).total_seconds() // 60)
    else:
        elapsed_minutes = _business_minutes_between(incident.created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    # Un SLA vencido NO apaga el escalamiento; solo la resolución lo hace.
    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    is_open = incident.status != "RESOLVED" and incident.resolved_at is None
    requires_escalation = is_open and elapsed_minutes >= escalation_limit

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


def _run_demo() -> None:
    """Verifica casos borde con minutos esperados exactos (falla con AssertionError)."""
    D = datetime

    def inc(sev, created, status="OPEN", resolved=None):
        return Incident("INC-T", "t", "reporting-api", sev, status, created, resolved)

    # (descripción, incidente, referencia, elapsed, breached, escalation)
    cases = [
        ("P2 viernes 17:00 -> lunes 09:00 (cruce de fin de semana)",
         inc("P2", D(2026, 11, 6, 17, 0)), D(2026, 11, 9, 9, 0), 120, False, False),
        ("P2 viernes 18:30 (fuera de horario) -> lunes 08:30",
         inc("P2", D(2026, 11, 6, 18, 30)), D(2026, 11, 9, 8, 30), 30, False, False),
        ("P2 sábado 10:00 -> lunes 12:00 (creado en fin de semana)",
         inc("P2", D(2026, 11, 7, 10, 0)), D(2026, 11, 9, 12, 0), 240, False, False),
        ("P0 viernes 17:00 -> lunes 09:00 (24/7, mismo intervalo)",
         inc("P0", D(2026, 11, 6, 17, 0)), D(2026, 11, 9, 9, 0), 3840, True, True),
        ("P2 lunes 08:00 -> 14:00 (alcanza 75%: 360/480)",
         inc("P2", D(2026, 11, 9, 8, 0)), D(2026, 11, 9, 14, 0), 360, False, True),
        ("P2 lunes 08:00 -> 17:00 (vencido, sigue escalando)",
         inc("P2", D(2026, 11, 9, 8, 0)), D(2026, 11, 9, 17, 0), 540, True, True),
        ("P3 lunes 02-nov 09:00 -> lunes 16-nov 09:00 (dos fines de semana)",
         inc("P3", D(2026, 11, 2, 9, 0)), D(2026, 11, 16, 9, 0), 6000, True, True),
        ("P2 resuelto lunes 08:00 -> 15:00 (420 min, sin escalamiento)",
         inc("P2", D(2026, 11, 9, 8, 0), "RESOLVED", D(2026, 11, 9, 15, 0)),
         D(2026, 11, 20), 420, False, False),
        ("P3 sábado 10:00 -> sábado 20:00 (solo fin de semana)",
         inc("P3", D(2026, 11, 7, 10, 0)), D(2026, 11, 7, 20, 0), 0, False, False),
    ]

    print("=== Verificación determinista de SLA (horario hábil vs 24/7) ===")
    print(f"{'Caso':<66} | {'min':>5} | Venc. | Escal.")
    print("-" * 94)
    for desc, incident, ref, exp_min, exp_breach, exp_esc in cases:
        ev = evaluate_sla_status(incident, ref)
        assert ev.elapsed_minutes == exp_min, f"{desc}: {ev.elapsed_minutes} != {exp_min}"
        assert ev.is_breached == exp_breach, f"{desc}: is_breached={ev.is_breached}"
        assert ev.requires_escalation == exp_esc, f"{desc}: escalation={ev.requires_escalation}"
        print(f"{desc:<66} | {ev.elapsed_minutes:>5} | {str(ev.is_breached):<5} | {ev.requires_escalation}")
    print("-" * 94)
    print(f"OK: {len(cases)}/{len(cases)} casos con minutos exactos.")


if __name__ == "__main__":
    _run_demo()
