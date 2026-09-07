"""
Système de Rôles avec Héritage et Permissions pour Aegis.

Permet la gestion hiérarchique des rôles avec héritage de permissions,
facilitant la gestion des autorisations complexes à grande échelle.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from aegis.core.domain.values import PermissionCode, RoleId, SubjectId, TenantId


class RoleHierarchyError(Exception):
    """Erreur levée lors de conflits dans la hiérarchie de rôles."""

    pass


@dataclass(frozen=True, slots=True)
class Role:
    """Rôle avec permissions et métadonnées."""

    id: RoleId
    name: str
    description: str = ""
    permissions: Set[PermissionCode] = field(default_factory=set)
    parent_role_ids: Set[RoleId] = field(default_factory=set)  # Héritage
    tenant_id: Optional[TenantId] = None
    is_system_role: bool = False  # Rôle système non modifiable
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: PermissionCode) -> bool:
        """Vérifie si le rôle a une permission directe."""
        return permission in self.permissions

    def add_permission(self, permission: PermissionCode) -> "Role":
        """Ajoute une permission au rôle."""
        new_permissions = self.permissions | {permission}
        return Role(
            id=self.id,
            name=self.name,
            description=self.description,
            permissions=new_permissions,
            parent_role_ids=self.parent_role_ids,
            tenant_id=self.tenant_id,
            is_system_role=self.is_system_role,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def remove_permission(self, permission: PermissionCode) -> "Role":
        """Supprime une permission du rôle."""
        new_permissions = self.permissions - {permission}
        return Role(
            id=self.id,
            name=self.name,
            description=self.description,
            permissions=new_permissions,
            parent_role_ids=self.parent_role_ids,
            tenant_id=self.tenant_id,
            is_system_role=self.is_system_role,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def add_parent_role(self, parent_role_id: RoleId) -> "Role":
        """Ajoute un rôle parent pour l'héritage."""
        new_parents = self.parent_role_ids | {parent_role_id}
        return Role(
            id=self.id,
            name=self.name,
            description=self.description,
            permissions=self.permissions,
            parent_role_ids=new_parents,
            tenant_id=self.tenant_id,
            is_system_role=self.is_system_role,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def remove_parent_role(self, parent_role_id: RoleId) -> "Role":
        """Supprime un rôle parent."""
        new_parents = self.parent_role_ids - {parent_role_id}
        return Role(
            id=self.id,
            name=self.name,
            description=self.description,
            permissions=self.permissions,
            parent_role_ids=new_parents,
            tenant_id=self.tenant_id,
            is_system_role=self.is_system_role,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    """Assignation d'un rôle à un sujet."""

    subject_id: SubjectId
    role_id: RoleId
    tenant_id: Optional[TenantId] = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    assigned_by: Optional[SubjectId] = None  # Qui a fait l'assignation
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Vérifie si l'assignation a expiré."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        """Vérifie si l'assignation est valide (non expirée)."""
        return not self.is_expired()


class RoleRepository(ABC):
    """Interface de repository pour les rôles."""

    @abstractmethod
    def get_by_id(self, role_id: RoleId) -> Optional[Role]:
        """Récupère un rôle par son ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: str, tenant_id: Optional[TenantId] = None) -> Optional[Role]:
        """Récupère un rôle par son nom."""
        pass

    @abstractmethod
    def save(self, role: Role) -> None:
        """Sauvegarde un rôle."""
        pass

    @abstractmethod
    def delete(self, role_id: RoleId) -> bool:
        """Supprime un rôle."""
        pass

    @abstractmethod
    def list_all(self, tenant_id: Optional[TenantId] = None) -> List[Role]:
        """Liste tous les rôles."""
        pass

    @abstractmethod
    def get_system_roles(self) -> List[Role]:
        """Récupère les rôles système."""
        pass


class RoleAssignmentRepository(ABC):
    """Interface de repository pour les assignations de rôles."""

    @abstractmethod
    def assign_role(self, assignment: RoleAssignment) -> None:
        """Assigne un rôle à un sujet."""
        pass

    @abstractmethod
    def remove_assignment(self, subject_id: SubjectId, role_id: RoleId) -> bool:
        """Supprime une assignation de rôle."""
        pass

    @abstractmethod
    def get_subject_roles(self, subject_id: SubjectId, include_expired: bool = False) -> List[RoleAssignment]:
        """Récupère les rôles assignés à un sujet."""
        pass

    @abstractmethod
    def get_role_subjects(self, role_id: RoleId, include_expired: bool = False) -> List[RoleAssignment]:
        """Récupère les sujets ayant un rôle."""
        pass

    @abstractmethod
    def has_role(self, subject_id: SubjectId, role_id: RoleId) -> bool:
        """Vérifie si un sujet a un rôle spécifique."""
        pass


class RoleHierarchyResolver:
    """Résolveur de hiérarchie de rôles avec détection de cycles."""

    def __init__(self, role_repository: RoleRepository):
        self._role_repository = role_repository
        self._cache: Dict[RoleId, Set[PermissionCode]] = {}

    def get_effective_permissions(self, role: Role) -> Set[PermissionCode]:
        """Récupère les permissions effectives d'un rôle avec héritage."""
        if role.id in self._cache:
            return self._cache[role.id]

        permissions = set(role.permissions)
        visited: Set[RoleId] = set()
        self._collect_parent_permissions(role.id, permissions, visited)

        self._cache[role.id] = permissions
        return permissions

    def _collect_parent_permissions(
        self, role_id: RoleId, permissions: Set[PermissionCode], visited: Set[RoleId]
    ) -> None:
        """Collecte récursivement les permissions des rôles parents."""
        if role_id in visited:
            return  # Éviter les cycles

        visited.add(role_id)
        role = self._role_repository.get_by_id(role_id)

        if role is None:
            return

        # Ajouter les permissions du parent
        permissions.update(role.permissions)

        # Récursion sur les parents
        for parent_id in role.parent_role_ids:
            self._collect_parent_permissions(parent_id, permissions, visited)

    def check_hierarchy_cycles(self) -> List[RoleId]:
        """Détecte les cycles dans la hiérarchie de rôles."""
        cycles = []
        visited = set()
        recursion_stack = set()

        def visit(role_id: RoleId) -> bool:
            if role_id in recursion_stack:
                return True  # Cycle détecté
            if role_id in visited:
                return False

            visited.add(role_id)
            recursion_stack.add(role_id)

            role = self._role_repository.get_by_id(role_id)
            if role:
                for parent_id in role.parent_role_ids:
                    if visit(parent_id):
                        cycles.append(role_id)

            recursion_stack.remove(role_id)
            return False

        all_roles = self._role_repository.list_all()
        for role in all_roles:
            if role.id not in visited:
                visit(role.id)

        return cycles

    def clear_cache(self) -> None:
        """Vide le cache de permissions."""
        self._cache.clear()


class RoleService:
    """Service de gestion des rôles avec logique métier."""

    def __init__(self, role_repository: RoleRepository, assignment_repository: RoleAssignmentRepository) -> None:
        self._role_repository = role_repository
        self._assignment_repository = assignment_repository
        self._hierarchy_resolver = RoleHierarchyResolver(role_repository)

    def create_role(self, role: Role) -> Role:
        """Crée un nouveau rôle."""
        # Vérifier que le nom est unique dans le tenant
        existing = self._role_repository.get_by_name(role.name, role.tenant_id)
        if existing is not None:
            raise ValueError(f"Un rôle avec le nom '{role.name}' existe déjà.")

        # Vérifier les parents existent
        for parent_id in role.parent_role_ids:
            parent = self._role_repository.get_by_id(parent_id)
            if parent is None:
                raise ValueError(f"Le rôle parent '{parent_id}' n'existe pas.")

        self._role_repository.save(role)
        self._hierarchy_resolver.clear_cache()
        return role

    def update_role(self, role: Role) -> Role:
        """Met à jour un rôle existant."""
        existing = self._role_repository.get_by_id(role.id)
        if existing is None:
            raise ValueError(f"Le rôle '{role.id}' n'existe pas.")

        # Empêcher la modification des rôles système
        if existing.is_system_role:
            raise ValueError(f"Le rôle système '{role.id}' ne peut pas être modifié.")

        # Vérifier les parents existent
        for parent_id in role.parent_role_ids:
            parent = self._role_repository.get_by_id(parent_id)
            if parent is None:
                raise ValueError(f"Le rôle parent '{parent_id}' n'existe pas.")

        # Vérifier les cycles
        self._role_repository.save(role)  # Sauvegarde temporaire pour vérifier les cycles
        cycles = self._hierarchy_resolver.check_hierarchy_cycles()
        if cycles:
            # Restaurer l'ancien rôle
            self._role_repository.save(existing)
            raise RoleHierarchyError(f"Cycle détecté dans la hiérarchie: {cycles}")

        self._role_repository.save(role)
        self._hierarchy_resolver.clear_cache()
        return role

    def delete_role(self, role_id: RoleId) -> bool:
        """Supprime un rôle."""
        role = self._role_repository.get_by_id(role_id)
        if role is None:
            return False

        # Empêcher la suppression des rôles système
        if role.is_system_role:
            raise ValueError(f"Le rôle système '{role_id}' ne peut pas être supprimé.")

        # Vérifier que le rôle n'est pas utilisé
        assignments = self._assignment_repository.get_role_subjects(role_id)
        if assignments:
            raise ValueError(f"Le rôle '{role_id}' est encore assigné à {len(assignments)} sujets.")

        # Vérifier que le rôle n'est pas parent d'autres rôles
        all_roles = self._role_repository.list_all()
        child_roles = [r for r in all_roles if role_id in r.parent_role_ids]
        if child_roles:
            raise ValueError(f"Le rôle '{role_id}' est parent de {len(child_roles)} autres rôles.")

        return self._role_repository.delete(role_id)

    def assign_role_to_subject(
        self,
        subject_id: SubjectId,
        role_id: RoleId,
        assigned_by: Optional[SubjectId] = None,
        expires_at: Optional[datetime] = None,
    ) -> RoleAssignment:
        """Assigne un rôle à un sujet."""
        role = self._role_repository.get_by_id(role_id)
        if role is None:
            raise ValueError(f"Le rôle '{role_id}' n'existe pas.")

        assignment = RoleAssignment(
            subject_id=subject_id,
            role_id=role_id,
            tenant_id=role.tenant_id,
            assigned_by=assigned_by,
            expires_at=expires_at,
        )

        self._assignment_repository.assign_role(assignment)
        return assignment

    def remove_role_from_subject(self, subject_id: SubjectId, role_id: RoleId) -> bool:
        """Supprime l'assignation d'un rôle à un sujet."""
        return self._assignment_repository.remove_assignment(subject_id, role_id)

    def get_subject_permissions(self, subject_id: SubjectId) -> Set[PermissionCode]:
        """Récupère toutes les permissions d'un sujet via ses rôles."""
        assignments = self._assignment_repository.get_subject_roles(subject_id)
        permissions = set()

        for assignment in assignments:
            if not assignment.is_valid():
                continue

            role = self._role_repository.get_by_id(assignment.role_id)
            if role:
                # Inclure les permissions effectives avec héritage
                effective_permissions = self._hierarchy_resolver.get_effective_permissions(role)
                permissions.update(effective_permissions)

        return permissions

    def subject_has_permission(self, subject_id: SubjectId, permission: PermissionCode) -> bool:
        """Vérifie si un sujet a une permission via ses rôles."""
        permissions = self.get_subject_permissions(subject_id)
        return permission in permissions

    def get_subject_roles_info(self, subject_id: SubjectId) -> List[Dict[str, Any]]:
        """Récupère les informations détaillées des rôles d'un sujet."""
        assignments = self._assignment_repository.get_subject_roles(subject_id)
        roles_info = []

        for assignment in assignments:
            role = self._role_repository.get_by_id(assignment.role_id)
            if role:
                effective_permissions = self._hierarchy_resolver.get_effective_permissions(role)
                roles_info.append(
                    {
                        "role_id": role.id.value,
                        "role_name": role.name,
                        "role_description": role.description,
                        "direct_permissions": [p.value for p in role.permissions],
                        "effective_permissions": [p.value for p in effective_permissions],
                        "assigned_at": assignment.assigned_at.isoformat(),
                        "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
                        "is_valid": assignment.is_valid(),
                    }
                )

        return roles_info


# Factory pour créer des rôles système prédéfinis
class SystemRolesFactory:
    """Factory pour créer les rôles système standards."""

    @staticmethod
    def create_super_admin_role() -> Role:
        """Crée le rôle super-admin avec toutes les permissions."""
        return Role(
            id=RoleId("super_admin"),
            name="Super Administrator",
            description="Accès complet à toutes les fonctionnalités",
            permissions={PermissionCode("*")},  # Wildcard pour toutes les permissions
            is_system_role=True,
        )

    @staticmethod
    def create_admin_role() -> Role:
        """Crée le rôle administrateur."""
        return Role(
            id=RoleId("admin"),
            name="Administrator",
            description="Accès administratif standard",
            permissions={
                PermissionCode("user:read"),
                PermissionCode("user:write"),
                PermissionCode("user:delete"),
                PermissionCode("role:read"),
                PermissionCode("role:write"),
                PermissionCode("audit:read"),
                PermissionCode("settings:read"),
                PermissionCode("settings:write"),
            },
            is_system_role=True,
        )

    @staticmethod
    def create_moderator_role() -> Role:
        """Crée le rôle modérateur."""
        return Role(
            id=RoleId("moderator"),
            name="Moderator",
            description="Accès de modération de contenu",
            permissions={
                PermissionCode("content:read"),
                PermissionCode("content:write"),
                PermissionCode("content:moderate"),
                PermissionCode("user:read"),
                PermissionCode("report:read"),
                PermissionCode("report:process"),
            },
            is_system_role=True,
        )

    @staticmethod
    def create_editor_role() -> Role:
        """Crée le rôle éditeur."""
        return Role(
            id=RoleId("editor"),
            name="Editor",
            description="Accès d'édition de contenu",
            permissions={
                PermissionCode("content:read"),
                PermissionCode("content:write"),
                PermissionCode("media:read"),
                PermissionCode("media:upload"),
            },
            is_system_role=True,
        )

    @staticmethod
    def create_viewer_role() -> Role:
        """Crée le rôle lecteur."""
        return Role(
            id=RoleId("viewer"),
            name="Viewer",
            description="Accès en lecture seule",
            permissions={"content:read", "media:read"},
            is_system_role=True,
        )

    @staticmethod
    def create_all_system_roles() -> List[Role]:
        """Crée tous les rôles système standards."""
        return [
            SystemRolesFactory.create_super_admin_role(),
            SystemRolesFactory.create_admin_role(),
            SystemRolesFactory.create_moderator_role(),
            SystemRolesFactory.create_editor_role(),
            SystemRolesFactory.create_viewer_role(),
        ]
