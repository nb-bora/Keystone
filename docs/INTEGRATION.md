# Tutoriels d'Intégration Aegis IAM

## 📚 Guide d'Intégration Framework

Aegis IAM est conçu pour être intégré facilement dans différents frameworks Python grâce à son architecture Clean Architecture et ses adaptateurs pluggables.

## 🚀 Intégration avec FastAPI

### Installation

```bash
pip install aegis-iam[fastapi,sqlalchemy]
```

### Configuration de Base

```python
from fastapi import FastAPI, Depends, HTTPException
from aegis.sdk.client import AegisClient, AegisContainer
from aegis.drivers.fastapi.dependencies import get_aegis_client

app = FastAPI(title="Mon API avec Aegis IAM")

# Initialisation du conteneur Aegis
container = AegisContainer()
container.configure(
    storage_driver="sqlalchemy",
    database_url="postgresql://user:pass@localhost/aegis_iam_db"
)

# Injection de dépendance
@app.get("/api/v1/protected")
async def protected_endpoint(client: AegisClient = Depends(get_aegis_client)):
    """Endpoint protégé par Aegis IAM."""
    # L'authentification est gérée par le middleware FastAPI
    # L'autorisation est vérifiée ici
    subject_id = "current-user-id"  # Récupéré depuis le JWT/token
    
    if not client.can(subject_id, "document:read"):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return {"message": "Access granted"}
```

### Middleware d'Authentification

```python
from fastapi import Request
from aegis.core.domain.authentication import AuthenticationManager, AuthenticationFactory
from aegis.drivers.inmemory import Pbkdf2PasswordHasher

# Créer le manager d'authentification
hasher = Pbkdf2PasswordHasher(iterations=100000)
auth_manager = AuthenticationFactory.create_default_manager(hasher)

@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """Middleware d'authentification Aegis."""
    # Extraire les credentials depuis le header Authorization
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        
        # Valider le token avec Aegis
        # Pour cet exemple, on suppose un token JWT
        subject_id = validate_jwt_token(token)
        
        # Ajouter l'ID du sujet au state de la requête
        request.state.subject_id = subject_id
    
    response = await call_next(request)
    return response
```

### Intégration avec SQLAlchemy

```python
from sqlalchemy import create_engine
from aegis.drivers.sqlalchemy.driver import SQLAlchemySubjectRepository

# Configuration de la base de données
engine = create_engine("postgresql://user:pass@localhost/aegis_iam_db")

# Créer le repository Aegis
subject_repo = SQLAlchemySubjectRepository(engine)

# Utilisation dans votre application
@app.post("/api/v1/users")
async def create_user(email: str, password: str):
    """Créer un utilisateur avec Aegis."""
    from aegis.core.domain.entities import HumanIdentity
    from aegis.core.domain.values import EmailAddress, SubjectId, PermissionCode
    
    human = HumanIdentity(
        id=SubjectId("user-123"),
        email=EmailAddress(email),
        first_name="John",
        last_name="Doe",
        permissions={PermissionCode("document:read")}
    )
    
    subject_repo.save(human)
    return {"user_id": human.id.value}
```

## 🐍 Intégration avec Django

### Installation

```bash
pip install aegis-iam[django]
```

### Configuration dans settings.py

```python
# settings.py

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'aegis.drivers.django',  # Driver Django Aegis
    # ... vos autres apps
]

# Configuration Aegis
AEGIS_CONFIG = {
    'storage_driver': 'django',
    'policy_engines': {
        'primary': 'rbac',
        'cascade': ['abac', 'rebac']
    },
    'tenancy': {
        'mode': 'hierarchical',
        'isolation_type': 'row_level'
    }
}
```

### Middleware Django

```python
# middleware.py

from django.conf import settings
from aegis.sdk.client import AegisClient, AegisContainer

class AegisAuthenticationMiddleware:
    """Middleware d'authentification Aegis pour Django."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Initialiser Aegis
        self.container = AegisContainer()
        self.container.configure(
            storage_driver="django"
        )
        self.client = AegisClient(self.container)
    
    def __call__(self, request):
        """Traiter chaque requête."""
        # Extraire le token depuis le header Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            
            # Valider le token et récupérer le subject_id
            subject_id = self.validate_token(token)
            
            # Ajouter au request
            request.aegis_subject_id = subject_id
            request.aegis_client = self.client
        
        response = self.get_response(request)
        return response
    
    def validate_token(self, token: str) -> str:
        """Valider le token et retourner l'ID du sujet."""
        # Implémenter votre logique de validation JWT
        # Pour l'exemple, on suppose que le token contient l'ID
        return "user-123"  # À remplacer par votre logique
```

### Décorateur d'Autorisation

```python
# decorators.py

from functools import wraps
from django.http import HttpResponseForbidden
from aegis.sdk.client import AegisClient

def aegis_required(permission: str):
    """Décorateur d'autorisation Aegis."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Récupérer le client Aegis depuis la requête
            client = getattr(request, 'aegis_client', None)
            subject_id = getattr(request, 'aegis_subject_id', None)
            
            if not client or not subject_id:
                return HttpResponseForbidden("Authentication required")
            
            # Vérifier la permission
            if not client.can(subject_id, permission):
                return HttpResponseForbidden("Permission denied")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

### Utilisation dans les Views Django

```python
# views.py

from django.http import JsonResponse
from aegis.drivers.django.models import AegisSubject
from aegis.core.domain.entities import HumanIdentity
from aegis.core.domain.values import EmailAddress, SubjectId, PermissionCode

from .decorators import aegis_required

@aegis_required("document:read")
def protected_view(request):
    """Vue protégée par Aegis."""
    return JsonResponse({"message": "Access granted"})

def create_user_view(request):
    """Créer un utilisateur avec Aegis."""
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Créer l'entité de domaine Aegis
        human = HumanIdentity(
            id=SubjectId("user-123"),
            email=EmailAddress(email),
            first_name=first_name,
            last_name=last_name,
            permissions={PermissionCode("document:read")}
        )
        
        # Sauvegarder via le driver Django
        # Le driver Django gère la conversion automatiquement
        # Pour l'instant, nous utilisons le SDK direct
        
        return JsonResponse({"user_id": human.id.value})
```

## 🌊 Intégration avec Flask

### Installation

```bash
pip install aegis-iam
```

### Configuration de Base

```python
from flask import Flask, request, jsonify
from aegis.sdk.client import AegisClient, AegisContainer

app = Flask(__name__)

# Initialisation Aegis
container = AegisContainer()
container.configure(
    storage_driver="inmemory"  # Pour le développement
)
client = AegisClient(container)

@app.before_request
def authenticate_request():
    """Authentifier chaque requête."""
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        
        # Valider le token
        subject_id = validate_token(token)
        
        # Stocker dans le contexte Flask
        flask.g.subject_id = subject_id

def validate_token(token: str) -> str:
    """Valider le token et retourner l'ID du sujet."""
    # Implémenter votre logique de validation
    return "user-123"

@app.route('/api/v1/protected')
def protected_endpoint():
    """Endpoint protégé par Aegis."""
    subject_id = getattr(flask.g, 'subject_id', None)
    
    if not subject_id:
        return jsonify({"error": "Authentication required"}), 401
    
    if not client.can(subject_id, "document:read"):
        return jsonify({"error": "Permission denied"}), 403
    
    return jsonify({"message": "Access granted"})
```

### Intégration avec Flask-SQLAlchemy

```python
from flask_sqlalchemy import SQLAlchemy
from aegis.drivers.sqlalchemy.driver import SQLAlchemySubjectRepository

db = SQLAlchemy(app)

# Utiliser l'engine SQLAlchemy Flask pour Aegis
aegis_repo = SQLAlchemySubjectRepository(db.engine)

@app.route('/api/v1/users', methods=['POST'])
def create_user():
    """Créer un utilisateur avec Aegis."""
    from aegis.core.domain.entities import HumanIdentity
    from aegis.core.domain.values import EmailAddress, SubjectId, PermissionCode
    
    data = request.get_json()
    
    human = HumanIdentity(
        id=SubjectId("user-123"),
        email=EmailAddress(data['email']),
        first_name=data['first_name'],
        last_name=data['last_name'],
        permissions={PermissionCode("document:read")}
    )
    
    aegis_repo.save(human)
    
    return jsonify({"user_id": human.id.value}), 201
```

## 🔧 Intégration avec des Microservices

### Architecture Multi-Service

Aegis IAM peut être déployé comme un service d'authentification centralisé :

```python
# Service Aegis (service centralisé)

from fastapi import FastAPI
from aegis.sdk.client import AegisClient, AegisContainer

app = FastAPI(title="Aegis IAM Service")

container = AegisContainer()
container.configure(
    storage_driver="sqlalchemy",
    database_url="postgresql://user:pass@aegis-db/aegis_iam_db"
)
client = AegisClient(container)

@app.post("/auth/evaluate")
async def evaluate_permission(subject_id: str, action: str, resource_id: str):
    """Évaluer une permission d'accès."""
    decision = client._evaluate_access_uc.execute(
        subject_id=subject_id,
        action=action,
        resource_id=resource_id
    )
    
    return {
        "is_allowed": decision.effect.value == "ALLOW",
        "effect": decision.effect.value,
        "reason": decision.reason
    }
```

### Client HTTP pour Microservices

```python
# Service Client (consommateur)

import httpx

class AegisClientHTTP:
    """Client HTTP pour le service Aegis."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client()
    
    def can(self, subject_id: str, action: str, resource_id: str) -> bool:
        """Vérifier une permission via HTTP."""
        response = self.client.post(
            f"{self.base_url}/auth/evaluate",
            json={
                "subject_id": subject_id,
                "action": action,
                "resource_id": resource_id
            }
        )
        
        result = response.json()
        return result["is_allowed"]

# Utilisation
aegis_client = AegisClientHTTP("http://aegis-service:8000")

if aegis_client.can("user-123", "document:read", "doc-456"):
    print("Accès autorisé")
```

## 🎯 Intégration avec des CLI Tools

### Application de Ligne de Commande

```python
import click
from aegis.sdk.client import AegisClient, AegisContainer

@click.group()
def cli():
    """CLI Aegis IAM."""
    pass

@cli.command()
@click.option('--email', required=True, help='Email de l\'utilisateur')
@click.option('--password', required=True, help='Mot de passe')
def register(email: str, password: str):
    """Enregistrer un nouvel utilisateur."""
    container = AegisContainer()
    container.configure(storage_driver="inmemory")
    client = AegisClient(container)
    
    human = client.register_human(
        email=email,
        first_name="",
        last_name="",
        initial_permissions={"document:read"}
    )
    
    click.echo(f"Utilisateur créé : {human.id.value}")

@cli.command()
@click.argument('subject_id')
@click.argument('action')
@click.argument('resource_id')
def check_permission(subject_id: str, action: str, resource_id: str):
    """Vérifier une permission."""
    container = AegisContainer()
    container.configure(storage_driver="inmemory")
    client = AegisClient(container)
    
    if client.can(subject_id, action, resource_id):
        click.echo("✓ Permission accordée")
    else:
        click.echo("✗ Permission refusée")

if __name__ == '__main__':
    cli()
```

## 📊 Intégration avec des Data Pipelines

### Pipeline Apache Airflow

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from aegis.sdk.client import AegisClient, AegisContainer
from datetime import datetime, timedelta

def check_permission_task():
    """Tâche Airflow avec vérification Aegis."""
    container = AegisContainer()
    container.configure(
        storage_driver="sqlalchemy",
        database_url="postgresql://user:pass@localhost/aegis_iam_db"
    )
    client = AegisClient(container)
    
    # Vérifier la permission avant d'exécuter la tâche
    if client.can("service-account-1", "pipeline:execute", "pipeline-daily"):
        print("✓ Pipeline autorisé")
        # Exécuter le pipeline...
    else:
        print("✗ Pipeline non autorisé")

with DAG(
    'aegis_pipeline',
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2026, 1, 1),
    },
    schedule_interval=timedelta(days=1),
) as dag:
    
    check_permission = PythonOperator(
        task_id='check_permission',
        python_callable=check_permission_task
    )
```

## 🔗 Intégration avec des Services Externes

### Webhook d'Audit

```python
from fastapi import FastAPI, Request
from aegis.core.application.outbox import HTTPEventPublisher

app = FastAPI()

# Configurer le publisher HTTP
webhook_publisher = HTTPEventPublisher(
    webhook_url="https://audit-service.example.com/webhooks/aegis",
    timeout=30
)

@app.post("/webhooks/aegis-events")
async def receive_aegis_event(request: Request):
    """Recevoir les événements Aegis depuis l'outbox."""
    event_data = await request.json()
    
    # Traiter l'événement (stocker dans votre système d'audit)
    print(f"Event reçu : {event_data}")
    
    return {"status": "received"}
```

## 🎓 Tutoriels Avancés

### Multi-Tenancy avec FastAPI

```python
from fastapi import Header, HTTPException
from aegis.core.domain.tenancy import TenantContext, TenantService

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Middleware de multi-tenancy Aegis."""
    # Extraire le tenant_id depuis le header
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    
    # Créer le contexte de tenant
    tenant_context = TenantContext(
        tenant_id=tenant_id,
        isolation_level="row_level"
    )
    
    # Ajouter au state de la requête
    request.state.tenant_context = tenant_context
    
    response = await call_next(request)
    return response
```

### GDPR Compliance avec Django

```python
from django.http import JsonResponse
from aegis.core.application.gdpr import GDPRService, GDPRFactory

def gdpr_export_view(request):
    """Endpoint d'export de données RGPD."""
    gdpr_service = GDPRFactory.create_compliant_pipeline()
    
    subject_id = request.user.aegis_subject_id  # À adapter
    
    # Récupérer le sujet depuis votre base
    subject = get_subject_from_db(subject_id)
    
    # Exporter les données
    export_data = gdpr_service.handle_data_export(subject)
    
    return JsonResponse(export_data)

def gdpr_delete_view(request):
    """Endpoint de suppression de données (droit à l'oubli)."""
    gdpr_service = GDPRFactory.create_compliant_pipeline()
    
    subject_id = request.user.aegis_subject_id
    from aegis.core.domain.values import SubjectId
    
    # Demander la suppression
    result = gdpr_service.handle_right_to_erasure(
        SubjectId(subject_id),
        reason="User request"
    )
    
    return JsonResponse(result)
```

## 📚 Ressources Supplémentaires

- [Documentation API complète](API.md)
- [Guide de contribution](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Exemples de code](https://github.com/aegis/keystone/tree/main/examples)

---

**Aegis IAM** - *Universal, Pluggable & Domain-Driven Identity & Access Management*