"""
Use Cases Applicatifs pour Aegis.

Contient les composants d'orchestration autonomes et indépendants de tout framework web.
"""

import uuid
from typing import Optional

from aegis.core.application.dtos import (
    EvaluateAccessQuery,
    EvaluationResultDTO,
    RegisterHumanCommand,
)
from aegis.core.application.ports import EventOutbox, SubjectRepository
from aegis.core.domain.entities import HumanIdentity
from aegis.core.domain.events import SubjectRegisteredEvent
from aegis.core.domain.policies import PolicyEngine
from aegis.core.domain.values import EmailAddress, EvaluationContext, PermissionCode, SubjectId, TenantId


class RegisterHumanUseCase:
    """Use Case: Enregistrement d'une nouvelle identité humaine.

    Complexité Temporelle: O(1) enregistrement et émission d'événement Outbox.
    """

    def __init__(self, repository: SubjectRepository, outbox: EventOutbox) -> None:
        self._repository = repository
        self._outbox = outbox

    def execute(self, command: RegisterHumanCommand) -> HumanIdentity:
        email = EmailAddress(command.email)

        # Vérification d'unicité d'email
        existing = self._repository.get_by_email(email)
        if existing is not None:
            raise ValueError(f"Une identité avec l'email '{command.email}' existe déjà.")

        subject_id = SubjectId(str(uuid.uuid4()))
        tenant_id = TenantId(command.tenant_id) if command.tenant_id else None

        human = HumanIdentity(
            id=subject_id,
            tenant_id=tenant_id,
            email=email,
            first_name=command.first_name,
            last_name=command.last_name,
        )

        for perm in command.initial_permissions:
            human.grant_permission(PermissionCode(perm))

        # Persistance et Outbox dans la même transaction
        self._repository.save(human)
        self._outbox.publish(
            SubjectRegisteredEvent(
                subject_id=subject_id,
                subject_type="HUMAN",
                email_anonymized=email.anonymized(),
            )
        )

        return human


class EvaluateAccessUseCase:
    """Use Case: Évaluation de l'autorisation d'un sujet.

    Complexité Temporelle: O(1) recherche + évaluation de politique.
    """

    def __init__(self, repository: SubjectRepository, policy_engine: PolicyEngine) -> None:
        self._repository = repository
        self._policy_engine = policy_engine

    def execute(self, query: EvaluateAccessQuery) -> EvaluationResultDTO:
        subject_id = SubjectId(query.subject_id)
        subject = self._repository.get_by_id(subject_id)

        if subject is None:
            return EvaluationResultDTO(
                is_allowed=False,
                effect=PolicyEffect.DENY,  # type: ignore
                action=query.action,
                reason=f"Sujet '{query.subject_id}' introuvable.",
            )

        context = EvaluationContext(attributes=query.context_attributes)
        decision = self._policy_engine.evaluate(
            subject=subject,
            action=query.action,
            resource=query.resource,
            context=context,
        )

        return EvaluationResultDTO(
            is_allowed=decision.is_allowed,
            effect=decision.effect,
            action=decision.action,
            reason=decision.reason,
            evaluated_at=decision.evaluated_at,
        )
