"""Adaptador secundario PostgreSQL (psycopg 3, sin ORM) de IncidentRepositoryPort (ADR-004).

- SQL parametrizado con `%s` y filas como diccionarios (`dict_row`).
- Conexión por operación con `connect_timeout` corto: tolera reinicios del contenedor `db`.
- Esquema perezoso: se crea en la primera operación de datos, no al construir el objeto, para que
  el servicio arranque y reporte `503` aunque la base no esté disponible.
- Fechas como `TEXT` ISO 8601 (paridad temporal con SQLite).
"""

from datetime import datetime
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from src.domain.models import OPEN_STATUSES, Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE

ACTIVE_STATUSES = ("OPEN", "IN_PROGRESS")
CONNECT_TIMEOUT_SECONDS = 3
_COLUMNS = (
    "incident_id, title, component, severity, status, created_at, resolved_at, "
    "recommended_team, duplicate_group_key"
)
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS sla_policies (
        severity TEXT PRIMARY KEY,
        max_resolution_minutes INTEGER NOT NULL,
        operates_24x7 BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        component TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        recommended_team TEXT,
        duplicate_group_key TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status)",
)


def _to_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _row_to_incident(row: dict[str, Any]) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        component=row["component"],
        severity=row["severity"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolved_at=_to_datetime(row["resolved_at"]),
        recommended_team=row["recommended_team"],
        duplicate_group_key=row["duplicate_group_key"],
    )


class PostgresIncidentRepository:
    """Persistencia de incidentes en PostgreSQL."""

    def __init__(self, database_url: str, connect_timeout: int = CONNECT_TIMEOUT_SECONDS) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self._schema_ready = False

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(
            self.database_url, row_factory=dict_row, connect_timeout=self.connect_timeout
        )

    def _ensure_schema(self, conn: psycopg.Connection) -> None:
        if self._schema_ready:
            return
        with conn.cursor() as cur:
            for statement in _SCHEMA:
                cur.execute(statement)
            cur.executemany(
                """
                INSERT INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                VALUES (%s, %s, %s)
                ON CONFLICT (severity) DO UPDATE SET
                    max_resolution_minutes = EXCLUDED.max_resolution_minutes,
                    operates_24x7 = EXCLUDED.operates_24x7
                """,
                [
                    (r.severity, r.max_resolution_minutes, r.operates_24x7)
                    for r in SLA_POLICY_TABLE.values()
                ],
            )
        self._schema_ready = True

    def _fetch_all(self, sql: str, params: tuple) -> list[Incident]:
        with self._connect() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_incident(row) for row in rows]

    def save_incident(self, incident: Incident) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            conn.execute(
                f"""
                INSERT INTO incidents ({_COLUMNS})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    component = EXCLUDED.component,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    resolved_at = EXCLUDED.resolved_at,
                    recommended_team = EXCLUDED.recommended_team,
                    duplicate_group_key = EXCLUDED.duplicate_group_key
                """,
                (
                    incident.incident_id,
                    incident.title,
                    incident.component,
                    incident.severity,
                    incident.status,
                    incident.created_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                    incident.recommended_team,
                    incident.duplicate_group_key,
                ),
            )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        found = self._fetch_all(
            f"SELECT {_COLUMNS} FROM incidents WHERE incident_id = %s", (incident_id,)
        )
        return found[0] if found else None

    def find_open_duplicates(
        self, duplicate_group_key: str, exclude_incident_id: Optional[str] = None
    ) -> list[Incident]:
        return self._fetch_all(
            f"SELECT {_COLUMNS} FROM incidents "
            "WHERE duplicate_group_key = %s AND status = ANY(%s) AND incident_id <> %s "
            "ORDER BY created_at, incident_id",
            (duplicate_group_key, list(OPEN_STATUSES), exclude_incident_id or ""),
        )

    def list_active_incidents(self, component: Optional[str] = None) -> list[Incident]:
        sql = (
            "SELECT i.* FROM incidents i "
            "INNER JOIN sla_policies p ON p.severity = i.severity "
            "WHERE i.status = ANY(%s)"
        )
        params: list[Any] = [list(ACTIVE_STATUSES)]
        if component:
            sql += " AND i.component = %s"
            params.append(component)
        sql += " ORDER BY i.created_at, i.incident_id"
        return self._fetch_all(sql, tuple(params))

    def check_health(self) -> bool:
        """Ejecuta `SELECT 1` real; cualquier fallo de conexión o consulta devuelve False."""
        try:
            with self._connect() as conn:
                return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
        except (psycopg.Error, OSError):
            return False
