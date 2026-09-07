"""
Événements de Domaine (Domain Events) pour Aegis.

Contient les événements de sécurité immutables produits lors des mutations d'état.
Ces événements sont destinés au Transactional Outbox pour alimenter les logs d'audit,
les notifications et la synchronisation inter-services.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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


@dataclass(frozen=True, slots=True)
class PermissionGrantedEvent(DomainEvent):
    """Événement émis lorsqu'une permission est accordée à un sujet."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    permission: str = ""
    granted_by: Optional[SubjectId] = None
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "PERMISSION_GRANTED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "permission": self.permission,
            "granted_by": self.granted_by.value if self.granted_by else None,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PermissionRevokedEvent(DomainEvent):
    """Événement émis lorsqu'une permission est révoquée d'un sujet."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    permission: str = ""
    revoked_by: Optional[SubjectId] = None
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "PERMISSION_REVOKED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "permission": self.permission,
            "revoked_by": self.revoked_by.value if self.revoked_by else None,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AuthenticationSuccessEvent(DomainEvent):
    """Événement émis lors d'une authentification réussie."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    auth_method: str = ""
    ip_address: Optional[str] = None
    user_agent: str = ""
    device_type: str = "unknown"

    @property
    def event_type(self) -> str:
        return "AUTHENTICATION_SUCCESS"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "auth_method": self.auth_method,
            "ip_address": self._anonymize_ip(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "device_type": self.device_type,
            "occurred_at": self.occurred_at.isoformat(),
        }

    def _anonymize_ip(self, ip: str) -> str:
        """Anonymise partiellement l'adresse IP pour l'audit."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***.***.***.***"
        except Exception:
            return "***.***.***.***"


@dataclass(frozen=True, slots=True)
class AuthenticationFailureEvent(DomainEvent):
    """Événement émis lors d'une authentification échouée."""

    subject_id: Optional[SubjectId] = None
    auth_method: str = ""
    ip_address: Optional[str] = None
    user_agent: str = ""
    failure_reason: str = ""
    potential_subject_id: Optional[str] = None  # Pour les tentatives avec email incorrect

    @property
    def event_type(self) -> str:
        return "AUTHENTICATION_FAILURE"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value if self.subject_id else "unknown"

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "auth_method": self.auth_method,
            "ip_address": self._anonymize_ip(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "failure_reason": self.failure_reason,
            "potential_subject_id": self.potential_subject_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

    def _anonymize_ip(self, ip: str) -> str:
        """Anonymise partiellement l'adresse IP pour l'audit."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***.***.***.***"
        except Exception:
            return "***.***.***.***"


@dataclass(frozen=True, slots=True)
class AuthorizationDecisionEvent(DomainEvent):
    """Événement émis lors d'une décision d'autorisation."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    action: str = ""
    resource: str = ""
    decision: str = ""  # ALLOW, DENY, CONDITIONAL
    reason: str = ""
    policy_engine: str = ""

    @property
    def event_type(self) -> str:
        return "AUTHORIZATION_DECISION"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "action": self.action,
            "resource": self.resource,
            "decision": self.decision,
            "reason": self.reason,
            "policy_engine": self.policy_engine,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RoleAssignedEvent(DomainEvent):
    """Événement émis lorsqu'un rôle est assigné à un sujet."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    role_id: str = ""
    assigned_by: Optional[SubjectId] = None
    expires_at: Optional[datetime] = None

    @property
    def event_type(self) -> str:
        return "ROLE_ASSIGNED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "role_id": self.role_id,
            "assigned_by": self.assigned_by.value if self.assigned_by else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RoleRevokedEvent(DomainEvent):
    """Événement émis lorsqu'un rôle est révoqué d'un sujet."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    role_id: str = ""
    revoked_by: Optional[SubjectId] = None
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "ROLE_REVOKED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "role_id": self.role_id,
            "revoked_by": self.revoked_by.value if self.revoked_by else None,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SessionCreatedEvent(DomainEvent):
    """Événement émis lors de la création d'une session."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    session_id: str = ""
    ip_address: Optional[str] = None
    user_agent: str = ""
    device_type: str = "unknown"

    @property
    def event_type(self) -> str:
        return "SESSION_CREATED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "session_id": self.session_id,
            "ip_address": self._anonymize_ip(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "device_type": self.device_type,
            "occurred_at": self.occurred_at.isoformat(),
        }

    def _anonymize_ip(self, ip: str) -> str:
        """Anonymise partiellement l'adresse IP pour l'audit."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***.***.***.***"
        except Exception:
            return "***.***.***.***"


@dataclass(frozen=True, slots=True)
class SessionRevokedEvent(DomainEvent):
    """Événement émis lors de la révocation d'une session."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    session_id: str = ""
    revoked_by: Optional[SubjectId] = None
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "SESSION_REVOKED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "session_id": self.session_id,
            "revoked_by": self.revoked_by.value if self.revoked_by else None,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TenantCreatedEvent(DomainEvent):
    """Événement émis lors de la création d'un tenant."""

    tenant_id: str = ""
    tenant_name: str = ""
    tenant_level: str = ""
    parent_tenant_id: Optional[str] = None
    created_by: Optional[SubjectId] = None

    @property
    def event_type(self) -> str:
        return "TENANT_CREATED"

    @property
    def aggregate_id(self) -> str:
        return self.tenant_id

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "tenant_name": self.tenant_name,
            "tenant_level": self.tenant_level,
            "parent_tenant_id": self.parent_tenant_id,
            "created_by": self.created_by.value if self.created_by else None,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DataExportRequestedEvent(DomainEvent):
    """Événement émis lors d'une demande d'export de données (RGPD)."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    export_id: str = ""
    requested_by: Optional[SubjectId] = None
    reason: str = ""

    @property
    def event_type(self) -> str:
        return "DATA_EXPORT_REQUESTED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "export_id": self.export_id,
            "requested_by": self.requested_by.value if self.requested_by else None,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DataDeletionRequestedEvent(DomainEvent):
    """Événement émis lors d'une demande de suppression de données (Droit à l'oubli)."""

    subject_id: SubjectId = field(default=None)  # type: ignore
    requested_by: Optional[SubjectId] = None
    reason: str = ""
    anonymization_date: Optional[datetime] = None
    deletion_date: Optional[datetime] = None

    @property
    def event_type(self) -> str:
        return "DATA_DELETION_REQUESTED"

    @property
    def aggregate_id(self) -> str:
        return self.subject_id.value

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "requested_by": self.requested_by.value if self.requested_by else None,
            "reason": self.reason,
            "anonymization_date": self.anonymization_date.isoformat() if self.anonymization_date else None,
            "deletion_date": self.deletion_date.isoformat() if self.deletion_date else None,
            "occurred_at": self.occurred_at.isoformat(),
        }
