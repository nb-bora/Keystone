"""
Moteur de Politique ReBAC (Relationship-Based Access Control) pour Aegis.

Évalue les permissions basées sur les graphes de relations entre sujets et ressources,
similaire à Google Zanzibar. Permet des modèles d'autorisation complexes comme :
- Héritage organisationnel (manager peut voir les documents de ses subordonnés)
- Relations transitives (membre d'un équipe peut accéder aux projets de l'équipe)
- Hiérarchies de groupes et d'organisations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from aegis.core.domain.entities import Subject
from aegis.core.domain.policies import PolicyDecision, PolicyEngine
from aegis.core.domain.values import EvaluationContext, SubjectId


class RelationType(str, Enum):
    """Types de relations supportées."""

    # Relations directes
    DIRECT_MEMBER = "direct_member"  # membre direct d'un groupe
    DIRECT_OWNER = "direct_owner"  # propriétaire direct
    DIRECT_EDITOR = "direct_editor"  # éditeur direct
    DIRECT_VIEWER = "direct_viewer"  # lecteur direct

    # Relations hiérarchiques
    PARENT = "parent"  # relation parent-enfant
    CHILD = "child"  # relation enfant-parent
    ANCESTOR = "ancestor"  # relation transitive ascendante
    DESCENDANT = "descendant"  # relation transitive descendante

    # Relations organisationnelles
    MANAGER = "manager"  # manager-subordonné
    REPORT = "report"  # subordonné-manager
    TEAM_LEAD = "team_lead"  # leader d'équipe
    TEAM_MEMBER = "team_member"  # membre d'équipe

    # Relations transitives
    TRANSITIVE_MEMBER = "transitive_member"  # membre transitif (inclut sous-groupes)
    TRANSITIVE_OWNER = "transitive_owner"  # propriétaire transitif


@dataclass(frozen=True, slots=True)
class RelationshipTuple:
    """Tuple de relation Zanzibar-style : sujet ↔ relation ↔ ressource."""

    subject_id: SubjectId
    relation: RelationType
    resource_id: str
    resource_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Vérifie si la relation a expiré."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __str__(self) -> str:
        return f"{self.subject_id} {self.relation.value} {self.resource_type}:{self.resource_id}"


@dataclass(frozen=True, slots=True)
class RelationshipCheck:
    """Requête de vérification de relation."""

    subject_id: SubjectId
    relation: RelationType
    resource_id: str
    resource_type: str
    follow_transitive: bool = True  # Suivre les relations transitives
    max_depth: int = 10  # Profondeur maximale pour les relations transitives


class RelationshipStore(ABC):
    """Interface de stockage des relations de graphe."""

    @abstractmethod
    def add_tuple(self, tuple: RelationshipTuple) -> None:
        """Ajoute un tuple de relation."""
        pass

    @abstractmethod
    def remove_tuple(self, tuple: RelationshipTuple) -> bool:
        """Supprime un tuple de relation."""
        pass

    @abstractmethod
    def get_tuples(
        self,
        subject_id: Optional[SubjectId] = None,
        resource_id: Optional[str] = None,
        relation: Optional[RelationType] = None,
    ) -> List[RelationshipTuple]:
        """Récupère les tuples de relation selon les critères."""
        pass

    @abstractmethod
    def check_relation(self, check: RelationshipCheck) -> bool:
        """Vérifie si une relation existe."""
        pass

    @abstractmethod
    def get_related_subjects(self, resource_id: str, resource_type: str, relation: RelationType) -> Set[SubjectId]:
        """Récupère tous les sujets ayant une relation avec une ressource."""
        pass

    @abstractmethod
    def get_related_resources(self, subject_id: SubjectId, relation: RelationType) -> Set[Tuple[str, str]]:
        """Récupère toutes les ressources avec lesquelles un sujet a une relation."""
        pass


class InMemoryRelationshipStore(RelationshipStore):
    """Implémentation en mémoire du stockage de relations pour tests."""

    def __init__(self) -> None:
        self._tuples: List[RelationshipTuple] = []
        self._index_by_subject: Dict[SubjectId, List[RelationshipTuple]] = {}
        self._index_by_resource: Dict[Tuple[str, str], List[RelationshipTuple]] = {}

    def add_tuple(self, tuple: RelationshipTuple) -> None:
        """Ajoute un tuple de relation."""
        self._tuples.append(tuple)

        # Mise à jour de l'index par sujet
        if tuple.subject_id not in self._index_by_subject:
            self._index_by_subject[tuple.subject_id] = []
        self._index_by_subject[tuple.subject_id].append(tuple)

        # Mise à jour de l'index par ressource
        resource_key = (tuple.resource_id, tuple.resource_type)
        if resource_key not in self._index_by_resource:
            self._index_by_resource[resource_key] = []
        self._index_by_resource[resource_key].append(tuple)

    def remove_tuple(self, tuple: RelationshipTuple) -> bool:
        """Supprime un tuple de relation."""
        if tuple in self._tuples:
            self._tuples.remove(tuple)

            # Mise à jour des index
            if tuple.subject_id in self._index_by_subject:
                self._index_by_subject[tuple.subject_id] = [
                    t for t in self._index_by_subject[tuple.subject_id] if t != tuple
                ]

            resource_key = (tuple.resource_id, tuple.resource_type)
            if resource_key in self._index_by_resource:
                self._index_by_resource[resource_key] = [t for t in self._index_by_resource[resource_key] if t != tuple]

            return True
        return False

    def get_tuples(
        self,
        subject_id: Optional[SubjectId] = None,
        resource_id: Optional[str] = None,
        relation: Optional[RelationType] = None,
    ) -> List[RelationshipTuple]:
        """Récupère les tuples de relation selon les critères."""
        tuples = self._tuples

        if subject_id is not None:
            tuples = [t for t in tuples if t.subject_id == subject_id]

        if resource_id is not None:
            tuples = [t for t in tuples if t.resource_id == resource_id]

        if relation is not None:
            tuples = [t for t in tuples if t.relation == relation]

        return tuples

    def check_relation(self, check: RelationshipCheck) -> bool:
        """Vérifie si une relation existe avec support transitif."""
        # Vérification directe d'abord
        direct_tuples = self.get_tuples(
            subject_id=check.subject_id, resource_id=check.resource_id, relation=check.relation
        )

        for tuple in direct_tuples:
            if not tuple.is_expired():
                return True

        # Si pas de transitivité demandée, retourner False
        if not check.follow_transitive:
            return False

        # Recherche transitive pour certaines relations
        if check.relation in [RelationType.TRANSITIVE_MEMBER, RelationType.TRANSITIVE_OWNER]:
            return self._check_transitive_relation(check, 0, check.max_depth)

        return False

    def _check_transitive_relation(self, check: RelationshipCheck, depth: int, max_depth: int) -> bool:
        """Vérification récursive des relations transitives."""
        if depth >= max_depth:
            return False

        # Rechercher les ressources intermédiaires
        if check.relation == RelationType.TRANSITIVE_MEMBER:
            # Pour membership transitif, chercher les groupes auxquels le sujet appartient
            group_tuples = self.get_tuples(subject_id=check.subject_id, relation=RelationType.DIRECT_MEMBER)

            for group_tuple in group_tuples:
                if group_tuple.is_expired():
                    continue

                # Vérifier si ce groupe a la relation demandée avec la ressource cible
                group_check = RelationshipCheck(
                    subject_id=SubjectId(group_tuple.resource_id),
                    relation=RelationType.DIRECT_MEMBER,  # ou la relation appropriée
                    resource_id=check.resource_id,
                    resource_type=check.resource_type,
                    follow_transitive=True,
                    max_depth=max_depth - depth - 1,
                )

                if self.check_relation(group_check):
                    return True

                # Recherche récursive
                if self._check_transitive_relation(group_check, depth + 1, max_depth):
                    return True

        return False

    def get_related_subjects(self, resource_id: str, resource_type: str, relation: RelationType) -> Set[SubjectId]:
        """Récupère tous les sujets ayant une relation avec une ressource."""
        tuples = self.get_tuples(resource_id=resource_id, resource_type=resource_type, relation=relation)
        return {t.subject_id for t in tuples if not t.is_expired()}

    def get_related_resources(self, subject_id: SubjectId, relation: RelationType) -> Set[Tuple[str, str]]:
        """Récupère toutes les ressources avec lesquelles un sujet a une relation."""
        tuples = self.get_tuples(subject_id=subject_id, relation=relation)
        return {(t.resource_id, t.resource_type) for t in tuples if not t.is_expired()}


@dataclass(frozen=True, slots=True)
class ReBACPolicy:
    """Politique ReBAC définissant les relations requises pour une action."""

    policy_id: str
    name: str
    description: str
    required_relation: RelationType
    resource_types: Set[str]  # Types de ressources concernés
    allow_transitive: bool = True
    max_depth: int = 10
    priority: int = 0

    def matches_resource_type(self, resource_type: str) -> bool:
        """Vérifie si la politique s'applique à ce type de ressource."""
        return resource_type in self.resource_types or "*" in self.resource_types


class ReBACPolicyEngine(PolicyEngine):
    """Moteur de politique ReBAC avec support des graphes de relations."""

    def __init__(
        self, relationship_store: Optional[RelationshipStore] = None, policies: Optional[List[ReBACPolicy]] = None
    ) -> None:
        self._store = relationship_store or InMemoryRelationshipStore()
        self._policies: List[ReBACPolicy] = policies or []
        self._policy_index: Dict[str, ReBACPolicy] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Reconstruit l'index des politiques."""
        self._policy_index = {policy.policy_id: policy for policy in self._policies}

    def add_policy(self, policy: ReBACPolicy) -> None:
        """Ajoute une politique ReBAC."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority, reverse=True)
        self._rebuild_index()

    def remove_policy(self, policy_id: str) -> bool:
        """Supprime une politique par son ID."""
        if policy_id in self._policy_index:
            self._policies = [p for p in self._policies if p.policy_id != policy_id]
            self._rebuild_index()
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[ReBACPolicy]:
        """Récupère une politique par son ID."""
        return self._policy_index.get(policy_id)

    def add_relation(self, tuple: RelationshipTuple) -> None:
        """Ajoute une relation au graphe."""
        self._store.add_tuple(tuple)

    def remove_relation(self, tuple: RelationshipTuple) -> bool:
        """Supprime une relation du graphe."""
        return self._store.remove_tuple(tuple)

    def evaluate(
        self,
        subject: Subject,
        action: str,
        resource: Optional[Any] = None,
        context: Optional[EvaluationContext] = None,
    ) -> PolicyDecision:
        """Évalue l'accès selon les relations ReBAC."""
        if resource is None:
            return PolicyDecision.deny(action=action, reason="ReBAC evaluation requires a resource.")

        # Extraire l'ID et le type de la ressource
        resource_id = self._extract_resource_id(resource)
        resource_type = self._extract_resource_type(resource)

        if not resource_id or not resource_type:
            return PolicyDecision.deny(action=action, reason="Cannot extract resource ID or type for ReBAC evaluation.")

        # Vérification que le sujet est actif
        if not subject.is_active:
            return PolicyDecision.deny(action=action, reason=f"Le sujet '{subject.id.value}' est inactif ou suspendu.")

        # Évaluation des politiques par ordre de priorité
        for policy in self._policies:
            if not policy.matches_resource_type(resource_type):
                continue

            # Vérification de la relation requise
            check = RelationshipCheck(
                subject_id=subject.id,
                relation=policy.required_relation,
                resource_id=resource_id,
                resource_type=resource_type,
                follow_transitive=policy.allow_transitive,
                max_depth=policy.max_depth,
            )

            if self._store.check_relation(check):
                return PolicyDecision.allow(
                    action=action,
                    reason=f"Accès autorisé par la politique ReBAC '{policy.name}' - relation {policy.required_relation.value}",
                )

        return PolicyDecision.deny(
            action=action,
            reason=f"Aucune relation ReBAC requise trouvée pour l'action '{action}' sur la ressource '{resource_type}:{resource_id}'",
        )

    def _extract_resource_id(self, resource: Any) -> Optional[str]:
        """Extrait l'ID de la ressource."""
        if hasattr(resource, "id"):
            return str(resource.id)
        if hasattr(resource, "resource_id"):
            return str(resource.resource_id)
        if isinstance(resource, dict):
            return resource.get("id") or resource.get("resource_id")
        if isinstance(resource, str):
            return resource
        return None

    def _extract_resource_type(self, resource: Any) -> Optional[str]:
        """Extrait le type de la ressource."""
        if hasattr(resource, "resource_type"):
            return str(resource.resource_type)
        if hasattr(resource, "__class__"):
            return resource.__class__.__name__.lower()
        if isinstance(resource, dict):
            return resource.get("resource_type") or resource.get("type")
        return "unknown"


# Factory pour créer des politiques ReBAC courantes
class ReBACPolicyFactory:
    """Factory pour créer des politiques ReBAC courantes."""

    @staticmethod
    def owner_only_policy(resource_types: Set[str]) -> ReBACPolicy:
        """Politique autorisant uniquement le propriétaire direct."""
        return ReBACPolicy(
            policy_id="owner_only",
            name="Owner Only",
            description="Autorise uniquement le propriétaire direct de la ressource",
            required_relation=RelationType.DIRECT_OWNER,
            resource_types=resource_types,
            allow_transitive=False,
            priority=100,
        )

    @staticmethod
    def editor_policy(resource_types: Set[str]) -> ReBACPolicy:
        """Politique autorisant les éditeurs directs."""
        return ReBACPolicy(
            policy_id="editor_access",
            name="Editor Access",
            description="Autorise les éditeurs directs de la ressource",
            required_relation=RelationType.DIRECT_EDITOR,
            resource_types=resource_types,
            allow_transitive=False,
            priority=90,
        )

    @staticmethod
    def viewer_policy(resource_types: Set[str]) -> ReBACPolicy:
        """Politique autorisant les lecteurs directs."""
        return ReBACPolicy(
            policy_id="viewer_access",
            name="Viewer Access",
            description="Autorise les lecteurs directs de la ressource",
            required_relation=RelationType.DIRECT_VIEWER,
            resource_types=resource_types,
            allow_transitive=False,
            priority=80,
        )

    @staticmethod
    def team_member_policy(resource_types: Set[str]) -> ReBACPolicy:
        """Politique autorisant les membres de l'équipe (transitif)."""
        return ReBACPolicy(
            policy_id="team_member_access",
            name="Team Member Access",
            description="Autorise les membres de l'équipe (incluant sous-groupes)",
            required_relation=RelationType.TRANSITIVE_MEMBER,
            resource_types=resource_types,
            allow_transitive=True,
            max_depth=5,
            priority=70,
        )

    @staticmethod
    def manager_policy(resource_types: Set[str]) -> ReBACPolicy:
        """Politique autorisant les managers (relation hiérarchique)."""
        return ReBACPolicy(
            policy_id="manager_access",
            name="Manager Access",
            description="Autorise les managers via la hiérarchie organisationnelle",
            required_relation=RelationType.MANAGER,
            resource_types=resource_types,
            allow_transitive=True,
            max_depth=3,
            priority=60,
        )


# Utilitaires pour construire des graphes de relations courants
class RelationshipGraphBuilder:
    """Builder pour construire des graphes de relations courants."""

    @staticmethod
    def build_team_structure(
        store: RelationshipStore, team_id: str, members: List[SubjectId], lead_id: Optional[SubjectId] = None
    ) -> None:
        """Construit une structure d'équipe avec membres et leader."""
        team_resource_type = "team"

        # Ajouter les membres
        for member_id in members:
            store.add_tuple(
                RelationshipTuple(
                    subject_id=member_id,
                    relation=RelationType.DIRECT_MEMBER,
                    resource_id=team_id,
                    resource_type=team_resource_type,
                )
            )

        # Ajouter le leader si fourni
        if lead_id:
            store.add_tuple(
                RelationshipTuple(
                    subject_id=lead_id,
                    relation=RelationType.TEAM_LEAD,
                    resource_id=team_id,
                    resource_type=team_resource_type,
                )
            )

    @staticmethod
    def build_ownership(store: RelationshipStore, owner_id: SubjectId, resource_id: str, resource_type: str) -> None:
        """Construit une relation de propriété."""
        store.add_tuple(
            RelationshipTuple(
                subject_id=owner_id,
                relation=RelationType.DIRECT_OWNER,
                resource_id=resource_id,
                resource_type=resource_type,
            )
        )

    @staticmethod
    def build_hierarchy(
        store: RelationshipStore, parent_id: str, parent_type: str, child_id: str, child_type: str
    ) -> None:
        """Construit une relation hiérarchique parent-enfant."""
        # Relation parent -> enfant
        store.add_tuple(
            RelationshipTuple(
                subject_id=SubjectId(parent_id),
                relation=RelationType.PARENT,
                resource_id=child_id,
                resource_type=child_type,
            )
        )

        # Relation enfant -> parent
        store.add_tuple(
            RelationshipTuple(
                subject_id=SubjectId(child_id),
                relation=RelationType.CHILD,
                resource_id=parent_id,
                resource_type=parent_type,
            )
        )
