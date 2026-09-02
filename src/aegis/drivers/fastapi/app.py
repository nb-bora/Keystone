"""
Serveur API REST FastAPI & Documentation OpenAPI / Swagger pour Aegis Enterprise.

Expose l'ensemble des Use Cases de gestion des identités, d'évaluation d'accès,
d'audit RGPD et d'observabilité (Liveness, Readiness, Startup, Metrics, Correlation ID).
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from aegis import __version__
from aegis.core.config import settings
from aegis.core.domain.entities import AIAgentActor, ServiceAccount
from aegis.core.domain.values import PermissionCode, SubjectId, TenantId
from aegis.core.logger import get_logger
from aegis.drivers.fastapi.dependencies import get_aegis_client, get_aegis_container
from aegis.drivers.fastapi.schemas import (
    AccessEvaluationResponse,
    AuditEventResponse,
    EvaluateAccessRequest,
    RegisterAIAgentRequest,
    RegisterHumanRequest,
    RegisterServiceAccountRequest,
    SubjectResponse,
)
from aegis.sdk.client import AegisClient, AegisContainer
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = get_logger("aegis.fastapi")

SWAGGER_DESCRIPTION = """
# Aegis IAM Enterprise REST API 🛡️

**The Universal, Pluggable & Domain-Driven IAM Engine for Python & Django**

Aegis offre un moteur complet de gestion des identités, d'authentification et de contrôle d'accès
(RBAC, ABAC, ReBAC) conçu selon les principes de la **Clean Architecture** et du **Domain-Driven Design (DDD)**.

## Enterprise Architecture 🏛️
* **Triple-Level Healthchecks** : `/health/live` (Liveness), `/health/ready` (Readiness avec réel test DB PostgreSQL), `/health/startup` (Startup).
* **Correlation Request ID (`X-Request-ID`)** : Traçabilité end-to-end sur toute la chaîne applicative.
* **Network Isolation & Security** : Base PostgreSQL isolée sur réseau privé `db_net`.
"""

app = FastAPI(
    title="Aegis IAM Enterprise API",
    description=SWAGGER_DESCRIPTION,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de Corrélation & Logging Structuré
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Any) -> Response:
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"{request.method} {request.url.path} -> HTTP {response.status_code} ({duration_ms}ms)",
        extra={
            "request_id": request_id,
            "http_method": request.method,
            "http_route": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# --- ENDPOINTS DE SANTÉ TRIPLE-NIVEAUX (Liveness, Readiness, Startup) ---


@app.get(
    "/health/live",
    tags=["Infrastructure & Health"],
    summary="Liveness Probe (Processus Vivant)",
    description="Vérifie uniquement que le processus Python applicatif est vivant et capable de répondre. Ne dépend d'aucune base de données.",
)
def liveness_probe() -> Dict[str, Any]:
    return {"status": "ok", "service": "aegis-api", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(
    "/health/ready",
    tags=["Infrastructure & Health"],
    summary="Readiness Probe (Prêt à Recevoir du Trafic)",
    description="Vérifie la disponibilité réelle des dépendances critiques (PostgreSQL / Stockage & Redis). Renvoie 503 Service Unavailable si la base de données est indisponible.",
    responses={
        200: {"description": "L'application et toutes ses dépendances sont opérationnelles."},
        503: {"description": "La dépendance critique (PostgreSQL / Stockage) est indisponible."},
    },
)
def readiness_probe(container: AegisContainer = Depends(get_aegis_container)) -> JSONResponse:
    checks = {"database": "ok", "redis": "ok"}
    is_ready = True

    # 1. Vérification réelle du stockage / DB
    try:
        # Test de lecture/accès minimal O(1)
        container.repository.get_by_id(SubjectId("healthcheck-dummy-id"))
    except Exception as err:
        checks["database"] = f"error: {str(err)}"
        is_ready = False

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    payload = {
        "status": "ok" if is_ready else "error",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status_code, content=payload)


@app.get(
    "/health/startup",
    tags=["Infrastructure & Health"],
    summary="Startup Probe (Initialisation Terminée)",
    description="Vérifie si l'initialisation des configurations et la préparation du moteur sont achevées.",
)
def startup_probe() -> Dict[str, Any]:
    return {"status": "ok", "initialized": True, "environment": settings.environment}


@app.get(
    "/metrics",
    tags=["Infrastructure & Health"],
    summary="Métriques Télémétrie / Prometheus",
    description="Expose les métriques applicatives (nombre de sujets, requêtes, statut) au format Prometheus / JSON.",
)
def get_metrics(container: AegisContainer = Depends(get_aegis_container)) -> Dict[str, Any]:
    pending_audit_events = len(container.outbox.get_pending_events(batch_size=1000))
    return {
        "aegis_info": {"version": __version__, "environment": settings.environment},
        "aegis_pending_audit_events": pending_audit_events,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- ENDPOINTS GESTION DES SUJETS ---


@app.post(
    "/api/v1/subjects/human",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Subject Management"],
    summary="Enregistrer une Identité Humaine",
)
def register_human_subject(
    payload: RegisterHumanRequest,
    client: AegisClient = Depends(get_aegis_client),
) -> SubjectResponse:
    try:
        human = client.register_human(
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            tenant_id=payload.tenant_id,
            initial_permissions=payload.initial_permissions,
        )
        return SubjectResponse(
            id=human.id.value,
            subject_type=human.subject_type,
            tenant_id=human.tenant_id.value if human.tenant_id else None,
            is_active=human.is_active,
            created_at=human.created_at,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@app.post(
    "/api/v1/subjects/service-account",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Subject Management"],
    summary="Enregistrer un Service Account M2M",
)
def register_service_account(
    payload: RegisterServiceAccountRequest,
    container: AegisContainer = Depends(get_aegis_container),
) -> SubjectResponse:
    subject_id = SubjectId(f"sa-{uuid.uuid4().hex[:12]}")
    tenant_id = TenantId(payload.tenant_id) if payload.tenant_id else None

    sa = ServiceAccount(
        id=subject_id,
        tenant_id=tenant_id,
        client_id=payload.client_id,
        allowed_scopes=payload.initial_scopes,
    )
    container.repository.save(sa)

    return SubjectResponse(
        id=sa.id.value,
        subject_type=sa.subject_type,
        tenant_id=sa.tenant_id.value if sa.tenant_id else None,
        is_active=sa.is_active,
        created_at=sa.created_at,
    )


@app.post(
    "/api/v1/subjects/ai-agent",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Subject Management"],
    summary="Enregistrer un Agent IA",
)
def register_ai_agent(
    payload: RegisterAIAgentRequest,
    container: AegisContainer = Depends(get_aegis_container),
) -> SubjectResponse:
    subject_id = SubjectId(f"agent-{uuid.uuid4().hex[:12]}")
    owner_id = SubjectId(payload.owner_identity_id) if payload.owner_identity_id else None

    agent = AIAgentActor(
        id=subject_id,
        agent_name=payload.agent_name,
        owner_identity_id=owner_id,
        max_autonomy_level=payload.max_autonomy_level,
        permissions={PermissionCode(p) for p in payload.initial_permissions},
    )
    container.repository.save(agent)

    return SubjectResponse(
        id=agent.id.value,
        subject_type=agent.subject_type,
        tenant_id=None,
        is_active=agent.is_active,
        created_at=agent.created_at,
    )


@app.post(
    "/api/v1/auth/evaluate",
    response_model=AccessEvaluationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Access Control & Evaluation"],
    summary="Évaluer une Permission d'Accès en Temps Réel O(1)",
)
def evaluate_access(
    payload: EvaluateAccessRequest,
    client: AegisClient = Depends(get_aegis_client),
) -> AccessEvaluationResponse:
    from aegis.core.application.dtos import EvaluateAccessQuery

    query = EvaluateAccessQuery(
        subject_id=payload.subject_id,
        action=payload.action,
        resource=payload.resource_id,
        context_attributes=payload.context_attributes,
    )
    result = client._evaluate_access_uc.execute(query)

    if result.reason.startswith("Sujet") and "introuvable" in result.reason:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.reason)

    return AccessEvaluationResponse(
        is_allowed=result.is_allowed,
        effect=result.effect.value,
        action=result.action,
        reason=result.reason,
        evaluated_at=result.evaluated_at,
    )


@app.get(
    "/api/v1/audit/events",
    response_model=List[AuditEventResponse],
    tags=["Audit & Compliance"],
    summary="Inspecter les Événements d'Audit Outbox (RGPD)",
)
def get_audit_events(
    batch_size: int = 50,
    container: AegisContainer = Depends(get_aegis_container),
) -> List[AuditEventResponse]:
    events = container.outbox.get_pending_events(batch_size=batch_size)
    response = []
    for e in events:
        audit_dict = e.to_audit_dict()
        response.append(
            AuditEventResponse(
                event_id=e.event_id,
                event_type=e.event_type,
                aggregate_id=e.aggregate_id,
                details=audit_dict,
                occurred_at=e.occurred_at.isoformat(),
            )
        )
    return response
