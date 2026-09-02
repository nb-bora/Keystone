"""
Schémas Pydantic v2 pour l'API REST FastAPI d'Aegis.

Contient la validation stricte des données d'entrée/sortie avec métadonnées
Swagger / OpenAPI ultra-détaillées (exemples JSON, descriptions et contraintes).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, EmailStr


class RegisterHumanRequest(BaseModel):
    """Payload de requête pour l'enregistrement d'une identité humaine."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "alice.smith@enterprise.com",
                "first_name": "Alice",
                "last_name": "Smith",
                "tenant_id": "tenant-corp-01",
                "initial_permissions": ["document:read", "document:edit", "report:generate"],
            }
        }
    )

    email: EmailStr = Field(..., description="Adresse email unique et valide de l'utilisateur.")
    first_name: str = Field(default="", description="Prénom de l'utilisateur.")
    last_name: str = Field(default="", description="Nom de famille de l'utilisateur.")
    tenant_id: Optional[str] = Field(default=None, description="Identifiant du tenant / de l'organisation.")
    initial_permissions: Set[str] = Field(
        default_factory=set, description="Ensemble initial des codes de permissions assignés."
    )


class RegisterServiceAccountRequest(BaseModel):
    """Payload de requête pour l'enregistrement d'un Service Account M2M."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": "m2m-billing-service",
                "tenant_id": "tenant-corp-01",
                "initial_scopes": ["invoices:read", "invoices:write", "payments:process"],
            }
        }
    )

    client_id: str = Field(..., description="Identifiant unique du client M2M / microservice.")
    tenant_id: Optional[str] = Field(default=None, description="Identifiant du tenant.")
    initial_scopes: Set[str] = Field(default_factory=set, description="Scopes M2M autorisés.")


class RegisterAIAgentRequest(BaseModel):
    """Payload de requête pour l'enregistrement d'un Agent IA."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "DataAnalystAgent",
                "owner_identity_id": "sub-human-12345",
                "max_autonomy_level": 2,
                "initial_permissions": ["dataset:read", "analytics:query"],
            }
        }
    )

    agent_name: str = Field(..., description="Nom de l'agent IA.")
    owner_identity_id: Optional[str] = Field(default=None, description="ID de l'identité humaine propriétaire.")
    max_autonomy_level: int = Field(
        default=1, ge=1, le=3, description="Niveau d'autonomie (1: Supervisé, 2: Semi-autonome, 3: Totalement autonome)."
    )
    initial_permissions: Set[str] = Field(default_factory=set, description="Permissions accordées à l'agent IA.")


class EvaluateAccessRequest(BaseModel):
    """Payload de requête pour l'évaluation de permission temps réel en O(1)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject_id": "sub-human-12345",
                "action": "document:edit",
                "resource_id": "doc-99823",
                "context_attributes": {
                    "ip_address": "192.168.1.50",
                    "device_type": "corporate_laptop",
                },
            }
        }
    )

    subject_id: str = Field(..., description="Identifiant unique du sujet (Humain, M2M, Agent IA).")
    action: str = Field(..., description="Code de l'action/permission demandée (ex: 'document:edit').")
    resource_id: Optional[str] = Field(default=None, description="Identifiant optionnel de la ressource cible.")
    context_attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Attributs de contexte pour l'évaluation ABAC (IP, heure, risquetier)."
    )


class AccessEvaluationResponse(BaseModel):
    """Payload de réponse pour l'évaluation d'accès."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_allowed": True,
                "effect": "ALLOW",
                "action": "document:edit",
                "reason": "Permission 'document:edit' accordée directement à l'identité humaine.",
                "evaluated_at": "2026-09-02T15:30:00Z",
            }
        }
    )

    is_allowed: bool = Field(..., description="True si l'accès est accordé.")
    effect: str = Field(..., description="Effet de la politique: ALLOW, DENY, CONDITIONAL.")
    action: str = Field(..., description="Code de l'action évaluée.")
    reason: str = Field(..., description="Explication explicite de la décision de sécurité.")
    evaluated_at: datetime = Field(..., description="Horodatage ISO de l'évaluation.")


class SubjectResponse(BaseModel):
    """Payload de réponse générique pour un Sujet enregistré."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "sub-human-12345",
                "subject_type": "HUMAN",
                "tenant_id": "tenant-corp-01",
                "is_active": True,
                "created_at": "2026-09-02T15:30:00Z",
            }
        }
    )

    id: str = Field(..., description="Identifiant du sujet.")
    subject_type: str = Field(..., description="Type discriminant: HUMAN, SERVICE_ACCOUNT, API_KEY, AI_AGENT.")
    tenant_id: Optional[str] = Field(default=None, description="Tenant rattaché.")
    is_active: bool = Field(..., description="Statut d'activation de l'accès.")
    created_at: datetime = Field(..., description="Horodatage de création.")


class AuditEventResponse(BaseModel):
    """Payload de réponse pour un événement d'audit de l'Outbox."""

    event_id: str = Field(..., description="Identifiant unique de l'événement.")
    event_type: str = Field(..., description="Type d'événement (ex: SUBJECT_REGISTERED).")
    aggregate_id: str = Field(..., description="ID de l'aggregate concerné.")
    details: Dict[str, Any] = Field(..., description="Métadonnées d'audit (sans PII en clair).")
    occurred_at: str = Field(..., description="Horodatage ISO de survenance.")


class HealthResponse(BaseModel):
    """Réponse de santé du système et des composants d'infrastructure."""

    status: str = Field(..., description="Statut global: 'healthy' ou 'unhealthy'.")
    version: str = Field(..., description="Version du package Aegis.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
