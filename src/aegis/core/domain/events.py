"""
Événements de Domaine (Domain Events) pour Aegis.

Contient les événements de sécurité immutables produits lors des mutations d'état.
Ces événements sont destinés au Transactional Outbox pour alimenter les logs d'audit,
les notifications et la synchronisation inter-services.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict

from aegis.core.domain.values import SubjectId


@dataclass(frozen=True, slots=True)
class DomainEvent(ABC):
    """Classe de base immutable pour tous les événements de domaine.

    Complexité Spatiale: O(1) mémoire constante.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Type d'événement unique (ex: 'IDENTITY_REGISTERED')."""
        pass

    @property
    @abstractmethod
    def aggregate_id(self) -> str:
        """Identifiant de l'aggregate concerné."""
        pass

    @abstractmethod
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convertit l'événement en dictionnaire sécurisé sans PII en clair."""
        pass


@dataclass(frozen=True, slots=True)
class SubjectRegisteredEvent(DomainEvent):
    """Événement émis lors de l'enregistrement d'un nouvel acteur."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    subject_type: str = ""
    email_anonymized: Optional[str] = None

    @property
    def event_type(self) -> str:
        return "SUBJECT_REGISTERED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "subject_type": self.subject_type,
            "email_anonymized": self.email_anonymized,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SubjectStatusChangedEvent(DomainEvent):
    """Événement émis lors de la suspension ou réactivation d'un acteur."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    is_active: bool = False
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "SUBJECT_ACTIVATED" if self.is_active else "SUBJECT_SUSPENDED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "is_active": self.is_active,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }
