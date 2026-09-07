"""
Système de Multi-Tenancy avec Isolation et Hiérarchie pour Aegis.

Supporte différents modes d'isolation (flat, single, hierarchical) et la gestion
des hiérarchies d'organisation (Enterprise -> Organization -> Workspace -> Project).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from aegis.core.domain.values import SubjectId, TenantId


class TenancyMode(str, Enum):
    """Modes de multi-tenancy supportés."""

    FLAT = "flat"  # Un seul niveau de tenants
    SINGLE = "single"  # Un seul tenant (mono-tenant)
    HIERARCHICAL = "hierarchical"  # Hiérarchie multi-niveaux


class IsolationType(str, Enum):
    """Types d'isolation de données."""

    ROW_LEVEL = "row_level"  # Isolation au niveau des lignes (tenant_id)
    DATABASE = "database"  # Base de données séparée par tenant
    SCHEMA = "schema"  # Schéma séparé par tenant


class TenantLevel(str, Enum):
    """Niveaux de hiérarchie de tenants."""

    ENTERPRISE = "enterprise"
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class Tenant:
    """Tenant (organisation/entreprise) avec métadonnées."""

    id: TenantId
    name: str
    description: str = ""
    parent_tenant_id: Optional[TenantId] = None  # Pour hiérarchie
    level: TenantLevel = TenantLevel.ORGANIZATION
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_path(self) -> str:
        """Retourne le chemin hiérarchique du tenant."""
        return f"{self.level.value}/{self.id.value}"

    def is_root(self) -> bool:
        """Vérifie si c'est un tenant racine (sans parent)."""
        return self.parent_tenant_id is None


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Contexte de tenant pour propagation dans les use cases."""

    tenant_id: TenantId
    isolation_type: IsolationType = IsolationType.ROW_LEVEL
    tenant_path: Optional[str] = None  # Chemin hiérarchique complet
    user_permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_access_tenant(self, target_tenant_id: TenantId) -> bool:
        """Vérifie si le contexte peut accéder à un tenant cible."""
        # En mode row_level, vérifier l'appartenance à la hiérarchie
        if self.isolation_type == IsolationType.ROW_LEVEL:
            return self._is_in_hierarchy(target_tenant_id)

        # En mode database/schema, accès seulement si même tenant
        return self.tenant_id == target_tenant_id

    def _is_in_hierarchy(self, target_tenant_id: TenantId) -> bool:
        """Vérifie si le tenant cible est dans la hiérarchie du tenant actuel."""
        # Pour l'instant, simple égalité - à améliorer avec résolution de hiérarchie
        return self.tenant_id == target_tenant_id


class TenantRepository(ABC):
    """Interface de repository pour les tenants."""

    @abstractmethod
    def get_by_id(self, tenant_id: TenantId) -> Optional[Tenant]:
        """Récupère un tenant par son ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Tenant]:
        """Récupère un tenant par son nom."""
        pass

    @abstractmethod
    def save(self, tenant: Tenant) -> None:
        """Sauvegarde un tenant."""
        pass

    @abstractmethod
    def delete(self, tenant_id: TenantId) -> bool:
        """Supprime un tenant."""
        pass

    @abstractmethod
    def list_children(self, parent_tenant_id: TenantId) -> List[Tenant]:
        """Liste les tenants enfants d'un parent."""
        pass

    @abstractmethod
    def get_hierarchy_path(self, tenant_id: TenantId) -> List[Tenant]:
        """Récupère le chemin hiérarchique complet d'un tenant."""
        pass

    @abstractmethod
    def list_all(self, include_inactive: bool = False) -> List[Tenant]:
        """Liste tous les tenants."""
        pass


class TenantIsolationPolicy:
    """Politique d'isolation des tenants."""

    def __init__(
        self, mode: TenancyMode = TenancyMode.FLAT, isolation_type: IsolationType = IsolationType.ROW_LEVEL
    ) -> None:
        self._mode = mode
        self._isolation_type = isolation_type

    @property
    def mode(self) -> TenancyMode:
        return self._mode

    @property
    def isolation_type(self) -> IsolationType:
        return self._isolation_type

    def apply_isolation_filter(self, query: Any, tenant_context: TenantContext) -> Any:
        """Applique le filtre d'isolation à une requête."""
        if self._mode == TenancyMode.SINGLE:
            return query  # Pas de filtrage en mode mono-tenant

        if self._isolation_type == IsolationType.ROW_LEVEL:
            # Ajouter filtre tenant_id
            return self._apply_row_level_filter(query, tenant_context)

        return query

    def _apply_row_level_filter(self, query: Any, tenant_context: TenantContext) -> Any:
        """Applique le filtre au niveau des lignes."""
        # Cette méthode serait implémentée spécifiquement selon l'ORM
        # Pour SQLAlchemy: query = query.filter(TenantORM.tenant_id == tenant_context.tenant_id)
        return query

    def validate_cross_tenant_access(self, source_tenant_id: TenantId, target_tenant_id: TenantId) -> bool:
        """Valide l'accès cross-tenant."""
        if self._mode == TenancyMode.SINGLE:
            return True  # Pas de restriction en mono-tenant

        if source_tenant_id == target_tenant_id:
            return True  # Même tenant

        # Pour l'isolation row_level, vérifier la hiérarchie
        if self._isolation_type == IsolationType.ROW_LEVEL:
            return self._check_hierarchy_access(source_tenant_id, target_tenant_id)

        return False  # Isolation stricte par défaut

    def _check_hierarchy_access(self, source_tenant_id: TenantId, target_tenant_id: TenantId) -> bool:
        """Vérifie l'accès hiérarchique entre tenants."""
        # Implémentation simplifiée - à améliorer avec résolution de hiérarchie réelle
        return source_tenant_id == target_tenant_id


class TenantService:
    """Service de gestion des tenants avec logique métier."""

    def __init__(
        self, tenant_repository: TenantRepository, isolation_policy: Optional[TenantIsolationPolicy] = None
    ) -> None:
        self._tenant_repository = tenant_repository
        self._isolation_policy = isolation_policy or TenantIsolationPolicy()

    def create_tenant(self, tenant: Tenant) -> Tenant:
        """Crée un nouveau tenant."""
        # Vérifier que le nom est unique
        existing = self._tenant_repository.get_by_name(tenant.name)
        if existing is not None:
            raise ValueError(f"Un tenant avec le nom '{tenant.name}' existe déjà.")

        # Vérifier le parent existe si spécifié
        if tenant.parent_tenant_id is not None:
            parent = self._tenant_repository.get_by_id(tenant.parent_tenant_id)
            if parent is None:
                raise ValueError(f"Le tenant parent '{tenant.parent_tenant_id}' n'existe pas.")

            # Vérifier la cohérence des niveaux
            if not self._is_valid_hierarchy_level(parent.level, tenant.level):
                raise ValueError(f"Niveau de hiérarchie invalide: {parent.level} -> {tenant.level}")

        self._tenant_repository.save(tenant)
        return tenant

    def _is_valid_hierarchy_level(self, parent_level: TenantLevel, child_level: TenantLevel) -> bool:
        """Vérifie la cohérence des niveaux de hiérarchie."""
        level_order = [TenantLevel.ENTERPRISE, TenantLevel.ORGANIZATION, TenantLevel.WORKSPACE, TenantLevel.PROJECT]

        try:
            parent_index = level_order.index(parent_level)
            child_index = level_order.index(child_level)
            return child_index == parent_index + 1
        except ValueError:
            return False

    def update_tenant(self, tenant: Tenant) -> Tenant:
        """Met à jour un tenant existant."""
        existing = self._tenant_repository.get_by_id(tenant.id)
        if existing is None:
            raise ValueError(f"Le tenant '{tenant.id}' n'existe pas.")

        # Vérifier que le nouveau nom est unique (si changé)
        if tenant.name != existing.name:
            name_existing = self._tenant_repository.get_by_name(tenant.name)
            if name_existing is not None:
                raise ValueError(f"Un tenant avec le nom '{tenant.name}' existe déjà.")

        # Vérifier le parent existe si changé
        if tenant.parent_tenant_id != existing.parent_tenant_id:
            if tenant.parent_tenant_id is not None:
                parent = self._tenant_repository.get_by_id(tenant.parent_tenant_id)
                if parent is None:
                    raise ValueError(f"Le tenant parent '{tenant.parent_tenant_id}' n'existe pas.")

        self._tenant_repository.save(tenant)
        return tenant

    def delete_tenant(self, tenant_id: TenantId) -> bool:
        """Supprime un tenant."""
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            return False

        # Vérifier qu'il n'y a pas de tenants enfants
        children = self._tenant_repository.list_children(tenant_id)
        if children:
            raise ValueError(f"Le tenant '{tenant_id}' a {len(children)} tenants enfants.")

        return self._tenant_repository.delete(tenant_id)

    def get_tenant_hierarchy(self, tenant_id: TenantId) -> List[Tenant]:
        """Récupère la hiérarchie complète d'un tenant."""
        return self._tenant_repository.get_hierarchy_path(tenant_id)

    def get_tenant_children(self, tenant_id: TenantId) -> List[Tenant]:
        """Récupère les tenants directs d'un parent."""
        return self._tenant_repository.list_children(tenant_id)

    def create_tenant_context(self, tenant_id: TenantId, subject_id: Optional[SubjectId] = None) -> TenantContext:
        """Crée un contexte de tenant pour un sujet."""
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError(f"Le tenant '{tenant_id}' n'existe pas.")

        hierarchy_path = self._build_tenant_path(tenant)

        return TenantContext(
            tenant_id=tenant_id, isolation_type=self._isolation_policy.isolation_type, tenant_path=hierarchy_path
        )

    def _build_tenant_path(self, tenant: Tenant) -> str:
        """Construit le chemin hiérarchique d'un tenant."""
        hierarchy = self._tenant_repository.get_hierarchy_path(tenant.id)
        path_parts = [t.level.value + ":" + t.id.value for t in hierarchy]
        return "/".join(path_parts)

    def validate_access(self, subject_id: SubjectId, target_tenant_id: TenantId) -> bool:
        """Valide l'accès d'un sujet à un tenant."""
        # Récupérer le tenant du sujet (à implémenter avec repository de sujets)
        # Pour l'instant, simplification
        subject_tenant_id = self._get_subject_tenant(subject_id)

        if subject_tenant_id is None:
            return False

        return self._isolation_policy.validate_cross_tenant_access(subject_tenant_id, target_tenant_id)

    def _get_subject_tenant(self, subject_id: SubjectId) -> Optional[TenantId]:
        """Récupère le tenant d'un sujet (à implémenter)."""
        # Cette méthode nécessiterait l'accès au repository de sujets
        # Pour l'instant, retourne None
        return None


class TenantHierarchyBuilder:
    """Builder pour construire des hiérarchies de tenants."""

    @staticmethod
    def build_enterprise_structure(
        service: TenantService, enterprise_name: str, organizations: List[str]
    ) -> Dict[str, TenantId]:
        """Construit une structure d'entreprise avec organisations."""
        # Créer l'enterprise
        enterprise = Tenant(
            id=TenantId(f"ent-{enterprise_name.lower()}"), name=enterprise_name, level=TenantLevel.ENTERPRISE
        )
        enterprise = service.create_tenant(enterprise)

        result = {"enterprise": enterprise.id}

        # Créer les organisations
        for i, org_name in enumerate(organizations):
            org = Tenant(
                id=TenantId(f"org-{org_name.lower()}"),
                name=org_name,
                parent_tenant_id=enterprise.id,
                level=TenantLevel.ORGANIZATION,
            )
            org = service.create_tenant(org)
            result[f"organization_{i}"] = org.id

        return result

    @staticmethod
    def build_workspace_structure(
        service: TenantService, parent_tenant_id: TenantId, workspace_names: List[str]
    ) -> List[TenantId]:
        """Construit des workspaces sous un parent."""
        workspace_ids = []

        for workspace_name in workspace_names:
            workspace = Tenant(
                id=TenantId(f"ws-{workspace_name.lower()}"),
                name=workspace_name,
                parent_tenant_id=parent_tenant_id,
                level=TenantLevel.WORKSPACE,
            )
            workspace = service.create_tenant(workspace)
            workspace_ids.append(workspace.id)

        return workspace_ids

    @staticmethod
    def build_project_structure(
        service: TenantService, parent_tenant_id: TenantId, project_names: List[str]
    ) -> List[TenantId]:
        """Construit des projets sous un parent."""
        project_ids = []

        for project_name in project_names:
            project = Tenant(
                id=TenantId(f"proj-{project_name.lower()}"),
                name=project_name,
                parent_tenant_id=parent_tenant_id,
                level=TenantLevel.PROJECT,
            )
            project = service.create_tenant(project)
            project_ids.append(project.id)

        return project_ids
