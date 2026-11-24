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

    def list_active_incidents(self, component: Optional[str] = None) -> list[Incident]:
        """Incidentes `OPEN`/`IN_PROGRESS`, opcionalmente filtrados por componente."""
        ...
