"""Puertos secundarios (driven ports) de IncidentOps.

Los adaptadores de `src/adapters/outbound/` los implementan por tipado estructural (Protocol),
sin heredar de ellos.
"""

from typing import Optional, Protocol, runtime_checkable

from src.domain.models import Incident


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Contrato de persistencia de incidentes."""

    def save_incident(self, incident: Incident) -> None:
        """Inserta o actualiza un incidente (upsert por `incident_id`)."""
        ...

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Devuelve el incidente o `None` si no existe."""
        ...

    def find_open_duplicates(
        self, duplicate_group_key: str, exclude_incident_id: Optional[str] = None
    ) -> list[Incident]:
        """Incidentes abiertos (`OPEN_STATUSES`) con la misma clave, excluyendo un ID."""
        ...

    def list_active_incidents(self, component: Optional[str] = None) -> list[Incident]:
        """Incidentes `OPEN`/`IN_PROGRESS`, opcionalmente filtrados por componente."""
        ...

    def check_health(self) -> bool:
        """Ejecuta una consulta real (`SELECT 1`); `False` ante cualquier fallo de conectividad."""
        ...
