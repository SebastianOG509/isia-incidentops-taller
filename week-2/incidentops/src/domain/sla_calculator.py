"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

Implementa la decisión del ADR-002 (docs/adr/002-calculo-sla-horario-habil.md):
- Severidades con `operates_24x7=True` (P0, P1) cuentan tiempo de reloj continuo.
- Severidades con `operates_24x7=False` (P2, P3) cuentan solo minutos hábiles:
  Lunes a Viernes, 08:00 a 18:00 (600 min/día; fines de semana = 0).
- Un incidente abierto (`status != "RESOLVED"` y `resolved_at is None`) requiere
  escalamiento cuando alcanza el umbral preventivo, incluso si ya incumplió el SLA.

Normalización temporal (Hito 003): toda marca con zona horaria se convierte a la hora local de
operación (`BUSINESS_TZ`, UTC-05:00 fija, Colombia sin horario de verano) y se trata como naive;
las marcas naive se asumen ya en hora local. Festivos fuera de alcance.
Solo usa la biblioteca estándar y el resultado es determinista.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Dict, Optional

from src.domain.models import Incident, SLAEvaluation, SLARule, SeverityLevel

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

BUSINESS_DAY_START = time(8, 0)
BUSINESS_DAY_END = time(18, 0)
BUSINESS_TZ = timezone(timedelta(hours=-5), name="America/Bogota")


def normalize_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    """Convierte una marca aware a hora local naive de `BUSINESS_TZ`; deja intactas las naive."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(BUSINESS_TZ).replace(tzinfo=None)


def now_local() -> datetime:
    """Instante actual en hora local de operación (naive), independiente del reloj del host."""
    return normalize_timestamp(datetime.now(timezone.utc))


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _business_minutes_between(start: datetime, end: datetime) -> int:
    """Cuenta los minutos hábiles (L-V 08:00-18:00) entre `start` y `end`.

    Recorre cada fecha calendario de `start.date()` a `end.date()`. Los sábados y
    domingos aportan 0; los días hábiles aportan la intersección de `[start, end]`
    con la ventana `[08:00, 18:00)`. Los segundos se acumulan y se convierten a
    minutos una sola vez para no acumular truncamientos por día.

    Args:
        start: Inicio del intervalo (naive).
        end: Fin del intervalo (naive).

    Returns:
        Minutos hábiles completos; 0 si `end <= start`.
    """
    if end <= start:
        return 0

    total = timedelta(0)
    current_day = start.date()
    last_day = end.date()
    one_day = timedelta(days=1)

    while current_day <= last_day:
        if current_day.weekday() < 5:  # 0=Lunes ... 4=Viernes
            opening = datetime.combine(current_day, BUSINESS_DAY_START)
            closing = datetime.combine(current_day, BUSINESS_DAY_END)
            window_start = max(start, opening)
            window_end = min(end, closing)
            if window_end > window_start:
                total += window_end - window_start
        current_day += one_day

    return int(total.total_seconds() // 60)


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Para P0/P1 (`operates_24x7=True`) se usa el delta de reloj; para P2/P3 solo se
    cuentan minutos hábiles. Un incidente abierto que alcanza el umbral de
    escalamiento sigue escalado aunque ya haya incumplido el SLA.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes (pueden ser negativos)
        y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    created_at = normalize_timestamp(incident.created_at)
    end_time = normalize_timestamp(incident.resolved_at or reference_time)

    if end_time < created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        delta_seconds = (end_time - created_at).total_seconds()
        elapsed_minutes = int(delta_seconds // 60)
    else:
        elapsed_minutes = _business_minutes_between(created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    is_open = incident.status != "RESOLVED" and incident.resolved_at is None
    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
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


def _run_verification() -> None:
    """Ejecuta todos los casos de la tabla de Verificación del ADR-002 con asserts."""
    # Semana de referencia: viernes 2026-11-06, sábado 07, domingo 08, lunes 09.
    fri = datetime(2026, 11, 6)
    sat = datetime(2026, 11, 7)
    sun = datetime(2026, 11, 8)
    mon = datetime(2026, 11, 9)
    mon_plus_10 = datetime(2026, 11, 16)  # Lunes 10 días después del viernes

    def at(day: datetime, hour: int, minute: int = 0) -> datetime:
        return day.replace(hour=hour, minute=minute)

    # (caso, severidad, inicio, referencia, resolved_at, elapsed, is_breached, requires_escalation)
    cases = [
        ("Bug reportado", "P2", at(fri, 18, 30), at(mon, 8, 30), None, 30, False, False),
        ("Fin de semana", "P2", at(sat, 9), at(sun, 17), None, 0, False, False),
        ("Cruce fin de semana", "P2", at(sat, 10), at(mon, 10), None, 120, False, False),
        ("Multi-semana", "P3", at(fri, 17), at(mon_plus_10, 9), None, 3120, True, True),
        ("Umbral 75 %", "P2", at(fri, 14), at(mon, 10), None, 360, False, True),
        ("Borde apertura", "P2", at(mon, 7), at(mon, 8), None, 0, False, False),
        ("Borde cierre", "P2", at(mon, 18), at(mon, 19), None, 0, False, False),
        ("Día completo", "P2", at(mon, 8), at(mon, 18), None, 600, True, True),
        ("24/7 sin cambio", "P0", at(fri, 17), at(mon, 9), None, 3840, True, True),
        ("24/7 sin cambio", "P1", at(mon, 8), at(mon, 10, 30), None, 150, False, False),
        # Resuelto: se mide hasta resolved_at (lun 10:00), no hasta la referencia (lun 12:00).
        ("Resuelto", "P2", at(fri, 14), at(mon, 12), at(mon, 10), 360, False, False),
    ]

    header = (
        f"{'Caso':<20} {'Sev':<4} {'Inicio':<16} {'Fin':<16} "
        f"{'Elapsed':>7} {'Breach':>6} {'Escal':>6}"
    )
    print("=== Verificación determinista ADR-002 ===")
    print(header)
    print("-" * len(header))

    for idx, (name, sev, start, ref, resolved, exp_el, exp_br, exp_esc) in enumerate(cases, 1):
        incident = Incident(
            incident_id=f"INC-V{idx:02d}",
            title=name,
            component="sla-verification",
            severity=sev,
            status="RESOLVED" if resolved else "OPEN",
            created_at=start,
            resolved_at=resolved,
        )
        result = evaluate_sla_status(incident, reference_time=ref)
        end = resolved or ref
        print(
            f"{name:<20} {sev:<4} {start:%Y-%m-%d %H:%M} {end:%Y-%m-%d %H:%M} "
            f"{result.elapsed_minutes:>7} {str(result.is_breached):>6} "
            f"{str(result.requires_escalation):>6}"
        )
        assert result.elapsed_minutes == exp_el, (name, result.elapsed_minutes, exp_el)
        assert result.is_breached == exp_br, (name, result.is_breached, exp_br)
        assert result.requires_escalation == exp_esc, (name, result.requires_escalation, exp_esc)
        assert result.remaining_minutes == result.allowed_minutes - exp_el, name

    print("-" * len(header))
    print(f"OK: {len(cases)} casos verificados.")


if __name__ == "__main__":
    _run_verification()
