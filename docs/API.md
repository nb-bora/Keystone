# Documentation API Aegis IAM

## 🎯 Introduction

L'API Aegis IAM est une API RESTful conçue selon les principes de la Clean Architecture, offrant une interface unifiée pour la gestion des identités, de l'authentification et du contrôle d'accès.

## 🌐 Base URL

- **Développement** : `http://localhost:8000`
- **Production** : `https://api.aegis-iam.com`

## 📚 Version de l'API

- **Version actuelle** : `v1`
- **Format** : `/api/v1/{resource}`

## 🔑 Authentification

Pour les endpoints qui nécessitent une authentification, incluez le token dans le header :

```http
Authorization: Bearer {access_token}
```

## 📋 Endpoints Disponibles

### Endpoints de Santé (Infrastructure)

#### GET /health/live
Vérifie que le processus Python est vivant. Ne dépend d'aucune base de données.

**Réponse :**
```json
{
  "status": "ok",
  "service": "aegis-api",
  "timestamp": "2026-09-03T10:00:00Z"
}
```

#### GET /health/ready
Vérifie la disponibilité réelle des dépendances (PostgreSQL, Redis).

**Réponse (200 OK) :**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok"
  },
  "timestamp": "2026-09-03T10:00:00Z"
}
```

**Réponse (503 Service Unavailable) :**
```json
{
  "status": "error",
  "checks": {
    "database": "error: connection refused"
  },
  "timestamp": "2026-09-03T:10:00:00Z"
}
```

#### GET /health/startup
Vérifie que l'initialisation est terminée.

**Réponse :**
```json
{
  "status": "ok",
  "initialized": true,
  "environment": "production"
}
```

#### GET /metrics
Expose les métriques Prometheus.

**Réponse :**
```json
{
  "aegis_info": {
    "version": "0.1.0",
    "environment": "production"
  },
  "aegis_pending_audit_events": 12,
  "timestamp": "2026-09-03T10:00:00Z"
}
```

### Endpoints de Gestion des Sujets

#### POST /api/v1/subjects/human
Enregistre une nouvelle identité humaine.

**Request Body :**
```json
{
  "email": "alice.smith@enterprise.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "tenant_id": "tenant-corp-01",
  "initial_permissions": ["document:read", "document:edit", "report:generate"]
}
```

**Réponse (201 Created) :**
```json
{
  "id": "sub-human-abc123",
  "subject_type": "HUMAN",
  "tenant_id": "tenant-corp-01",
  "is_active": true,
  "created_at": "2026-09-03T10:00:00Z"
}
```

**Erreurs possibles :**
- `400 Bad Request` : Email invalide ou déjà existant
- `422 Unprocessable Entity` : Données invalides

#### POST /api/v1/subjects/service-account
Enregistre un Service Account M2M.

**Request Body :**
```json
{
  "client_id": "m2m-billing-service",
  "tenant_id": "tenant-corp-01",
  "initial_scopes": ["invoices:read", "invoices:write", "payments:process"]
}
```

**Réponse (201 Created) :**
```json
{
  "id": "sa-m2m-billing-service",
  "subject_type": "SERVICE_ACCOUNT",
  "tenant_id": "tenant-corp-01",
  "is_active": true,
  "created_at": "2026-09-03T10:00:00Z"
}
```

#### POST /api/v1/subjects/ai-agent
Enregistre un Agent IA.

**Request Body :**
```json
{
  "agent_name": "DataAnalystAgent",
  "owner_identity_id": "sub-human-12345",
  "max_autonomy_level": 2,
  "initial_permissions": ["dataset:read", "analytics:query"]
}
```

**Réponse (201 Created) :**
```json
{
  "id": "agent-007",
  "subject_type": "AI_AGENT",
  "tenant_id": null,
  "is_active": true,
  "created_at": "2026-09-03T10:00:00Z"
}
```

### Endpoints de Contrôle d'Accès

#### POST /api/v1/auth/evaluate
Évalue une permission d'accès en temps réel.

**Request Body :**
```json
{
  "subject_id": "sub-human-12345",
  "action": "document:edit",
  "resource_id": "doc-99823",
  "context_attributes": {
    "ip_address": "192.168.1.50",
    "device_type": "corporate_laptop"
  }
}
```

**Réponse (200 OK) :**
```json
{
  "is_allowed": true,
  "effect": "ALLOW",
  "action": "document:edit",
  "reason": "Permission 'document:edit' accordée directement à l'identité humaine.",
  "evaluated_at": "2026-09-03T10:00:00Z"
}
```

**Réponse (404 Not Found) :**
```json
{
  "detail": "Sujet 'sub-human-12345' introuvable."
}
```

### Endpoints d'Audit et Compliance

#### GET /api/v1/audit/events
Inspecte les événements d'audit Outbox (RGPD).

**Query Parameters :**
- `batch_size` (optionnel) : Nombre d'événements à retourner (défaut: 50)

**Réponse (200 OK) :**
```json
[
  {
    "event_id": "evt-abc123",
    "event_type": "SUBJECT_REGISTERED",
    "aggregate_id": "sub-human-12345",
    "details": {
      "event_id": "evt-abc123",
      "event_type": "SUBJECT_REGISTERED",
      "aggregate_id": "sub-human-12345",
      "subject_type": "HUMAN",
      "email_anonymized": "a***@enterprise.com",
      "occurred_at": "2026-09-03T10:00:00Z"
    },
    "occurred_at": "2026-09-03T10:00:00Z"
  }
]
```

## 🔧 Exemples d'Utilisation

### Exemple 1 : Création et Évaluation d'Utilisateur

```python
import requests

# 1. Créer un utilisateur
response = requests.post('http://localhost:8000/api/v1/subjects/human', json={
    "email": "alice@example.com",
    "first_name": "Alice",
    "last_name": "Smith",
    "initial_permissions": ["document:read", "document:write"]
})

user_data = response.json()
user_id = user_data['id']
print(f"Utilisateur créé : {user_id}")

# 2. Évaluer une permission
response = requests.post('http://localhost:8000/api/v1/auth/evaluate', json={
    "subject_id": user_id,
    "action": "document:read",
    "resource_id": "doc-123"
})

auth_result = response.json()
print(f"Accès autorisé : {auth_result['is_allowed']}")
print(f"Raison : {auth_result['reason']}")
```

### Exemple 2 : Gestion Multi-Tenant

```python
# Créer un utilisateur dans un tenant spécifique
response = requests.post('http://localhost:8000/api/v1/subjects/human', json={
    "email": "bob@company.com",
    "first_name": "Bob",
    "last_name": "Johnson",
    "tenant_id": "tenant-company-01",
    "initial_permissions": ["project:create"]
})

user_data = response.json()
print(f"Utilisateur créé dans tenant : {user_data['tenant_id']}")
```

### Exemple 3 : Évaluation avec Contexte ABAC

```python
# Évaluation avec contexte IP et temps
response = requests.post('http://localhost:8000/api/v1/auth/evaluate', json={
    "subject_id": "sub-human-12345",
    "action": "sensitive:operation",
    "resource_id": "resource-secret",
    "context_attributes": {
        "ip_address": "192.168.1.50",
        "time": "14:30",
        "location": "office"
    }
})

auth_result = response.json()
# Le moteur ABAC peut refuser basé sur l'IP ou l'heure
print(f"Décision : {auth_result['effect']}")
```

### Exemple 4 : Agent IA avec Autonomie

```python
# Créer un agent IA avec autonomie semi-autonome
response = requests.post('http://localhost:8000/api/v1/subjects/ai-agent', json={
    "agent_name": "AutoCoder",
    "owner_identity_id": "sub-human-admin",
    "max_autonomy_level": 2,  # Semi-autonome
    "initial_permissions": ["code:read", "code:write", "deploy:staging"]
})

agent_data = response.json()
print(f"Agent IA créé : {agent_data['id']}")
```

## 📊 Codes d'Erreur

### Codes HTTP Standards

- `200 OK` : Requête réussie
- `201 Created` : Ressource créée avec succès
- `400 Bad Request` : Données invalides dans la requête
- `401 Unauthorized` : Authentification requise ou invalide
- `403 Forbidden` : Permissions insuffisantes
- `404 Not Found` : Ressource introuvable
- `422 Unprocessable Entity` : Données valides mais traitement impossible
- `429 Too Many Requests` : Rate limit dépassé
- `500 Internal Server Error` : Erreur serveur inattendue
- `503 Service Unavailable` : Service temporairement indisponible

### Format d'Erreur

```json
{
  "detail": "Description détaillée de l'erreur",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2026-9-03T10:00:00Z",
  "request_id": "req-uuid-99823-abc"
}
```

## 🔄 Async Operations

Certaines opérations longues peuvent être asynchrones. Dans ce cas, l'API retourne :

```json
{
  "operation_id": "op-async-123",
  "status": "processing",
  "resource_url": "/api/v1/operations/op-async-123"
}
```

### Polling des Opérations

```python
# Lancer une opération
response = requests.post('http://localhost:8000/api/v1/subjects/batch-create', json={
    "subjects": [...]
})

operation_data = response.json()
operation_id = operation_data['operation_id']

# Poller le statut
while True:
    response = requests.get(f'http://localhost:8000/api/v1/operations/{operation_id}')
    status_data = response.json()
    
    if status_data['status'] == 'completed':
        print("Opération terminée")
        break
    elif status_data['status'] == 'failed':
        print(f"Opération échouée : {status_data['error']}")
        break
    
    time.sleep(2)
```

## 🎨 Personnalisation de l'API

### Configuration via Variables d'Environnement

L'API peut être personnalisée via le fichier `aegis.config.yaml` :

```yaml
api:
  framework: fastapi
  host: 0.0.0.0
  port: 8000
  docs_enabled: true
  docs_url: /docs
  redoc_url: /redoc
```

### CORS Configuration

```yaml
security:
  cors:
    enabled: true
    origins: "https://example.com,https://app.example.com"
    allow_credentials: true
```

## 📈 Rate Limiting

L'API applique un rate limiting configurable :

```yaml
security:
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst: 10
```

En cas de dépassement, retourne `429 Too Many Requests` avec header :

```
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1620000000
```

## 🔒 Sécurité

### Headers de Sécurité

Toutes les réponses incluent les headers suivants :

```
X-Request-ID: req-uuid-99823-abc
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### Validation des Entrées

Toutes les entrées sont validées selon les règles configurées dans `aegis.config.yaml` :

```yaml
validation:
  strict_mode: true
  email:
    regex: "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
    check_deliverability: false
  password:
    min_length: 8
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_special_chars: true
```

## 📚 SDK Clients

### Python SDK

```python
from aegis.sdk.client import AegisClient, AegisContainer

# Initialisation
container = AegisContainer()
client = AegisClient(container)

# Créer un utilisateur
human = client.register_human(
    email="alice@example.com",
    first_name="Alice",
    last_name="Smith",
    initial_permissions={"document:read", "document:write"}
)

# Évaluer une permission
if client.can(human.id.value, "document:read"):
    print("Accès autorisé")
```

### JavaScript SDK (Futur)

```javascript
import { AegisClient } from '@aegis/sdk';

const client = new AegisClient({
  baseURL: 'https://api.aegis-iam.com',
  apiKey: 'your-api-key'
});

// Créer un utilisateur
const user = await client.registerHuman({
  email: 'alice@example.com',
  firstName: 'Alice',
  lastName: 'Smith',
  initialPermissions: ['document:read']
});

// Évaluer une permission
const canRead = await client.can(user.id, 'document:read');
console.log('Can read:', canRead);
```

## 🎯 Meilleures Pratiques

### Requêtes Idempotentes

Pour les opérations qui peuvent être répétées, utilisez le header `Idempotency-Key` :

```http
POST /api/v1/subjects/human
Idempotency-Key: unique-key-12345
```

### Pagination

Pour les endpoints qui retournent des listes, utilisez les paramètres :

- `page` : Numéro de page (défaut: 1)
- `per_page` : Éléments par page (défaut: 20, max: 100)

```http
GET /api/v1/subjects?page=2&per_page=50
```

**Réponse paginée :**
```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

### Filtrage et Tri

Pour les endpoints de liste, utilisez les paramètres de filtrage :

```http
GET /api/v1/subjects?subject_type=HUMAN&is_active=true&sort_by=created_at&order=desc
```

## 🚀 Déploiement

### Docker

```bash
# Image officielle
docker pull aegisiam/aegis-api:latest

# Lancer avec Docker Compose
docker-compose up -d
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aegis-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aegis-api
  template:
    metadata:
      labels:
        app: aegis-api
    spec:
      containers:
      - name: aegis-api
        image: aegisiam/aegis-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: aegis-secrets
              key: database-url
```

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/startup
```

### Metrics Prometheus

```bash
curl http://localhost:8000/metrics
```

Les métriques disponibles :
- `aegis_pending_audit_events` : Nombre d'événements en attente
- `aegis_total_subjects` : Nombre total de sujets
- `aegis_authorization_decisions_total` : Nombre total de décisions d'autorisation

## 🔄 Changelog de l'API

### Version 0.1.0 (Actuelle)
- ✅ Endpoints de santé (Liveness, Readiness, Startup)
- ✅ Gestion des sujets (Human, Service Account, AI Agent)
- ✅ Évaluation d'autorisation
- ✅ Audit des événements
- ✅ Policy Engines RBAC, ABAC, ReBAC
- ✅ Multi-tenancy
- ✅ GDPR Compliance

### Version Future 0.2.0 (Planifié)
- WebSockets pour notifications temps réel
- Bulk operations pour performances
- Advanced filtering et search
- GraphQL API alternative

## 📞 Support

- **Documentation** : https://docs.aegis-iam.com
- **GitHub Issues** : https://github.com/aegis/keystone/issues
- **Email** : support@aegis-iam.com

---

**Aegis IAM API** - *Universal, Pluggable & Domain-Driven Identity & Access Management*