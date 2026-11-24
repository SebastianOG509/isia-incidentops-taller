"""Selección del adaptador de persistencia a partir de `DATABASE_URL` (ADR-004)."""

from typing import Optional

from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SQLITE_PREFIX = "sqlite:///"
POSTGRES_PREFIXES = ("postgresql://", "postgres://")


def create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort:
    """`postgresql://` → PostgreSQL; `sqlite:///` o ausencia → SQLite (`:memory:` por defecto)."""
    url = (database_url or "").strip() or DEFAULT_DATABASE_URL
    if url.startswith(POSTGRES_PREFIXES):
        return PostgresIncidentRepository(url)
    if url.startswith(SQLITE_PREFIX):
        return SQLiteIncidentRepository(url[len(SQLITE_PREFIX):] or ":memory:")
    raise ValueError(f"DATABASE_URL no soportada: {url!r} (usa postgresql:// o sqlite:///)")
