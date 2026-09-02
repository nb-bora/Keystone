"""
Moteur de Politiques & Décisions d'Accès pour le Domaine Aegis.

Définit les effets de décision (ALLOW, DENY, CONDITIONAL), le modèle de décision
explicite (PolicyDecision) et l'interface abstraite universelle (PolicyEngine).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from aegis.core.domain.entities import Subject
from aegis.core.domain.values import EvaluationContext


class PolicyEffect(str, Enum):
    """Effet d'une décision de politique d'accès."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    CONDITIONAL = "CONDITIONAL"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Résultat explicite de l'évaluation d'une politique de sécurité.

    Complexité Temporelle: O(1) instanciation.
    Complexité Spatiale: O(1) mémoire constante.
    """

    effect: PolicyEffect
    action: str
    reason: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    conditions: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        """Retourne True si l'accès est explicitement accordé en O(1)."""
        return self.effect == PolicyEffect.ALLOW

    @property
    def is_denied(self) -> bool:
        """Retourne True si l'accès est refusé en O(1)."""
        return self.effect == PolicyEffect.DENY

    @classmethod
    def allow(cls, action: str, reason: str = "Accès autorisé") -> "PolicyDecision":
        """Factory pour construire une décision ALLOW en O(1)."""
        return cls(effect=PolicyEffect.ALLOW, action=action, reason=reason)

    @classmethod
    def deny(cls, action: str, reason: str = "Accès refusé") -> "PolicyDecision":
        """Factory pour construire une décision DENY en O(1)."""
        return cls(effect=PolicyEffect.DENY, action=action, reason=reason)


class PolicyEngine(ABC):
    """Interface abstraite universelle pour les moteurs de politique d'accès (Policy Engine).

    Peut être implémentée par un moteur RBAC, ABAC, ReBAC ou Composite.
    """

    @abstractmethod
    def evaluate(
        self,
        subject: Subject,
        action: str,
        resource: Optional[Any] = None,
        context: Optional[EvaluationContext] = None,
    ) -> PolicyDecision:
        """Évalue si le sujet est autorisé à exécuter l'action sur la ressource.

        Parameters
        ----------
        subject : Subject
            L'acteur demandant l'accès.
        action : str
            Le code de l'action/permission (ex: 'document:edit').
        resource : Optional[Any]
            L'objet ou entité cible (optionnel).
        context : Optional[EvaluationContext]
            Le contexte d'évaluation (IP, heure, métadonnées).

        Returns
        -------
        PolicyDecision
            La décision explicite ALLOW, DENY ou CONDITIONAL.
        """
        pass
