"""Selección del adaptador de persistencia a partir de `DATABASE_URL`."""

from typing import Optional

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SQLITE_PREFIX = "sqlite:///"


def create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort:
    """Crea el repositorio adecuado; sin URL usa SQLite en memoria."""
    url = (database_url or DEFAULT_DATABASE_URL).strip()
    if url.startswith(SQLITE_PREFIX):
        return SQLiteIncidentRepository(url[len(SQLITE_PREFIX):] or ":memory:")
    raise ValueError(f"DATABASE_URL no soportada: {url!r}")
