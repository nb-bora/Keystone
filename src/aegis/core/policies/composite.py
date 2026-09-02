"""
Moteur de Politique Composite (Cascade Evaluation) pour Aegis.

Permet de combiner plusieurs moteurs de politique (RBAC, ABAC, ReBAC) en cascade.
Stratégie par défaut: FIRST_APPLICABLE (le premier moteur retournant ALLOW accorde l'accès).
"""

from enum import Enum
from typing import Any, List, Optional

from aegis.core.domain.entities import Subject
from aegis.core.domain.policies import PolicyDecision, PolicyEngine
from aegis.core.domain.values import EvaluationContext


class CascadeStrategy(str, Enum):
    """Stratégie d'agrégation des résultats d'évaluation."""

    FIRST_APPLICABLE = "FIRST_APPLICABLE"  # Le premier ALLOW l'emporte, sinon le dernier DENY
    AFFIRMATIVE = "AFFIRMATIVE"  # Au moins un ALLOW autorise l'accès
    UNANIMOUS = "UNANIMOUS"  # Tous les moteurs doivent accorder ALLOW


class CompositePolicyEngine(PolicyEngine):
    """Moteur composite combinant N moteurs de politiques en cascade.

    Complexité Temporelle: O(N * P) où N est le nombre de moteurs et P le temps d'évaluation par moteur.
    """

    def __init__(
        self,
        engines: List[PolicyEngine],
        strategy: CascadeStrategy = CascadeStrategy.FIRST_APPLICABLE,
    ) -> None:
        if not engines:
            raise ValueError("CompositePolicyEngine nécessite au moins un moteur de politique.")
        self._engines = list(engines)
        self._strategy = strategy

    def evaluate(
        self,
        subject: Subject,
        action: str,
        resource: Optional[Any] = None,
        context: Optional[EvaluationContext] = None,
    ) -> PolicyDecision:
        last_decision: Optional[PolicyDecision] = None

        if self._strategy == CascadeStrategy.FIRST_APPLICABLE or self._strategy == CascadeStrategy.AFFIRMATIVE:
            for engine in self._engines:
                decision = engine.evaluate(subject, action, resource, context)
                last_decision = decision
                if decision.is_allowed:
                    return decision

            return last_decision or PolicyDecision.deny(action=action, reason="Aucun moteur n'a accordé l'accès.")

        elif self._strategy == CascadeStrategy.UNANIMOUS:
            for engine in self._engines:
                decision = engine.evaluate(subject, action, resource, context)
                if not decision.is_allowed:
                    return decision
            return PolicyDecision.allow(action=action, reason="Tous les moteurs ont validé l'accès.")

        return PolicyDecision.deny(action=action, reason="Stratégie de cascade invalide.")
