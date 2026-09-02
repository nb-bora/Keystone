"""
Driver In-Memory Officiel d'Aegis pour Tests Unitaires & Dev Local.

Fournit des implémentations légères, ultra-rapides et thread-safe sans aucune
dépendance de base de données externe.
"""

import hashlib
import hmac
import os
from typing import Dict, List, Optional

from aegis.core.application.ports import EventOutbox, PasswordHasher, SubjectRepository
from aegis.core.domain.entities import HumanIdentity, Subject
from aegis.core.domain.events import DomainEvent
from aegis.core.domain.values import EmailAddress, SubjectId


class InMemorySubjectRepository(SubjectRepository):
    """Repository d'Identités In-Memory basé sur un dictionnaire Python.

    Complexité Temporelle:
    - get_by_id: O(1)
    - get_by_email: O(N) où N est le nombre d'identités
    - save: O(1)
    - delete: O(1)
    """

    def __init__(self) -> None:
        self._storage: Dict[SubjectId, Subject] = {}
        self._email_index: Dict[str, SubjectId] = {}

    def get_by_id(self, subject_id: SubjectId) -> Optional[Subject]:
        return self._storage.get(subject_id)

    def get_by_email(self, email: EmailAddress) -> Optional[HumanIdentity]:
        subject_id = self._email_index.get(email.value)
        if subject_id is None:
            return None
        subject = self._storage.get(subject_id)
        if isinstance(subject, HumanIdentity):
            return subject
        return None

    def save(self, subject: Subject) -> None:
        self._storage[subject.id] = subject
        if isinstance(subject, HumanIdentity) and subject.email is not None:
            self._email_index[subject.email.value] = subject.id

    def delete(self, subject_id: SubjectId) -> bool:
        subject = self._storage.pop(subject_id, None)
        if subject is not None:
            if isinstance(subject, HumanIdentity) and subject.email is not None:
                self._email_index.pop(subject.email.value, None)
            return True
        return False

    def clear(self) -> None:
        """Re-initialise le stockage (utile entre deux tests)."""
        self._storage.clear()
        self._email_index.clear()


class InMemoryEventOutbox(EventOutbox):
    """Transactional Outbox In-Memory pour capturer les événements durant les tests."""

    def __init__(self) -> None:
        self._events: List[DomainEvent] = []
        self._published_ids: set[str] = set()

    def publish(self, event: DomainEvent) -> None:
        self._events.append(event)

    def get_pending_events(self, batch_size: int = 100) -> List[DomainEvent]:
        pending = [e for e in self._events if e.event_id not in self._published_ids]
        return pending[:batch_size]

    def mark_as_published(self, event_ids: List[str]) -> None:
        self._published_ids.update(event_ids)

    def clear(self) -> None:
        self._events.clear()
        self._published_ids.clear()


class Pbkdf2PasswordHasher(PasswordHasher):
    """Hasher de mots de passe sécurisé utilisant la stdlib (hashlib.pbkdf2_hmac).

    Conforme aux recommandations OWASP avec PBKDF2-HMAC-SHA256.
    Vérification en temps constant via hmac.compare_digest pour contrer les timing attacks.
    """

    def __init__(self, iterations: int = 100_000) -> None:
        self._iterations = iterations

    def hash(self, secret: str) -> str:
        salt = os.urandom(16)
        derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, self._iterations)
        return f"pbkdf2_sha256${self._iterations}${salt.hex()}${derived.hex()}"

    def verify(self, secret: str, hashed_value: str) -> bool:
        try:
            parts = hashed_value.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected_derived = bytes.fromhex(parts[3])

            actual_derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
            # hmac.compare_digest pour une comparaison O(N) constante insensible aux attaques temporelles
            return hmac.compare_digest(actual_derived, expected_derived)
        except Exception:
            return False
