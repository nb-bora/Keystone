"""
Ports Applicatifs (Interfaces & Abstractions) pour Aegis.

Contient les interfaces abstraites que la couche d'infrastructure doit implémenter
(Repositories, Event Outbox, Hashers, Password Handlers).
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from aegis.core.domain.entities import HumanIdentity, Subject
from aegis.core.domain.events import DomainEvent
from aegis.core.domain.values import EmailAddress, SubjectId


class SubjectRepository(ABC):
    """Port de Persistance pour les Aggregates Subject.

    Abstrait l'accès à la base de données (Django ORM, SQLAlchemy, Redis, In-Memory).
    """

    @abstractmethod
    def get_by_id(self, subject_id: SubjectId) -> Optional[Subject]:
        """Récupère un sujet par son identifiant unique en O(1) moyen."""
        pass

    @abstractmethod
    def get_by_email(self, email: EmailAddress) -> Optional[HumanIdentity]:
        """Récupère une identité humaine par son adresse email."""
        pass

    @abstractmethod
    def save(self, subject: Subject) -> None:
        """Persiste ou met à jour un sujet."""
        pass

    @abstractmethod
    def delete(self, subject_id: SubjectId) -> bool:
        """Supprime un sujet par son identifiant."""
        pass


class EventOutbox(ABC):
    """Port de Traçabilité & Transactional Outbox.

    Garantit que tous les événements de domaine sont enregistrés avec la même
    atomicité que la transaction de données.
    """

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Enregistre un événement de domaine dans l'Outbox."""
        pass

    @abstractmethod
    def get_pending_events(self, batch_size: int = 100) -> List[DomainEvent]:
        """Récupère les événements en attente de publication."""
        pass

    @abstractmethod
    def mark_as_published(self, event_ids: List[str]) -> None:
        """Marque les événements spécifiés comme publiés."""
        pass


class PasswordHasher(ABC):
    """Port d'Abstraction du Hachage de Mots de Passe."""

    @abstractmethod
    def hash(self, secret: str) -> str:
        """Hache un mot de passe ou secret."""
        pass

    @abstractmethod
    def verify(self, secret: str, hashed_value: str) -> bool:
        """Vérifie un mot de passe contre son hachage en temps constant O(N)."""
        pass
