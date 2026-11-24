"""Adaptador secundario SQLite (`sqlite3` estándar, sin ORM) de IncidentRepositoryPort.

Extraído de `incident_repository.py` (Semana 1) eliminando el escaneo completo y el N+1:
una sola consulta filtrada en SQL con `INNER JOIN sla_policies` e índice `(component, status)`.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from src.domain.models import Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE

ACTIVE_STATUSES = ("OPEN", "IN_PROGRESS")


def _to_text(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _to_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class SQLiteIncidentRepository:
    """Persistencia de incidentes y políticas de SLA en SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                component TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_component_status "
            "ON incidents (component, status)"
        )
        cur.executemany(
            "INSERT OR REPLACE INTO sla_policies (severity, max_resolution_minutes, operates_24x7) "
            "VALUES (?, ?, ?)",
            [
                (r.severity, r.max_resolution_minutes, int(r.operates_24x7))
                for r in SLA_POLICY_TABLE.values()
            ],
        )
        self.conn.commit()

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> Incident:
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            component=row["component"],
            severity=row["severity"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=_to_datetime(row["resolved_at"]),
        )

    def save_incident(self, incident: Incident) -> None:
        self.conn.execute(
            """
            INSERT INTO incidents
                (incident_id, title, component, severity, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET
                title = excluded.title,
                component = excluded.component,
                severity = excluded.severity,
                status = excluded.status,
                created_at = excluded.created_at,
                resolved_at = excluded.resolved_at
            """,
            (
                incident.incident_id,
                incident.title,
                incident.component,
                incident.severity,
                incident.status,
                incident.created_at.isoformat(),
                _to_text(incident.resolved_at),
            ),
        )
        self.conn.commit()

    def list_active_incidents(self, component: Optional[str] = None) -> list[Incident]:
        sql = (
            "SELECT i.* FROM incidents i "
            "INNER JOIN sla_policies p ON p.severity = i.severity "
            "WHERE i.status IN (?, ?)"
        )
        params: list[str] = list(ACTIVE_STATUSES)
        if component:
            sql += " AND i.component = ?"
            params.append(component)
        sql += " ORDER BY i.created_at, i.incident_id"
        return [self._row_to_incident(row) for row in self.conn.execute(sql, params)]
