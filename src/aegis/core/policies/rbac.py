"""
Moteur de Politique RBAC (Role-Based Access Control) pour Aegis.

Évalue les permissions d'un sujet (Humain, Agent IA, Clé API) par rapport à ses
permissions directement ou indirectement assignées.
Complexité Temporelle: O(1) moyen grâce aux ensembles hachés `set[PermissionCode]`.
"""

from typing import Any, Optional

from aegis.core.domain.entities import ApiKeyActor, HumanIdentity, Subject
from aegis.core.domain.policies import PolicyDecision, PolicyEngine
from aegis.core.domain.values import EvaluationContext, PermissionCode


class RBACPolicyEngine(PolicyEngine):
    """Moteur de politique RBAC à haute performance et découplé.

    Évalue l'appartenance de l'action dans l'ensemble des permissions du sujet.
    """

    def evaluate(
        self,
        subject: Subject,
        action: str,
        resource: Optional[Any] = None,
        context: Optional[EvaluationContext] = None,
    ) -> PolicyDecision:
        # Rule 1: Si le sujet est suspendu / inactif -> DENY immédiat O(1)
        if not subject.is_active:
            return PolicyDecision.deny(action=action, reason=f"Le sujet '{subject.id.value}' est inactif ou suspendu.")

        perm_code = PermissionCode(action)

        # Rule 2: Évaluation pour une Identité Humaine
        if isinstance(subject, HumanIdentity):
            if subject.has_direct_permission(perm_code):
                return PolicyDecision.allow(
                    action=action,
                    reason=f"Permission '{action}' accordée directement à l'identité humaine.",
                )

        # Rule 3: Évaluation pour un Acteur Clé API
        elif isinstance(subject, ApiKeyActor):
            if subject.is_expired():
                return PolicyDecision.deny(action=action, reason=f"La clé API '{subject.id.value}' a expiré.")
            if perm_code in subject.permissions:
                return PolicyDecision.allow(action=action, reason=f"Permission '{action}' autorisée pour la clé API.")

        return PolicyDecision.deny(
            action=action, reason=f"Permission '{action}' non trouvée pour le sujet '{subject.id.value}'."
        )
