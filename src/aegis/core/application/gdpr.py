"""
Pipeline GDPR avec Droit à l'Oubli pour Aegis.

Implémente la conformité RGPD avec anonymisation des données personnelles,
droit à l'oubli, export de données et gestion du consentement.
"""

import hashlib
import secrets
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from aegis.core.domain.entities import HumanIdentity, Subject
from aegis.core.domain.values import EmailAddress, SubjectId


class GDPRAction(str, Enum):
    """Actions RGPD supportées."""

    DATA_EXPORT = "data_export"
    DATA_ANONYMIZATION = "data_anonymization"
    DATA_DELETION = "data_deletion"
    CONSENT_WITHDRAWAL = "consent_withdrawal"
    ACCESS_REQUEST = "access_request"


class DataRetentionStatus(str, Enum):
    """Statuts de rétention des données."""

    ACTIVE = "active"
    ANONYMIZED = "anonymized"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    """Enregistrement de consentement."""

    consent_id: str
    subject_id: SubjectId
    consent_type: str  # marketing, analytics, essential, etc.
    granted: bool
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    withdrawn_at: Optional[datetime] = None
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Vérifie si le consentement est actif."""
        return self.granted and self.withdrawn_at is None

    def withdraw(self) -> "ConsentRecord":
        """Retire le consentement."""
        return ConsentRecord(
            consent_id=self.consent_id,
            subject_id=self.subject_id,
            consent_type=self.consent_type,
            granted=False,
            granted_at=self.granted_at,
            withdrawn_at=datetime.now(timezone.utc),
            version=self.version,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class DataRetentionRecord:
    """Enregistrement de rétention des données."""

    subject_id: SubjectId
    status: DataRetentionStatus
    anonymization_date: Optional[datetime] = None
    scheduled_deletion_date: Optional[datetime] = None
    deletion_date: Optional[datetime] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def should_anonymize(self) -> bool:
        """Vérifie si les données doivent être anonymisées."""
        if self.status != DataRetentionStatus.ACTIVE:
            return False
        if self.anonymization_date is None:
            return False
        return datetime.now(timezone.utc) >= self.anonymization_date

    def should_delete(self) -> bool:
        """Vérifie si les données doivent être supprimées."""
        if self.status != DataRetentionStatus.PENDING_DELETION:
            return False
        if self.scheduled_deletion_date is None:
            return False
        return datetime.now(timezone.utc) >= self.scheduled_deletion_date


class DataAnonymizer(ABC):
    """Interface pour les anonymisateurs de données."""

    @abstractmethod
    def anonymize_email(self, email: str) -> str:
        """Anonymise une adresse email."""
        pass

    @abstractmethod
    def anonymize_phone(self, phone: str) -> str:
        """Anonymise un numéro de téléphone."""
        pass

    @abstractmethod
    def anonymize_name(self, name: str) -> str:
        """Anonymise un nom."""
        pass

    @abstractmethod
    def anonymize_address(self, address: str) -> str:
        """Anonymise une adresse."""
        pass

    @abstractmethod
    def anonymize_ip(self, ip: str) -> str:
        """Anonymise une adresse IP."""
        pass


class StandardDataAnonymizer(DataAnonymizer):
    """Anonymiseur standard de données."""

    def anonymize_email(self, email: str) -> str:
        """Anonymise une adresse email."""
        try:
            username, domain = email.split("@")
            if len(username) <= 2:
                return f"*@{domain}"
            return f"{username[0]}***@{domain}"
        except Exception:
            return "***@***.***"

    def anonymize_phone(self, phone: str) -> str:
        """Anonymise un numéro de téléphone."""
        # Garder seulement les 2 derniers chiffres
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) <= 2:
            return "***"
        return "*" * (len(digits) - 2) + digits[-2:]

    def anonymize_name(self, name: str) -> str:
        """Anonymise un nom."""
        if len(name) <= 1:
            return "*"
        return name[0] + "*" * (len(name) - 1)

    def anonymize_address(self, address: str) -> str:
        """Anonymise une adresse."""
        # Garder seulement le code postal si présent
        words = address.split()
        for word in words:
            if word.isdigit() and len(word) >= 5:
                return f"***, {word}"
        return "***"

    def anonymize_ip(self, ip: str) -> str:
        """Anonymise une adresse IP."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***.***.***.***"
        except Exception:
            return "***.***.***.***"


class GDPRPipeline:
    """Pipeline de traitement RGPD."""

    def __init__(
        self,
        anonymizer: Optional[DataAnonymizer] = None,
        anonymization_delay_days: int = 30,
        hard_delete_delay_days: int = 365,
    ) -> None:
        self._anonymizer = anonymizer or StandardDataAnonymizer()
        self._anonymization_delay = timedelta(days=anonymization_delay_days)
        self._hard_delete_delay = timedelta(days=hard_delete_delay_days)
        self._retention_records: Dict[SubjectId, DataRetentionRecord] = {}
        self._consent_records: Dict[str, ConsentRecord] = {}
        self._lock = threading.Lock()

    def request_data_deletion(self, subject_id: SubjectId, reason: str = "User request") -> DataRetentionRecord:
        """Traite une demande de suppression de données."""
        anonymization_date = datetime.now(timezone.utc) + self._anonymization_delay
        deletion_date = datetime.now(timezone.utc) + self._hard_delete_delay

        record = DataRetentionRecord(
            subject_id=subject_id,
            status=DataRetentionStatus.ACTIVE,
            anonymization_date=anonymization_date,
            scheduled_deletion_date=deletion_date,
            reason=reason,
        )

        with self._lock:
            self._retention_records[subject_id] = record

        return record

    def anonymize_subject_data(self, subject: Subject) -> Subject:
        """Anonymise les données personnelles d'un sujet."""
        if not isinstance(subject, HumanIdentity):
            return subject

        anonymized_email = None
        if subject.email:
            anonymized_email = EmailAddress(self._anonymizer.anonymize_email(subject.email.value))

        anonymized_first_name = self._anonymizer.anonymize_name(subject.first_name)
        anonymized_last_name = self._anonymizer.anonymize_name(subject.last_name)

        anonymized_subject = HumanIdentity(
            id=subject.id,
            tenant_id=subject.tenant_id,
            is_active=subject.is_active,
            email=anonymized_email,
            first_name=anonymized_first_name,
            last_name=anonymized_last_name,
            is_email_verified=False,  # Après anonymisation, email n'est plus vérifié
            permissions=subject.permissions,
            created_at=subject.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        # Mettre à jour le record de rétention
        with self._lock:
            if subject.id in self._retention_records:
                old_record = self._retention_records[subject.id]
                new_record = DataRetentionRecord(
                    subject_id=old_record.subject_id,
                    status=DataRetentionStatus.ANONYMIZED,
                    anonymization_date=datetime.now(timezone.utc),
                    scheduled_deletion_date=old_record.scheduled_deletion_date,
                    reason=old_record.reason,
                    metadata=old_record.metadata,
                )
                self._retention_records[subject.id] = new_record

        return anonymized_subject

    def hard_delete_subject(self, subject_id: SubjectId) -> bool:
        """Supprime définitivement les données d'un sujet."""
        with self._lock:
            if subject_id in self._retention_records:
                old_record = self._retention_records[subject_id]
                new_record = DataRetentionRecord(
                    subject_id=old_record.subject_id,
                    status=DataRetentionStatus.DELETED,
                    anonymization_date=old_record.anonymization_date,
                    scheduled_deletion_date=old_record.scheduled_deletion_date,
                    deletion_date=datetime.now(timezone.utc),
                    reason=old_record.reason,
                    metadata=old_record.metadata,
                )
                self._retention_records[subject_id] = new_record

            # Supprimer également les consentements
            consent_ids_to_remove = [
                consent_id for consent_id, record in self._consent_records.items() if record.subject_id == subject_id
            ]
            for consent_id in consent_ids_to_remove:
                del self._consent_records[consent_id]

            return True

        return False

    def export_subject_data(self, subject: Subject) -> Dict[str, Any]:
        """Exporte les données d'un sujet au format RGPD."""
        export_data = {
            "export_id": secrets.token_urlsafe(16),
            "subject_id": subject.id.value,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "data": {
                "subject_type": subject.subject_type,
                "is_active": subject.is_active,
                "created_at": subject.created_at.isoformat(),
                "updated_at": subject.updated_at.isoformat(),
            },
            "consents": [],
            "retention_status": None,
        }

        if isinstance(subject, HumanIdentity):
            export_data["data"].update(
                {
                    "email": subject.email.value if subject.email else None,
                    "first_name": subject.first_name,
                    "last_name": subject.last_name,
                    "is_email_verified": subject.is_email_verified,
                    "permissions": [p.value for p in subject.permissions],
                }
            )

        # Ajouter les consentements
        with self._lock:
            subject_consents = [record for record in self._consent_records.values() if record.subject_id == subject.id]
            export_data["consents"] = [
                {
                    "consent_type": record.consent_type,
                    "granted": record.granted,
                    "granted_at": record.granted_at.isoformat(),
                    "withdrawn_at": record.withdrawn_at.isoformat() if record.withdrawn_at else None,
                    "version": record.version,
                }
                for record in subject_consents
            ]

            # Ajouter le statut de rétention
            if subject.id in self._retention_records:
                retention_record = self._retention_records[subject.id]
                export_data["retention_status"] = {
                    "status": retention_record.status.value,
                    "anonymization_date": retention_record.anonymization_date.isoformat()
                    if retention_record.anonymization_date
                    else None,
                    "scheduled_deletion_date": retention_record.scheduled_deletion_date.isoformat()
                    if retention_record.scheduled_deletion_date
                    else None,
                    "deletion_date": retention_record.deletion_date.isoformat()
                    if retention_record.deletion_date
                    else None,
                    "reason": retention_record.reason,
                }

        return export_data

    def record_consent(
        self, subject_id: SubjectId, consent_type: str, granted: bool = True, metadata: Optional[Dict[str, Any]] = None
    ) -> ConsentRecord:
        """Enregistre un consentement."""
        consent_id = secrets.token_urlsafe(16)

        record = ConsentRecord(
            consent_id=consent_id,
            subject_id=subject_id,
            consent_type=consent_type,
            granted=granted,
            metadata=metadata or {},
        )

        with self._lock:
            self._consent_records[consent_id] = record

        return record

    def withdraw_consent(self, consent_id: str) -> Optional[ConsentRecord]:
        """Retire un consentement."""
        with self._lock:
            if consent_id in self._consent_records:
                old_record = self._consent_records[consent_id]
                new_record = old_record.withdraw()
                self._consent_records[consent_id] = new_record
                return new_record
        return None

    def check_consent(self, subject_id: SubjectId, consent_type: str) -> bool:
        """Vérifie si un sujet a donné un consentement actif."""
        with self._lock:
            for record in self._consent_records.values():
                if record.subject_id == subject_id and record.consent_type == consent_type:
                    return record.is_active()
        return False

    def process_pending_actions(self) -> Dict[str, int]:
        """Traite les actions RGPD en attente (anonymisation, suppression)."""
        results = {"anonymized": 0, "deleted": 0, "errors": 0}

        with self._lock:
            for _subject_id, record in list(self._retention_records.items()):
                try:
                    if record.should_anonymize():
                        # Anonymisation à implémenter avec repository
                        results["anonymized"] += 1

                    if record.should_delete():
                        # Suppression à implémenter avec repository
                        results["deleted"] += 1

                except Exception:
                    results["errors"] += 1

        return results

    def get_retention_record(self, subject_id: SubjectId) -> Optional[DataRetentionRecord]:
        """Récupère le record de rétention d'un sujet."""
        with self._lock:
            return self._retention_records.get(subject_id)

    def get_subject_consents(self, subject_id: SubjectId) -> List[ConsentRecord]:
        """Récupère tous les consentements d'un sujet."""
        with self._lock:
            return [record for record in self._consent_records.values() if record.subject_id == subject_id]


class GDPRService:
    """Service RGPD avec logique métier."""

    def __init__(self, pipeline: Optional[GDPRPipeline] = None) -> None:
        self._pipeline = pipeline or GDPRPipeline()

    def handle_right_to_erasure(self, subject_id: SubjectId, reason: str = "User request") -> Dict[str, Any]:
        """Traite une demande de droit à l'oubli."""
        # Enregistrer la demande
        retention_record = self._pipeline.request_data_deletion(subject_id, reason)

        return {
            "status": "pending",
            "subject_id": subject_id.value,
            "anonymization_scheduled": retention_record.anonymization_date.isoformat(),
            "deletion_scheduled": retention_record.scheduled_deletion_date.isoformat(),
            "reference_id": hashlib.sha256(
                f"{subject_id.value}:{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16],
        }

    def handle_data_export(self, subject: Subject) -> Dict[str, Any]:
        """Traite une demande d'export de données."""
        return self._pipeline.export_subject_data(subject)

    def handle_consent_withdrawal(self, subject_id: SubjectId, consent_type: str) -> bool:
        """Traite un retrait de consentement."""
        # Trouver le consentement actif
        with self._pipeline._lock:
            for consent_id, record in self._pipeline._consent_records.items():
                if record.subject_id == subject_id and record.consent_type == consent_type and record.is_active():
                    self._pipeline.withdraw_consent(consent_id)
                    return True
        return False

    def process_automated_actions(self) -> Dict[str, int]:
        """Traite les actions automatisées (anonymisation, suppression)."""
        return self._pipeline.process_pending_actions()

    def get_compliance_status(self, subject_id: SubjectId) -> Dict[str, Any]:
        """Retourne le statut de conformité RGPD d'un sujet."""
        retention_record = self._pipeline.get_retention_record(subject_id)
        consents = self._pipeline.get_subject_consents(subject_id)

        return {
            "subject_id": subject_id.value,
            "retention_status": retention_record.status.value if retention_record else "not_managed",
            "anonymization_date": retention_record.anonymization_date.isoformat()
            if retention_record and retention_record.anonymization_date
            else None,
            "deletion_date": retention_record.deletion_date.isoformat()
            if retention_record and retention_record.deletion_date
            else None,
            "active_consents": [record.consent_type for record in consents if record.is_active()],
            "total_consents": len(consents),
        }


# Factory pour créer des configurations GDPR courantes
class GDPRFactory:
    """Factory pour créer des configurations GDPR."""

    @staticmethod
    def create_standard_pipeline() -> GDPRPipeline:
        """Crée un pipeline GDPR standard."""
        return GDPRPipeline(anonymization_delay_days=30, hard_delete_delay_days=365)

    @staticmethod
    def create_strict_pipeline() -> GDPRPipeline:
        """Crée un pipeline GDPR strict (délais plus courts)."""
        return GDPRPipeline(anonymization_delay_days=7, hard_delete_delay_days=90)

    @staticmethod
    def create_compliant_pipeline() -> GDPRService:
        """Crée un service GDPR conforme aux recommandations."""
        pipeline = GDPRFactory.create_standard_pipeline()
        return GDPRService(pipeline)
