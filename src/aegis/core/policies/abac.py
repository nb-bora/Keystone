"""
Moteur de Politique ABAC (Attribute-Based Access Control) pour Aegis.

Évalue les permissions basées sur des attributs dynamiques du contexte :
- Heure de la journée (business hours only)
- Adresse IP ( whitelist/blacklist)
- Localisation géographique
- Statut de la ressource
- Niveau de risque du sujet
- Attributs personnalisés
"""

import ipaddress
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from aegis.core.domain.entities import Subject
from aegis.core.domain.policies import PolicyDecision, PolicyEngine
from aegis.core.domain.values import EvaluationContext


class AttributeOperator(str, Enum):
    """Opérateurs de comparaison pour les attributs."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    REGEX_MATCH = "regex_match"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


@dataclass(frozen=True, slots=True)
class AttributeCondition:
    """Condition sur un attribut pour l'évaluation ABAC."""

    attribute_name: str
    operator: AttributeOperator
    expected_value: Any
    description: str = ""

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue la condition sur le contexte et le sujet."""
        # Récupération de la valeur de l'attribut
        actual_value = self._get_attribute_value(context, subject)

        if actual_value is None:
            return False

        # Application de l'opérateur
        try:
            return self._apply_operator(actual_value)
        except Exception:
            return False

    def _get_attribute_value(self, context: EvaluationContext, subject: Subject) -> Any:
        """Récupère la valeur de l'attribut depuis le contexte ou le sujet."""
        # Attributs du contexte
        if self.attribute_name in context.attributes:
            return context.attributes[self.attribute_name]

        # Attributs système prédéfinis
        if self.attribute_name == "ip_address":
            return context.ip_address

        if self.attribute_name == "timestamp":
            return context.timestamp

        if self.attribute_name == "subject_id":
            return subject.id.value

        if self.attribute_name == "subject_type":
            return subject.subject_type

        if self.attribute_name == "is_active":
            return subject.is_active

        if self.attribute_name == "tenant_id":
            return subject.tenant_id.value if subject.tenant_id else None

        # Attributs spécifiques aux types de sujets
        if hasattr(subject, self.attribute_name):
            attr_value = getattr(subject, self.attribute_name)
            # Gestion des value objects
            if hasattr(attr_value, "value"):
                return attr_value.value
            return attr_value

        return None

    def _apply_operator(self, actual_value: Any) -> bool:
        """Applique l'opérateur de comparaison."""
        expected = self.expected_value

        if self.operator == AttributeOperator.EQUALS:
            return actual_value == expected

        if self.operator == AttributeOperator.NOT_EQUALS:
            return actual_value != expected

        if self.operator == AttributeOperator.CONTAINS:
            if isinstance(actual_value, (list, set, tuple)):
                return expected in actual_value
            if isinstance(actual_value, str):
                return expected in actual_value
            return False

        if self.operator == AttributeOperator.NOT_CONTAINS:
            if isinstance(actual_value, (list, set, tuple)):
                return expected not in actual_value
            if isinstance(actual_value, str):
                return expected not in actual_value
            return False

        if self.operator == AttributeOperator.GREATER_THAN:
            try:
                return actual_value > expected
            except TypeError:
                return False

        if self.operator == AttributeOperator.LESS_THAN:
            try:
                return actual_value < expected
            except TypeError:
                return False

        if self.operator == AttributeOperator.GREATER_THAN_OR_EQUAL:
            try:
                return actual_value >= expected
            except TypeError:
                return False

        if self.operator == AttributeOperator.LESS_THAN_OR_EQUAL:
            try:
                return actual_value <= expected
            except TypeError:
                return False

        if self.operator == AttributeOperator.IN:
            if isinstance(expected, (list, set, tuple)):
                return actual_value in expected
            return False

        if self.operator == AttributeOperator.NOT_IN:
            if isinstance(expected, (list, set, tuple)):
                return actual_value not in expected
            return False

        if self.operator == AttributeOperator.STARTS_WITH:
            if isinstance(actual_value, str) and isinstance(expected, str):
                return actual_value.startswith(expected)
            return False

        if self.operator == AttributeOperator.ENDS_WITH:
            if isinstance(actual_value, str) and isinstance(expected, str):
                return actual_value.endswith(expected)
            return False

        return False


@dataclass(frozen=True, slots=True)
class TimeBasedCondition(AttributeCondition):
    """Condition basée sur le temps (heures ouvrées, jours ouvrés, etc.)."""

    start_time: Optional[time] = None
    end_time: Optional[time] = None
    allowed_days: Optional[Set[int]] = None  # 0=Monday, 6=Sunday
    timezone_str: str = "UTC"

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue la condition temporelle."""
        if context.timestamp is None:
            return False

        # Conversion du timestamp vers le timezone spécifié
        try:
            import pytz

            tz = pytz.timezone(self.timezone_str)
            local_time = context.timestamp.astimezone(tz)
        except ImportError:
            # Fallback sans pytz
            local_time = context.timestamp

        # Validation des jours de la semaine
        if self.allowed_days is not None:
            day_of_week = local_time.weekday()  # 0=Monday, 6=Sunday
            if day_of_week not in self.allowed_days:
                return False

        # Validation des heures
        if self.start_time is not None and self.end_time is not None:
            current_time = local_time.time()
            if not (self.start_time <= current_time <= self.end_time):
                return False

        return True


@dataclass(frozen=True, slots=True)
class IPBasedCondition(AttributeCondition):
    """Condition basée sur l'adresse IP (whitelist, blacklist, plage)."""

    allowed_ips: Optional[Set[str]] = None
    blocked_ips: Optional[Set[str]] = None
    allowed_ip_ranges: Optional[List[str]] = None  # ex: ["192.168.1.0/24"]
    blocked_ip_ranges: Optional[List[str]] = None

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue la condition IP."""
        ip_str = context.ip_address
        if not ip_str:
            return False

        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        # Validation des IP bloquées
        if self.blocked_ips and ip_str in self.blocked_ips:
            return False

        # Validation des plages IP bloquées
        if self.blocked_ip_ranges:
            for range_str in self.blocked_ip_ranges:
                try:
                    if ip in ipaddress.ip_network(range_str):
                        return False
                except ValueError:
                    continue

        # Validation des IP autorisées
        if self.allowed_ips:
            return ip_str in self.allowed_ips

        # Validation des plages IP autorisées
        if self.allowed_ip_ranges:
            for range_str in self.allowed_ip_ranges:
                try:
                    if ip in ipaddress.ip_network(range_str):
                        return True
                except ValueError:
                    continue
            return False  # Si des plages sont définies mais IP n'est dans aucune

        return True


@dataclass(frozen=True, slots=True)
class ResourceBasedCondition(AttributeCondition):
    """Condition basée sur les attributs de la ressource."""

    resource_attribute: str = ""
    operator: AttributeOperator = AttributeOperator.EQUALS
    expected_value: Any = None

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue la condition sur la ressource."""
        # La ressource est passée via le contexte
        resource = context.attributes.get("resource")
        if resource is None:
            return False

        if not hasattr(resource, self.resource_attribute):
            return False

        actual_value = getattr(resource, self.resource_attribute)

        # Application de l'opérateur
        try:
            if self.operator == AttributeOperator.EQUALS:
                return actual_value == self.expected_value
            elif self.operator == AttributeOperator.NOT_EQUALS:
                return actual_value != self.expected_value
            elif self.operator == AttributeOperator.IN:
                return actual_value in self.expected_value
            elif self.operator == AttributeOperator.CONTAINS:
                return self.expected_value in actual_value
            else:
                return False
        except Exception:
            return False


@dataclass(frozen=True, slots=True)
class CustomCondition(AttributeCondition):
    """Condition personnalisée utilisant une fonction lambda."""

    evaluation_func: Optional[Callable[[EvaluationContext, Subject], bool]] = None

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue la condition personnalisée."""
        if self.evaluation_func is None:
            return False

        try:
            return self.evaluation_func(context, subject)
        except Exception:
            return False


@dataclass(frozen=True, slots=True)
class ABACPolicy:
    """Politique ABAC complète avec conditions et effet."""

    policy_id: str
    name: str
    description: str
    effect: str  # "ALLOW" ou "DENY"
    conditions: List[AttributeCondition] = field(default_factory=list)
    priority: int = 0  # Plus haute priorité = évalué en premier

    def evaluate(self, context: EvaluationContext, subject: Subject) -> bool:
        """Évalue toutes les conditions de la politique."""
        # Si aucune condition, la politique s'applique toujours
        if not self.conditions:
            return True

        # Toutes les conditions doivent être satisfaites (AND logique)
        for condition in self.conditions:
            if not condition.evaluate(context, subject):
                return False

        return True


class ABACPolicyEngine(PolicyEngine):
    """Moteur de politique ABAC à haute performance et extensibilité."""

    def __init__(self, policies: Optional[List[ABACPolicy]] = None) -> None:
        self._policies: List[ABACPolicy] = policies or []
        self._policy_index: Dict[str, ABACPolicy] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Reconstruit l'index des politiques par ID."""
        self._policy_index = {policy.policy_id: policy for policy in self._policies}

    def add_policy(self, policy: ABACPolicy) -> None:
        """Ajoute une politique au moteur."""
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

    def get_policy(self, policy_id: str) -> Optional[ABACPolicy]:
        """Récupère une politique par son ID."""
        return self._policy_index.get(policy_id)

    def evaluate(
        self,
        subject: Subject,
        action: str,
        resource: Optional[Any] = None,
        context: Optional[EvaluationContext] = None,
    ) -> PolicyDecision:
        """Évalue l'accès selon les politiques ABAC."""
        if context is None:
            context = EvaluationContext()

        # Ajout de la ressource au contexte si fournie
        if resource is not None:
            context = EvaluationContext(
                ip_address=context.ip_address,
                timestamp=context.timestamp,
                attributes={**context.attributes, "resource": resource},
            )

        # Vérification que le sujet est actif
        if not subject.is_active:
            return PolicyDecision.deny(action=action, reason=f"Le sujet '{subject.id.value}' est inactif ou suspendu.")

        # Évaluation des politiques par ordre de priorité
        for policy in self._policies:
            if policy.evaluate(context, subject):
                if policy.effect == "ALLOW":
                    return PolicyDecision.allow(
                        action=action,
                        reason=f"Accès autorisé par la politique ABAC '{policy.name}' (ID: {policy.policy_id})",
                    )
                else:
                    return PolicyDecision.deny(
                        action=action,
                        reason=f"Accès refusé par la politique ABAC '{policy.name}' (ID: {policy.policy_id})",
                    )

        # Par défaut, refus si aucune politique ne s'applique
        return PolicyDecision.deny(action=action, reason="Aucune politique ABAC ne s'applique à cette demande.")


# Factory pour créer des conditions courantes
class ABACConditionFactory:
    """Factory pour créer des conditions ABAC courantes."""

    @staticmethod
    def business_hours_only(
        start_hour: int = 9, end_hour: int = 17, timezone_str: str = "UTC", allowed_days: Optional[Set[int]] = None
    ) -> TimeBasedCondition:
        """Crée une condition pour les heures ouvrées uniquement."""
        return TimeBasedCondition(
            attribute_name="timestamp",
            operator=AttributeOperator.EQUALS,
            expected_value=None,
            start_time=time(start_hour, 0),
            end_time=time(end_hour, 0),
            timezone_str=timezone_str,
            allowed_days=allowed_days or {0, 1, 2, 3, 4},  # Lundi-Vendredi
        )

    @staticmethod
    def ip_whitelist(allowed_ips: Set[str]) -> IPBasedCondition:
        """Crée une condition de whitelist IP."""
        return IPBasedCondition(
            attribute_name="ip_address",
            operator=AttributeOperator.IN,
            expected_value=allowed_ips,
            allowed_ips=allowed_ips,
        )

    @staticmethod
    def ip_blacklist(blocked_ips: Set[str]) -> IPBasedCondition:
        """Crée une condition de blacklist IP."""
        return IPBasedCondition(
            attribute_name="ip_address",
            operator=AttributeOperator.NOT_IN,
            expected_value=blocked_ips,
            blocked_ips=blocked_ips,
        )

    @staticmethod
    def ip_range_whitelist(ranges: List[str]) -> IPBasedCondition:
        """Crée une condition de whitelist de plages IP."""
        return IPBasedCondition(
            attribute_name="ip_address",
            operator=AttributeOperator.EQUALS,
            expected_value=None,
            allowed_ip_ranges=ranges,
        )

    @staticmethod
    def resource_status_equals(expected_status: str) -> ResourceBasedCondition:
        """Crée une condition sur le statut de la ressource."""
        return ResourceBasedCondition(
            attribute_name="resource",
            operator=AttributeOperator.EQUALS,
            expected_value=expected_status,
            resource_attribute="status",
        )

    @staticmethod
    def resource_owner_equals(subject_id: str) -> ResourceBasedCondition:
        """Crée une condition vérifiant que le sujet est le propriétaire de la ressource."""
        return ResourceBasedCondition(
            attribute_name="resource",
            operator=AttributeOperator.EQUALS,
            expected_value=subject_id,
            resource_attribute="owner_id",
        )

    @staticmethod
    def custom_condition(
        func: Callable[[EvaluationContext, Subject], bool], description: str = "Custom condition"
    ) -> CustomCondition:
        """Crée une condition personnalisée."""
        return CustomCondition(
            attribute_name="custom",
            operator=AttributeOperator.EQUALS,
            expected_value=None,
            evaluation_func=func,
            description=description,
        )


# Politiques ABAC prédéfinies
class PredefinedABACPolicies:
    """Collection de politiques ABAC prédéfinies."""

    @staticmethod
    def business_hours_policy() -> ABACPolicy:
        """Politique autorisant l'accès uniquement pendant les heures ouvrées."""
        return ABACPolicy(
            policy_id="business_hours_only",
            name="Business Hours Only",
            description="Autorise l'accès uniquement pendant les heures ouvrées (9h-17h, Lundi-Vendredi, UTC)",
            effect="ALLOW",
            conditions=[ABACConditionFactory.business_hours_only()],
            priority=100,
        )

    @staticmethod
    def corporate_network_policy(allowed_ranges: List[str]) -> ABACPolicy:
        """Politique autorisant l'accès uniquement depuis le réseau corporate."""
        return ABACPolicy(
            policy_id="corporate_network_only",
            name="Corporate Network Only",
            description=f"Autorise l'accès uniquement depuis les plages IP corporate: {allowed_ranges}",
            effect="ALLOW",
            conditions=[ABACConditionFactory.ip_range_whitelist(allowed_ranges)],
            priority=90,
        )

    @staticmethod
    def owner_only_policy() -> ABACPolicy:
        """Politique autorisant uniquement le propriétaire de la ressource."""
        return ABACPolicy(
            policy_id="owner_only",
            name="Owner Only",
            description="Autorise uniquement le propriétaire de la ressource",
            effect="ALLOW",
            conditions=[ABACConditionFactory.resource_owner_equals("subject_id")],
            priority=80,
        )

    @staticmethod
    def draft_documents_policy() -> ABACPolicy:
        """Politique autorisant l'édition uniquement des documents en brouillon."""
        return ABACPolicy(
            policy_id="draft_documents_only",
            name="Draft Documents Only",
            description="Autorise l'édition uniquement des documents avec le statut DRAFT",
            effect="ALLOW",
            conditions=[ABACConditionFactory.resource_status_equals("DRAFT")],
            priority=70,
        )
