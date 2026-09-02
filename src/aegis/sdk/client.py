"""
Façade SDK & AegisContainer pour les Développeurs Hôtes.

Offre une interface de haut niveau unifiée pour initialiser Aegis et exécuter
les Use Cases de sécurité en 1 ligne de code.
"""

from typing import Any, Dict, Optional, Set

from aegis.core.application.dtos import EvaluateAccessQuery, RegisterHumanCommand
from aegis.core.application.ports import EventOutbox, SubjectRepository
from aegis.core.application.use_cases import EvaluateAccessUseCase, RegisterHumanUseCase
from aegis.core.domain.entities import HumanIdentity
from aegis.core.domain.policies import PolicyDecision, PolicyEngine
from aegis.core.policies.rbac import RBACPolicyEngine
from aegis.drivers.inmemory import InMemoryEventOutbox, InMemorySubjectRepository


class AegisContainer:
    """Container d'injection de dépendances pour Aegis.

    Permet de configurer les drivers d'infrastructure et les moteurs de politiques.
    """

    def __init__(
        self,
        repository: Optional[SubjectRepository] = None,
        policy_engine: Optional[PolicyEngine] = None,
        outbox: Optional[EventOutbox] = None,
    ) -> None:
        self.repository = repository or InMemorySubjectRepository()
        self.policy_engine = policy_engine or RBACPolicyEngine()
        self.outbox = outbox or InMemoryEventOutbox()


class AegisClient:
    """Façade unifiée pour l'intégration d'Aegis dans les applications hôtes."""

    def __init__(self, container: Optional[AegisContainer] = None) -> None:
        self._container = container or AegisContainer()
        self._register_human_uc = RegisterHumanUseCase(
            repository=self._container.repository, outbox=self._container.outbox
        )
        self._evaluate_access_uc = EvaluateAccessUseCase(
            repository=self._container.repository, policy_engine=self._container.policy_engine
        )

    def register_human(
        self,
        email: str,
        first_name: str = "",
        last_name: str = "",
        tenant_id: Optional[str] = None,
        initial_permissions: Optional[Set[str]] = None,
    ) -> HumanIdentity:
        """Enregistre une nouvelle identité humaine."""
        cmd = RegisterHumanCommand(
            email=email,
            first_name=first_name,
            last_name=last_name,
            tenant_id=tenant_id,
            initial_permissions=initial_permissions or set(),
        )
        return self._register_human_uc.execute(cmd)

    def can(
        self,
        subject_id: str,
        action: str,
        resource: Optional[Any] = None,
        context_attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Vérifie si un sujet est autorisé à exécuter une action en O(1)."""
        query = EvaluateAccessQuery(
            subject_id=subject_id,
            action=action,
            resource=resource,
            context_attributes=context_attributes or {},
        )
        result = self._evaluate_access_uc.execute(query)
        return result.is_allowed
