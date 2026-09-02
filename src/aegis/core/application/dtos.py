"""
DTOs (Data Transfer Objects) pour la couche Application d'Aegis.

Contient les structures de données immutables servant de frontière entre
l'application hôte et les Use Cases Aegis.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from aegis.core.domain.policies import PolicyEffect


@dataclass(frozen=True, slots=True)
class RegisterHumanCommand:
    """Commande d'enregistrement d'une identité humaine."""

    email: str
    first_name: str = ""
    last_name: str = ""
    tenant_id: Optional[str] = None
    initial_permissions: Set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class RegisterServiceAccountCommand:
    """Commande d'enregistrement d'un Service Account M2M."""

    client_id: str
    tenant_id: Optional[str] = None
    initial_scopes: Set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class EvaluateAccessQuery:
    """Requête d'évaluation d'autorisation d'un sujet."""

    subject_id: str
    action: str
    resource: Optional[Any] = None
    context_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvaluationResultDTO:
    """Résultat DTO transmis à l'application hôte après évaluation."""

    is_allowed: bool
    effect: PolicyEffect
    action: str
    reason: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
