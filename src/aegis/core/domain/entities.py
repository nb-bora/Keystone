"""
Entities & Aggregates du Domaine Aegis.

Modélise le Modèle d'Acteur Universel (Subject) et ses déclinaisons:
- HumanIdentity (Êtres humains avec PII)
- ServiceAccount (Microservices M2M)
- ApiKeyActor (Acteurs programmatiques avec clé API)
- AIAgentActor (Agents IA autonomes ou supervisés)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Set

from aegis.core.domain.values import EmailAddress, PermissionCode, SubjectId, TenantId


@dataclass(slots=True)
class Subject(ABC):
    """Racine d'Aggregate d'Acteur Universel (Subject).

    Modélise tout entité ou système capable d'exécuter des actions ou de demander
    des accès dans le système.
    """

    id: SubjectId
    tenant_id: Optional[TenantId] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    @abstractmethod
    def subject_type(self) -> str:
        """Retourne le type discriminant de l'acteur.

        Valeurs possibles: 'HUMAN', 'SERVICE_ACCOUNT', 'API_KEY', 'AI_AGENT'.
        """
        pass

    def suspend(self) -> None:
        """Suspend l'accès de l'acteur en O(1)."""
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        """Réactive l'accès de l'acteur en O(1)."""
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class HumanIdentity(Subject):
    """Aggregate Root d'une Identité Humaine.

    Complexité Spatiale: O(P) où P est le nombre de permissions directes assignées.
    """

    email: Optional[EmailAddress] = None
    first_name: str = ""
    last_name: str = ""
    is_email_verified: bool = False
    permissions: Set[PermissionCode] = field(default_factory=set)

    @property
    def subject_type(self) -> str:
        return "HUMAN"

    def grant_permission(self, permission: PermissionCode) -> None:
        """Ajoute une permission directe en O(1)."""
        self.permissions.add(permission)
        self.updated_at = datetime.now(timezone.utc)

    def revoke_permission(self, permission: PermissionCode) -> None:
        """Révoque une permission directe en O(1)."""
        self.permissions.discard(permission)
        self.updated_at = datetime.now(timezone.utc)

    def has_direct_permission(self, permission: PermissionCode) -> bool:
        """Vérifie si la permission est directement assignée en O(1)."""
        return permission in self.permissions


@dataclass(slots=True)
class ServiceAccount(Subject):
    """Acteur Machine-to-Machine (M2M / Microservice).

    Complexité Spatiale: O(S) où S est le nombre de scopes autorisés.
    """

    client_id: str = ""
    allowed_scopes: Set[str] = field(default_factory=set)

    @property
    def subject_type(self) -> str:
        return "SERVICE_ACCOUNT"

    def grant_scope(self, scope: str) -> None:
        """Accorde un scope M2M en O(1)."""
        self.allowed_scopes.add(scope)
        self.updated_at = datetime.now(timezone.utc)

    def has_scope(self, scope: str) -> bool:
        """Vérifie si un scope est autorisé en O(1)."""
        return scope in self.allowed_scopes


@dataclass(slots=True)
class ApiKeyActor(Subject):
    """Acteur d'accès programmatique via Clé API."""

    key_prefix: str = ""
    name: str = ""
    permissions: Set[PermissionCode] = field(default_factory=set)
    expires_at: Optional[datetime] = None

    @property
    def subject_type(self) -> str:
        return "API_KEY"

    def is_expired(self) -> bool:
        """Vérifie si la clé API a expiré en O(1)."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass(slots=True)
class AIAgentActor(Subject):
    """Acteur Agent IA autonome ou supervisé."""

    agent_name: str = ""
    owner_identity_id: Optional[SubjectId] = None
    max_autonomy_level: int = 1  # 1: Supervisé, 2: Semi-autonome, 3: Totalement autonome
    permissions: Set[PermissionCode] = field(default_factory=set)

    @property
    def subject_type(self) -> str:
        return "AI_AGENT"
