"""
Système de Session Management avec Révocation Globale pour Aegis.

Gère les sessions utilisateur avec support de la révocation globale, expiration,
et gestion multi-device avec patterns de sécurité avancés.
"""

import hashlib
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from aegis.core.domain.values import SubjectId


class SessionStatus(str, Enum):
    """Statuts de session."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    TERMINATED = "terminated"


class SessionBackend(str, Enum):
    """Types de backend pour les sessions."""

    MEMORY = "memory"
    REDIS = "redis"
    DATABASE = "database"


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """Informations de session."""

    session_id: str
    subject_id: SubjectId
    user_agent: str = ""
    ip_address: str = ""
    device_type: str = "unknown"
    location: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Vérifie si la session a expiré."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        """Vérifie si la session est valide."""
        return self.status == SessionStatus.ACTIVE and not self.is_expired()

    def update_activity(self) -> "SessionInfo":
        """Met à jour la dernière activité."""
        return SessionInfo(
            session_id=self.session_id,
            subject_id=self.subject_id,
            user_agent=self.user_agent,
            ip_address=self.ip_address,
            device_type=self.device_type,
            location=self.location,
            created_at=self.created_at,
            last_activity=datetime.now(timezone.utc),
            expires_at=self.expires_at,
            status=self.status,
            metadata=self.metadata,
        )

    def revoke(self) -> "SessionInfo":
        """Révoque la session."""
        return SessionInfo(
            session_id=self.session_id,
            subject_id=self.subject_id,
            user_agent=self.user_agent,
            ip_address=self.ip_address,
            device_type=self.device_type,
            location=self.location,
            created_at=self.created_at,
            last_activity=self.last_activity,
            expires_at=self.expires_at,
            status=SessionStatus.REVOKED,
            metadata=self.metadata,
        )


class SessionStore(ABC):
    """Interface de stockage des sessions."""

    @abstractmethod
    def create_session(self, session: SessionInfo) -> None:
        """Crée une nouvelle session."""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Récupère une session par son ID."""
        pass

    @abstractmethod
    def update_session(self, session: SessionInfo) -> None:
        """Met à jour une session."""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Supprime une session."""
        pass

    @abstractmethod
    def get_subject_sessions(self, subject_id: SubjectId) -> List[SessionInfo]:
        """Récupère toutes les sessions d'un sujet."""
        pass

    @abstractmethod
    def revoke_subject_sessions(self, subject_id: SubjectId) -> int:
        """Révoque toutes les sessions d'un sujet."""
        pass

    @abstractmethod
    def cleanup_expired_sessions(self) -> int:
        """Nettoie les sessions expirées."""
        pass


class InMemorySessionStore(SessionStore):
    """Implémentation en mémoire du stockage de sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._subject_index: Dict[SubjectId, Set[str]] = {}
        self._lock = threading.Lock()

    def create_session(self, session: SessionInfo) -> None:
        """Crée une nouvelle session."""
        with self._lock:
            self._sessions[session.session_id] = session

            if session.subject_id not in self._subject_index:
                self._subject_index[session.subject_id] = set()
            self._subject_index[session.subject_id].add(session.session_id)

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Récupère une session par son ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, session: SessionInfo) -> None:
        """Met à jour une session."""
        with self._lock:
            if session.session_id in self._sessions:
                self._sessions[session.session_id] = session

    def delete_session(self, session_id: str) -> bool:
        """Supprime une session."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                del self._sessions[session_id]

                if session.subject_id in self._subject_index:
                    self._subject_index[session.subject_id].discard(session_id)
                    if not self._subject_index[session.subject_id]:
                        del self._subject_index[session.subject_id]

                return True
            return False

    def get_subject_sessions(self, subject_id: SubjectId) -> List[SessionInfo]:
        """Récupère toutes les sessions d'un sujet."""
        with self._lock:
            session_ids = self._subject_index.get(subject_id, set())
            return [self._sessions[sid] for sid in session_ids if sid in self._sessions]

    def revoke_subject_sessions(self, subject_id: SubjectId) -> int:
        """Révoque toutes les sessions d'un sujet."""
        with self._lock:
            session_ids = self._subject_index.get(subject_id, set()).copy()
            revoked_count = 0

            for session_id in session_ids:
                if session_id in self._sessions:
                    session = self._sessions[session_id]
                    self._sessions[session_id] = session.revoke()
                    revoked_count += 1

            return revoked_count

    def cleanup_expired_sessions(self) -> int:
        """Nettoie les sessions expirées."""
        with self._lock:
            expired_ids = [sid for sid, session in self._sessions.items() if session.is_expired()]

            for session_id in expired_ids:
                self.delete_session(session_id)

            return len(expired_ids)


class SessionManager:
    """Gestionnaire de sessions avec logique métier."""

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        default_ttl_seconds: int = 3600,
        max_sessions_per_subject: int = 5,
    ) -> None:
        self._store = session_store or InMemorySessionStore()
        self._default_ttl = default_ttl_seconds
        self._max_sessions_per_subject = max_sessions_per_subject

    def create_session(
        self,
        subject_id: SubjectId,
        user_agent: str = "",
        ip_address: str = "",
        device_type: str = "unknown",
        ttl_seconds: Optional[int] = None,
    ) -> SessionInfo:
        """Crée une nouvelle session pour un sujet."""
        # Vérifier le nombre maximal de sessions
        existing_sessions = self._store.get_subject_sessions(subject_id)
        active_sessions = [s for s in existing_sessions if s.is_valid()]

        if len(active_sessions) >= self._max_sessions_per_subject:
            # Révoquer la session la plus ancienne
            oldest_session = min(active_sessions, key=lambda s: s.created_at)
            self.revoke_session(oldest_session.session_id)

        # Générer un ID de session sécurisé
        session_id = self._generate_session_id(subject_id)

        # Calculer l'expiration
        ttl = ttl_seconds or self._default_ttl
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        session = SessionInfo(
            session_id=session_id,
            subject_id=subject_id,
            user_agent=user_agent,
            ip_address=ip_address,
            device_type=device_type,
            expires_at=expires_at,
        )

        self._store.create_session(session)
        return session

    def _generate_session_id(self, subject_id: SubjectId) -> str:
        """Génère un ID de session sécurisé et unique."""
        # Combiner le subject_id avec un token aléatoire et un timestamp
        timestamp = int(time.time())
        random_token = secrets.token_urlsafe(32)

        # Hasher pour éviter la fuite d'information
        hash_input = f"{subject_id.value}:{timestamp}:{random_token}".encode()
        session_hash = hashlib.sha256(hash_input).hexdigest()

        return f"ses_{session_hash[:32]}"

    def validate_session(self, session_id: str) -> Optional[SessionInfo]:
        """Valide une session et la met à jour."""
        session = self._store.get_session(session_id)

        if session is None:
            return None

        if not session.is_valid():
            return None

        # Mettre à jour la dernière activité
        updated_session = session.update_activity()
        self._store.update_session(updated_session)

        return updated_session

    def revoke_session(self, session_id: str) -> bool:
        """Révoque une session spécifique."""
        session = self._store.get_session(session_id)
        if session is None:
            return False

        revoked_session = session.revoke()
        self._store.update_session(revoked_session)
        return True

    def revoke_all_subject_sessions(self, subject_id: SubjectId) -> int:
        """Révoque toutes les sessions d'un sujet (révocation globale)."""
        return self._store.revoke_subject_sessions(subject_id)

    def get_subject_sessions(self, subject_id: SubjectId) -> List[SessionInfo]:
        """Récupère toutes les sessions d'un sujet."""
        return self._store.get_subject_sessions(subject_id)

    def get_active_sessions(self, subject_id: SubjectId) -> List[SessionInfo]:
        """Récupère uniquement les sessions actives d'un sujet."""
        all_sessions = self._store.get_subject_sessions(subject_id)
        return [s for s in all_sessions if s.is_valid()]

    def cleanup_expired_sessions(self) -> int:
        """Nettoie les sessions expirées."""
        return self._store.cleanup_expired_sessions()

    def terminate_session(self, session_id: str) -> bool:
        """Termine immédiatement une session."""
        session = self._store.get_session(session_id)
        if session is None:
            return False

        terminated_session = SessionInfo(
            session_id=session.session_id,
            subject_id=session.subject_id,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            device_type=session.device_type,
            location=session.location,
            created_at=session.created_at,
            last_activity=session.last_activity,
            expires_at=session.expires_at,
            status=SessionStatus.TERMINATED,
            metadata=session.metadata,
        )

        self._store.update_session(terminated_session)
        return True

    def extend_session(self, session_id: str, additional_seconds: int = 3600) -> bool:
        """Étend la durée de vie d'une session."""
        session = self._store.get_session(session_id)
        if session is None or not session.is_valid():
            return False

        new_expires_at = session.expires_at + timedelta(seconds=additional_seconds) if session.expires_at else None
        extended_session = SessionInfo(
            session_id=session.session_id,
            subject_id=session.subject_id,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            device_type=session.device_type,
            location=session.location,
            created_at=session.created_at,
            last_activity=datetime.now(timezone.utc),
            expires_at=new_expires_at,
            status=session.status,
            metadata=session.metadata,
        )

        self._store.update_session(extended_session)
        return True

    def get_session_statistics(self, subject_id: Optional[SubjectId] = None) -> Dict[str, int]:
        """Retourne des statistiques sur les sessions."""
        if subject_id:
            sessions = self._store.get_subject_sessions(subject_id)
        else:
            # Pour l'instant, limitation à un sujet spécifique
            return {"total": 0, "active": 0, "expired": 0, "revoked": 0}

        stats = {
            "total": len(sessions),
            "active": sum(1 for s in sessions if s.is_valid()),
            "expired": sum(1 for s in sessions if s.is_expired()),
            "revoked": sum(1 for s in sessions if s.status == SessionStatus.REVOKED),
        }

        return stats


class SessionSecurityPolicy:
    """Politique de sécurité pour les sessions."""

    def __init__(
        self,
        max_concurrent_sessions: int = 5,
        session_timeout_seconds: int = 3600,
        idle_timeout_seconds: int = 1800,
        revoke_on_password_change: bool = True,
        revoke_on_security_event: bool = True,
    ) -> None:
        self._max_concurrent_sessions = max_concurrent_sessions
        self._session_timeout = session_timeout_seconds
        self._idle_timeout = idle_timeout_seconds
        self._revoke_on_password_change = revoke_on_password_change
        self._revoke_on_security_event = revoke_on_security_event

    def should_revoke_on_password_change(self) -> bool:
        """Vérifie si les sessions doivent être révoquées lors d'un changement de mot de passe."""
        return self._revoke_on_password_change

    def should_revoke_on_security_event(self) -> bool:
        """Vérifie si les sessions doivent être révoquées lors d'un événement de sécurité."""
        return self._revoke_on_security_event

    def is_session_timeout_valid(self, session: SessionInfo) -> bool:
        """Vérifie si la session n'a pas dépassé le timeout d'inactivité."""
        if session.last_activity is None:
            return False

        idle_time = (datetime.now(timezone.utc) - session.last_activity).total_seconds()
        return idle_time < self._idle_timeout

    def get_max_concurrent_sessions(self) -> int:
        """Retourne le nombre maximal de sessions concurrentes."""
        return self._max_concurrent_sessions


class SessionService:
    """Service de gestion des sessions avec politique de sécurité."""

    def __init__(
        self, session_manager: SessionManager, security_policy: Optional[SessionSecurityPolicy] = None
    ) -> None:
        self._manager = session_manager
        self._security_policy = security_policy or SessionSecurityPolicy()

    def create_secure_session(
        self, subject_id: SubjectId, user_agent: str = "", ip_address: str = "", device_type: str = "unknown"
    ) -> SessionInfo:
        """Crée une session avec application de la politique de sécurité."""
        session = self._manager.create_session(
            subject_id=subject_id,
            user_agent=user_agent,
            ip_address=ip_address,
            device_type=device_type,
            ttl_seconds=self._security_policy._session_timeout,
        )

        return session

    def validate_session_with_security(self, session_id: str) -> Optional[SessionInfo]:
        """Valide une session avec vérifications de sécurité."""
        session = self._manager.validate_session(session_id)

        if session is None:
            return None

        # Vérifier le timeout d'inactivité
        if not self._security_policy.is_session_timeout_valid(session):
            self._manager.revoke_session(session_id)
            return None

        return session

    def revoke_on_password_change(self, subject_id: SubjectId) -> int:
        """Révoque toutes les sessions lors d'un changement de mot de passe."""
        if self._security_policy.should_revoke_on_password_change():
            return self._manager.revoke_all_subject_sessions(subject_id)
        return 0

    def revoke_on_security_event(self, subject_id: SubjectId) -> int:
        """Révoque toutes les sessions lors d'un événement de sécurité."""
        if self._security_policy.should_revoke_on_security_event():
            return self._manager.revoke_all_subject_sessions(subject_id)
        return 0

    def get_security_info(self, subject_id: SubjectId) -> Dict[str, Any]:
        """Retourne des informations de sécurité sur les sessions d'un sujet."""
        sessions = self._manager.get_subject_sessions(subject_id)
        active_sessions = [s for s in sessions if s.is_valid()]

        return {
            "subject_id": subject_id.value,
            "total_sessions": len(sessions),
            "active_sessions": len(active_sessions),
            "max_concurrent": self._security_policy.get_max_concurrent_sessions(),
            "sessions_exceeded": len(active_sessions) > self._security_policy.get_max_concurrent_sessions(),
            "session_details": [
                {
                    "session_id": s.session_id,
                    "device_type": s.device_type,
                    "ip_address": s.ip_address,
                    "last_activity": s.last_activity.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "status": s.status.value,
                }
                for s in active_sessions
            ],
        }


# Factory pour créer des configurations de session courantes
class SessionFactory:
    """Factory pour créer des configurations de session."""

    @staticmethod
    def create_default_manager() -> SessionManager:
        """Crée un gestionnaire de sessions avec configuration par défaut."""
        return SessionManager(default_ttl_seconds=3600, max_sessions_per_subject=5)

    @staticmethod
    def create_security_manager() -> SessionService:
        """Crée un service de sessions avec politique de sécurité renforcée."""
        manager = SessionFactory.create_default_manager()
        security_policy = SessionSecurityPolicy(
            max_concurrent_sessions=3,
            session_timeout_seconds=1800,
            idle_timeout_seconds=900,
            revoke_on_password_change=True,
            revoke_on_security_event=True,
        )
        return SessionService(manager, security_policy)

    @staticmethod
    def create_high_security_manager() -> SessionService:
        """Crée un service de sessions avec politique de sécurité maximale."""
        manager = SessionManager(default_ttl_seconds=900, max_sessions_per_subject=1)
        security_policy = SessionSecurityPolicy(
            max_concurrent_sessions=1,
            session_timeout_seconds=900,
            idle_timeout_seconds=300,
            revoke_on_password_change=True,
            revoke_on_security_event=True,
        )
        return SessionService(manager, security_policy)
