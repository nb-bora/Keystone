"""
Anti-Corruption Layer (ACL) & Data Mapper pour Aegis.

Isolement strict entre le Domain Layer (Pure Python) et l'Infrastructure Layer (ORM).
Ce pattern empêche les exceptions ORM et les dépendances d'infrastructure de contaminer le Domain.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar

from aegis.core.domain.entities import (
    AIAgentActor,
    ApiKeyActor,
    HumanIdentity,
    ServiceAccount,
    Subject,
)
from aegis.core.domain.values import EmailAddress, PermissionCode, SubjectId, TenantId


class MappingError(Exception):
    """Erreur levée lors du mapping entre ORM et Domain."""

    pass


class ORMModelNotFoundError(MappingError):
    """Erreur quand un modèle ORM n'est pas trouvé."""

    pass


class DomainEntityInvalidError(MappingError):
    """Erreur quand une entité de domaine est invalide."""

    pass


@dataclass(frozen=True, slots=True)
class SubjectData:
    """DTO de transfert de données pour les sujets (ACL)."""

    id: str
    subject_type: str
    tenant_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Champs spécifiques à HumanIdentity
    email: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    is_email_verified: bool = False

    # Champs spécifiques à ServiceAccount
    client_id: str = ""

    # Champs spécifiques à ApiKeyActor
    key_prefix: str = ""
    name: str = ""
    expires_at: Optional[datetime] = None

    # Champs spécifiques à AIAgentActor
    agent_name: str = ""
    owner_identity_id: Optional[str] = None
    max_autonomy_level: int = 1

    # Permissions et scopes
    permissions: List[str] = None  # type: ignore
    allowed_scopes: List[str] = None  # type: ignore


T = TypeVar("T", bound=Subject)


class DataMapper(ABC):
    """Interface abstraite pour les Data Mappers."""

    @abstractmethod
    def to_domain(self, orm_model: Any) -> Subject:
        """Convertit un modèle ORM en entité de domaine."""
        pass

    @abstractmethod
    def to_orm(self, domain_entity: Subject) -> Any:
        """Convertit une entité de domaine en modèle ORM."""
        pass

    @abstractmethod
    def to_data(self, orm_model: Any) -> SubjectData:
        """Convertit un modèle ORM en DTO de données."""
        pass

    @abstractmethod
    def from_data(self, data: SubjectData) -> Subject:
        """Convertit un DTO de données en entité de domaine."""
        pass


class SubjectDataMapper(DataMapper):
    """Data Mapper pour les entités Subject."""

    def to_domain(self, orm_model: Any) -> Subject:
        """Convertit un modèle ORM en entité de domaine avec gestion d'erreurs."""
        try:
            data = self.to_data(orm_model)
            return self.from_data(data)
        except Exception as e:
            raise MappingError(f"Erreur lors de la conversion ORM vers Domain: {e}") from e

    def to_orm(self, domain_entity: Subject) -> Dict[str, Any]:
        """Convertit une entité de domaine en dictionnaire ORM-safe."""
        if not isinstance(domain_entity, Subject):
            raise DomainEntityInvalidError(f"Attendu Subject, reçu {type(domain_entity)}")

        data = {
            "id": domain_entity.id.value,
            "subject_type": domain_entity.subject_type,
            "tenant_id": domain_entity.tenant_id.value if domain_entity.tenant_id else None,
            "is_active": domain_entity.is_active,
            "created_at": domain_entity.created_at,
            "updated_at": domain_entity.updated_at,
        }

        # Champs spécifiques selon le type
        if isinstance(domain_entity, HumanIdentity):
            data.update(
                {
                    "email": domain_entity.email.value if domain_entity.email else None,
                    "first_name": domain_entity.first_name,
                    "last_name": domain_entity.last_name,
                    "is_email_verified": domain_entity.is_email_verified,
                    "permissions": [p.value for p in domain_entity.permissions],
                }
            )

        elif isinstance(domain_entity, ServiceAccount):
            data.update(
                {
                    "client_id": domain_entity.client_id,
                    "allowed_scopes": list(domain_entity.allowed_scopes),
                }
            )

        elif isinstance(domain_entity, ApiKeyActor):
            data.update(
                {
                    "key_prefix": domain_entity.key_prefix,
                    "key_name": domain_entity.name,  # Mapping vers key_name pour éviter conflit SQL
                    "expires_at": domain_entity.expires_at,
                    "permissions": [p.value for p in domain_entity.permissions],
                }
            )

        elif isinstance(domain_entity, AIAgentActor):
            data.update(
                {
                    "agent_name": domain_entity.agent_name,
                    "owner_identity_id": domain_entity.owner_identity_id.value
                    if domain_entity.owner_identity_id
                    else None,
                    "max_autonomy_level": domain_entity.max_autonomy_level,
                    "permissions": [p.value for p in domain_entity.permissions],
                }
            )

        return data

    def to_data(self, orm_model: Any) -> SubjectData:
        """Convertit un modèle ORM en DTO de données."""
        try:
            # Extraction sécurisée des attributs avec gestion des attributs manquants
            subject_id = getattr(orm_model, "id", None)
            if not subject_id:
                raise ORMModelNotFoundError("L'ORM model n'a pas d'attribut 'id'")

            subject_type = getattr(orm_model, "subject_type", "UNKNOWN")
            tenant_id = getattr(orm_model, "tenant_id", None)
            is_active = getattr(orm_model, "is_active", True)
            created_at = getattr(orm_model, "created_at", datetime.now(timezone.utc))
            updated_at = getattr(orm_model, "updated_at", datetime.now(timezone.utc))

            # Champs communs avec valeurs par défaut
            email = getattr(orm_model, "email", None)
            first_name = getattr(orm_model, "first_name", "")
            last_name = getattr(orm_model, "last_name", "")
            is_email_verified = getattr(orm_model, "is_email_verified", False)

            client_id = getattr(orm_model, "client_id", "")
            key_prefix = getattr(orm_model, "key_prefix", "")
            name = getattr(orm_model, "key_name", getattr(orm_model, "name", ""))  # Support des deux conventions
            expires_at = getattr(orm_model, "expires_at", None)

            agent_name = getattr(orm_model, "agent_name", "")
            owner_identity_id = getattr(orm_model, "owner_identity_id", None)
            max_autonomy_level = getattr(orm_model, "max_autonomy_level", 1)

            # Permissions et scopes
            permissions = getattr(orm_model, "permissions", [])
            allowed_scopes = getattr(orm_model, "allowed_scopes", [])

            return SubjectData(
                id=str(subject_id),
                subject_type=subject_type,
                tenant_id=str(tenant_id) if tenant_id else None,
                is_active=bool(is_active),
                created_at=created_at if isinstance(created_at, datetime) else datetime.now(timezone.utc),
                updated_at=updated_at if isinstance(updated_at, datetime) else datetime.now(timezone.utc),
                email=email,
                first_name=str(first_name),
                last_name=str(last_name),
                is_email_verified=bool(is_email_verified),
                client_id=str(client_id),
                key_prefix=str(key_prefix),
                name=str(name),
                expires_at=expires_at if isinstance(expires_at, datetime) else None,
                agent_name=str(agent_name),
                owner_identity_id=str(owner_identity_id) if owner_identity_id else None,
                max_autonomy_level=int(max_autonomy_level),
                permissions=list(permissions) if permissions else [],
                allowed_scopes=list(allowed_scopes) if allowed_scopes else [],
            )

        except Exception as e:
            raise MappingError(f"Erreur lors de l'extraction des données ORM: {e}") from e

    def from_data(self, data: SubjectData) -> Subject:
        """Convertit un DTO de données en entité de domaine avec validation."""
        try:
            subject_id = SubjectId(data.id)
            tenant_id = TenantId(data.tenant_id) if data.tenant_id else None

            # Construction selon le type
            if data.subject_type == "HUMAN":
                email = EmailAddress(data.email) if data.email else None
                permissions = {PermissionCode(p) for p in (data.permissions or [])}

                return HumanIdentity(
                    id=subject_id,
                    tenant_id=tenant_id,
                    is_active=data.is_active,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    email=email,
                    first_name=data.first_name,
                    last_name=data.last_name,
                    is_email_verified=data.is_email_verified,
                    permissions=permissions,
                )

            elif data.subject_type == "SERVICE_ACCOUNT":
                allowed_scopes = set(data.allowed_scopes or [])

                return ServiceAccount(
                    id=subject_id,
                    tenant_id=tenant_id,
                    is_active=data.is_active,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    client_id=data.client_id,
                    allowed_scopes=allowed_scopes,
                )

            elif data.subject_type == "API_KEY":
                permissions = {PermissionCode(p) for p in (data.permissions or [])}

                return ApiKeyActor(
                    id=subject_id,
                    tenant_id=tenant_id,
                    is_active=data.is_active,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    key_prefix=data.key_prefix,
                    name=data.name,
                    expires_at=data.expires_at,
                    permissions=permissions,
                )

            elif data.subject_type == "AI_AGENT":
                permissions = {PermissionCode(p) for p in (data.permissions or [])}
                owner_id = SubjectId(data.owner_identity_id) if data.owner_identity_id else None

                return AIAgentActor(
                    id=subject_id,
                    tenant_id=tenant_id,
                    is_active=data.is_active,
                    created_at=data.created_at,
                    updated_at=data.updated_at,
                    agent_name=data.agent_name,
                    owner_identity_id=owner_id,
                    max_autonomy_level=data.max_autonomy_level,
                    permissions=permissions,
                )

            else:
                raise DomainEntityInvalidError(f"Type de sujet inconnu: {data.subject_type}")

        except Exception as e:
            raise MappingError(f"Erreur lors de la construction de l'entité de domaine: {e}") from e


class UnitOfWork(ABC):
    """Pattern Unit of Work pour gérer les transactions de manière cohérente."""

    @abstractmethod
    def begin(self) -> None:
        """Démarre une nouvelle transaction."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Valide la transaction en cours."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Annule la transaction en cours."""
        pass

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        """Context manager entry."""
        pass

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit avec gestion automatique des exceptions."""
        pass


class RepositoryWithMapper(ABC):
    """Repository avec Data Mapper intégré."""

    def __init__(self, data_mapper: DataMapper) -> None:
        self._data_mapper = data_mapper

    @abstractmethod
    def get_by_id(self, subject_id: SubjectId) -> Optional[Subject]:
        """Récupère un sujet par son ID avec mapping automatique."""
        pass

    @abstractmethod
    def save(self, subject: Subject) -> None:
        """Sauvegarde un sujet avec mapping automatique."""
        pass

    @abstractmethod
    def delete(self, subject_id: SubjectId) -> bool:
        """Supprime un sujet par son ID."""
        pass


class TransactionBoundary:
    """Gestionnaire de frontière de transaction pour les Use Cases."""

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._uow = unit_of_work

    def execute(self, operation) -> Any:
        """Exécute une opération dans une transaction avec gestion d'erreurs."""
        try:
            self._uow.begin()
            result = operation()
            self._uow.commit()
            return result
        except Exception as e:
            try:
                self._uow.rollback()
            except Exception:
                # Log l'erreur de rollback mais propage l'erreur originale
                pass
            raise e


# Factory pour créer les mappers appropriés
class MapperFactory:
    """Factory pour créer les instances de Data Mapper."""

    @staticmethod
    def create_subject_mapper() -> SubjectDataMapper:
        """Crée un mapper pour les sujets."""
        return SubjectDataMapper()

    @staticmethod
    def create_mapper_for_type(entity_type: Type[Subject]) -> DataMapper:
        """Crée un mapper approprié selon le type d'entité."""
        # Pour l'instant, un seul mapper gère tous les types
        return SubjectDataMapper()
