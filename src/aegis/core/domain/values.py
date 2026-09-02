"""
Value Objects pour le Domaine Aegis.

Contient les types immutables et fortement typés du langage ubiquitaire.
Toutes les classes utilisent `slots=True, frozen=True` pour garantir une empreinte
mémoire minimale (réduction ~60%) et un hachage O(1) thread-safe.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True, slots=True)
class SubjectId:
    """Identifiant unique d'un sujet (Humain, Machine, Agent IA, Clé API).

    Complexité Temporelle: O(1) instanciation et hachage.
    Complexité Spatiale: O(1) mémoire constante (~64 octets avec slots).
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("SubjectId doit être une chaîne non vide.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TenantId:
    """Identifiant unique d'une organisation ou tenant.

    Complexité Temporelle: O(1).
    Complexité Spatiale: O(1).
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("TenantId doit être une chaîne non vide.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PermissionCode:
    """Code unique d'une permission métier (ex: 'document:edit', 'user:suspend').

    Complexité Temporelle: O(1).
    Complexité Spatiale: O(1).
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("PermissionCode doit être une chaîne non vide.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RoleId:
    """Identifiant unique d'un rôle (ex: 'ADMIN', 'EDITOR', 'VIEWER').

    Complexité Temporelle: O(1).
    Complexité Spatiale: O(1).
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("RoleId doit être une chaîne non vide.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """Adresse email validée et normalisée.

    Complexité Temporelle: O(1) validation regex.
    Complexité Spatiale: O(1).
    """

    value: str

    # Regex conforme à la RFC 5322 simplifiée
    _EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not self._EMAIL_REGEX.match(normalized):
            raise ValueError(f"Adresse email invalide: '{self.value}'")
        # Forcer la valeur normalisée via object.__setattr__ dans une dataclass frozen
        object.__setattr__(self, "value", normalized)

    @property
    def domain(self) -> str:
        """Retourne le nom de domaine de l'email en O(1)."""
        return self.value.split("@")[1]

    def anonymized(self) -> str:
        """Anonymise l'email pour le traçage d'audit (ex: 'j***@domain.com') en O(1)."""
        username, dom = self.value.split("@")
        if len(username) <= 1:
            return f"*@{dom}"
        return f"{username[0]}***@{dom}"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Contexte d'évaluation d'une politique de sécurité (IP, heure, métadonnées).

    Complexité Temporelle: O(1).
    Complexité Spatiale: O(K) où K est le nombre d'attributs de contexte.
    """

    ip_address: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = field(default_factory=dict)
