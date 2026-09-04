# Aegis IAM - Documentation Technique Complète

## 📚 Sommaire

1. [Architecture Générale](#architecture-générale)
2. [Modules Core](#modules-core)
3. [Configuration](#configuration)
4. [Déploiement](#déploiement)
5. [Sécurité](#sécurité)
6. [Performance](#performance)
7. [Extensibilité](#extensibilité)
8. [Tests](#tests)
9. [Monitoring](#monitoring)
10. [Maintenance](#maintenance)

-------------------------------------

## 🏗️ Architecture Générale

### Clean Architecture

Aegis IAM suit strictement les principes de Clean Architecture pour garantir la séparation des préoccupations et l'extensibilité maximale.

```
src/aegis/
├── core/                    # Domain Core (Business Logic)
│   ├── domain/             # Domain Layer (Entities, Value Objects, Events)
│   ├── application/        # Application Layer (Use Cases, Services)
│   ├── policies/           # Policy Engines (RBAC, ABAC, ReBAC)
│   ├── validation/         # Validation Engine
│   ├── config_loader.py    # Configuration Loader
│   └── plugins.py          # Plugin System
├── drivers/                # Infrastructure Layer (Adapters)
│   ├── inmemory/          # In-Memory Driver (Testing)
│   ├── fastapi/           # FastAPI Driver
│   ├── sqlalchemy/        # SQLAlchemy Driver
│   └── django/            # Django Driver
└── sdk/                   # SDK (Client Library)
    └── client.py          # AegisClient
```

### Domain-Driven Design (DDD)

#### Entités de Domaine

Les entités sont les racines d'agrégats et contiennent la logique métier centrale :

- **Subject**: Racine d'agrégat pour tous les types d'identités
- **HumanIdentity**: Utilisateurs humains avec email, nom, etc.
- **ServiceAccount**: Comptes de service pour l'authentification M2M
- **ApiKeyActor**: Clés API pour l'accès programmatique
- **AIAgentActor**: Agents IA avec niveaux d'autonomie
- **Role**: Rôles avec héritage et permissions
- **Tenant**: Entités multi-tenant avec hiérarchies

#### Value Objects

Les objets de valeur sont immuables et représentent des concepts du domaine :

- **SubjectId**: Identifiant unique d'un sujet
- **TenantId**: Identifiant unique d'un tenant
- **PermissionCode**: Code de permission (ex: "document:read")
- **EmailAddress**: Email validé
- **EvaluationContext**: Contexte d'évaluation de politique

#### Events

Les événements de domaine sont immuables et alimentent le Transactional Outbox :

- **AuthenticationSuccessEvent**: Succès d'authentification
- **AuthorizationDecisionEvent**: Décision d'autorisation
- **PermissionGrantedEvent**: Permission accordée
- **DataDeletionRequestedEvent**: Demande de suppression RGPD
- etc.

---

## 🔧 Modules Core

### 1. Configuration Declarative (config_loader.py)

#### Fichier de Configuration (aegis.config.yaml)

```yaml
# Configuration principale Aegis IAM
aegis:
  # Stratégies d'authentification
  strategies:
    - password
    - oidc
    - magic_link
  
  # Configuration du hachage de mot de passe
  password:
    algorithm: pbkdf2_sha256
    iterations: 100000
  
  # Configuration OIDC
  oidc_providers:
    - name: google
      client_id: ${GOOGLE_CLIENT_ID}
      client_secret: ${GOOGLE_CLIENT_SECRET}
      issuer: https://accounts.google.com
  
  # Configuration du stockage
  storage:
    driver: sqlalchemy
    database_url: ${DATABASE_URL}
  
  # Configuration des politiques
  policies:
    primary: rbac
    cascade:
      - abac
      - rebac
  
  # Configuration multi-tenant
  tenancy:
    mode: hierarchical
    isolation_type: row_level
    max_tenant_depth: 4
  
  # Configuration des sessions
  sessions:
    max_concurrent: 5
    timeout_seconds: 3600
    idle_timeout_seconds: 1800
```

#### Chargement de Configuration

```python
from aegis.core.config_loader import load_config, get_config

# Charger depuis le fichier YAML
config = load_config("aegis.config.yaml")

# Obtenir la configuration globale
config = get_config()

# Accéder aux valeurs
print(config.strategies)  # ['password', 'oidc', 'magic_link']
print(config.password.algorithm)  # 'pbkdf2_sha256'
```

### 2. Anti-Corruption Layer (acl.py)

#### Data Mapper Pattern

Le Data Mapper convertit entre les entités de domaine et les modèles ORM sans couplage :

```python
from aegis.core.application.acl import DataMapper, MapperFactory

# Créer un mapper pour les sujets
mapper = MapperFactory.create_subject_mapper()

# Convertir une entité de domaine en données ORM
domain_entity = HumanIdentity(
    id=SubjectId("user-123"),
    email=EmailAddress("user@example.com")
)
orm_data = mapper.domain_to_orm(domain_entity)

# Convertir des données ORM en entité de domaine
orm_model = {
    "id": "user-123",
    "email": "user@example.com",
    "subject_type": "human"
}
domain_entity = mapper.orm_to_domain(orm_model)
```

#### Unit of Work Pattern

Le Unit of Work gère les transactions de manière cohérente :

```python
from aegis.core.application.acl import UnitOfWork, SQLAlchemyUnitOfWork

# Créer un UoW SQLAlchemy
uow = SQLAlchemyUnitOfWork(engine)

# Utiliser le UoW
with uow:
    subject_repo = uow.subject_repository
    subject = subject_repo.get_by_id(SubjectId("user-123"))
    subject.activate()
    uow.commit()
```

### 3. Validation Engine (validation/)

#### Système de Validation Extensible

```python
from aegis.core.validation import ValidationEngine, ValidationRegistry

# Créer un moteur de validation
engine = ValidationEngine()

# Valider un email
result = engine.validate("email", "user@example.com")
if result.is_valid:
    print("Email valide")
else:
    print(f"Erreurs: {result.errors}")

# Valider un mot de passe
result = engine.validate("password", "StrongPass123!")
if result.is_valid:
    print("Mot de passe fort")
else:
    print(f"Erreurs: {result.errors}")

# Créer un validateur personnalisé
from aegis.core.validation import CustomValidator

def custom_validator(value):
    if value == "forbidden":
        return ValidationResult(is_valid=False, errors=[("field", "Value forbidden")])
    return ValidationResult(is_valid=True)

engine.register_custom_validator("custom", CustomValidator(custom_validator, lambda x: x))
```

### 4. Policy Engines (policies/)

#### RBAC Policy Engine

```python
from aegis.core.policies.rbac import RBACPolicyEngine

# Créer un engine RBAC
engine = RBACPolicyEngine(role_repository, permission_repository)

# Évaluer une permission
decision = engine.evaluate(
    subject_id=SubjectId("user-123"),
    action="document:read",
    resource_id="doc-456"
)

if decision.effect.value == "ALLOW":
    print("Accès autorisé")
else:
    print(f"Accès refusé: {decision.reason}")
```

#### ABAC Policy Engine

```python
from aegis.core.policies.abac import ABACPolicyEngine, ABACConditionFactory

# Créer un engine ABAC
engine = ABACPolicyEngine()

# Créer une politique temporelle
from aegis.core.policies.abac import TimeBasedCondition, ABACPolicy

policy = ABACPolicy(
    id="time-policy",
    effect=PolicyEffect.ALLOW,
    conditions=[
        TimeBasedCondition(
            start_hour=9,
            end_hour=17,
            days_of_week=[1, 2, 3, 4, 5]  # Lundi-Vendredi
        )
    ]
)

# Évaluer avec contexte
context = EvaluationContext(
    current_time=datetime.now(timezone.utc),
    ip_address="192.168.1.100"
)
decision = engine.evaluate(policy, context)
```

#### ReBAC Policy Engine

```python
from aegis.core.policies.rebac import ReBACPolicyEngine, InMemoryRelationshipStore

# Créer un engine ReBAC
store = InMemoryRelationshipStore()
engine = ReBACPolicyEngine(store)

# Ajouter des relations
from aegis.core.policies.rebac import RelationshipTuple, RelationType

store.add_tuple(RelationshipTuple(
    subject_id=SubjectId("user-1"),
    relation=RelationType.MEMBER,
    object_id="team-1"
))

# Évaluer un accès
check = RelationshipCheck(
    subject_id=SubjectId("user-1"),
    relation=RelationType.MEMBER,
    object_id="team-1"
)
is_allowed = engine.check(check)
```

### 5. Authentication Strategies (domain/authentication.py)

#### Manager d'Authentification

```python
from aegis.core.domain.authentication import AuthenticationFactory
from aegis.drivers.inmemory import Pbkdf2PasswordHasher

# Créer un manager d'authentification
hasher = Pbkdf2PasswordHasher(iterations=100000)
manager = AuthenticationFactory.create_default_manager(hasher)

# Authentifier avec mot de passe
result = manager.authenticate(
    AuthenticationMethod.PASSWORD,
    {
        "subject_id": "user-123",
        "password": "user_password"
    }
)

if result.is_success:
    print(f"Authentifié: {result.subject_id}")
else:
    print(f"Échec: {result.status}")
```

#### Stratégies d'Authentification

```python
# Mot de passe
password_strategy = PasswordAuthStrategy(hasher)

# OIDC
oidc_strategy = OIDCAuthStrategy(
    client_id="your-client-id",
    client_secret="your-client-secret",
    issuer="https://accounts.google.com"
)

# Magic Link
magic_link_strategy = MagicLinkAuthStrategy(token_ttl=3600)

# M2M Token
m2m_strategy = M2MTokenAuthStrategy(secret_key="your-secret-key")
```

### 6. Transactional Outbox (application/outbox.py)

#### Outbox Manager

```python
from aegis.core.application.outbox import OutboxManager, OutboxFactory

# Créer un manager d'outbox
manager = OutboxFactory.create_production_manager(
    backend=OutboxBackend.IN_MEMORY,
    publisher=ConsoleEventPublisher()
)

# Ajouter un événement
from aegis.core.domain.events import AuthenticationSuccessEvent

event = AuthenticationSuccessEvent(
    subject_id=SubjectId("user-123"),
    auth_method="password",
    ip_address="192.168.1.100"
)
manager.add_event(event)

# Traiter les événements
worker = OutboxWorker(manager, interval_seconds=5)
await worker.process_events()
```

### 7. Session Management (application/sessions.py)

#### Session Manager

```python
from aegis.core.application.sessions import SessionManager, SessionSecurityPolicy

# Créer un manager de sessions
policy = SessionSecurityPolicy(
    max_concurrent_sessions=5,
    session_timeout_seconds=3600,
    idle_timeout_seconds=1800
)
manager = SessionManager(default_ttl_seconds=3600, security_policy=policy)

# Créer une session
session = manager.create_session(
    subject_id=SubjectId("user-123"),
    user_agent="Mozilla/5.0...",
    ip_address="192.168.1.100"
)

# Valider une session
is_valid = manager.validate_session(session.session_id)

# Révoquer toutes les sessions d'un utilisateur
manager.revoke_all_sessions(SubjectId("user-123"))
```

### 8. GDPR Pipeline (application/gdpr.py)

#### Service GDPR

```python
from aegis.core.application.gdpr import GDPRFactory

# Créer un service GDPR compliant
gdpr_service = GDPRFactory.create_compliant_pipeline()

# Export de données
export_data = gdpr_service.handle_data_export(subject)
print(f"Export: {export_data}")

# Droit à l'oubli
result = gdpr_service.handle_right_to_erasure(
    SubjectId("user-123"),
    reason="User request"
)
print(f"Statut: {result['status']}")
```

### 9. Plugin System (plugins.py)

#### Plugin Manager

```python
from aegis.core.plugins import PluginManager, PluginFactory

# Créer un manager de plugins
manager = PluginManager()

# Créer et enregistrer un plugin
logging_plugin = PluginFactory.create_logging_plugin()
manager.register_plugin(logging_plugin)

# Exécuter des hooks
context = HookContext(
    hook_type=HookType.PRE_USE_CASE,
    data={"action": "create_user"}
)
results = manager.execute_hooks(HookType.PRE_USE_CASE, context)
```

### 10. Cache des Décisions (application/cache.py)

#### Système de Cache

```python
from aegis.core.application.cache import (
    InMemoryAuthorizationCache,
    CachedPolicyEngine,
    CacheFactory
)

# Créer un cache en mémoire
cache = CacheFactory.create_memory_cache(
    max_size=10000,
    eviction_policy=CacheEvictionPolicy.LRU
)

# Wraper un policy engine avec cache
cached_engine = CachedPolicyEngine(
    underlying_engine=rbac_engine,
    cache=cache,
    ttl_seconds=300
)

# Évaluer avec cache
decision = cached_engine.evaluate(
    subject_id="user-123",
    action="document:read",
    resource_id="doc-456"
)

# Invalider le cache d'un utilisateur
cached_engine.invalidate_subject("user-123")
```

---

## ⚙️ Configuration

### Variables d'Environnement

```bash
# Base de données
DATABASE_URL=postgresql://user:pass@localhost/aegis_iam_db

# OIDC
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Redis (optionnel)
REDIS_URL=redis://localhost:6379/0

# Sécurité
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret

# Session
SESSION_TIMEOUT=3600
MAX_CONCURRENT_SESSIONS=5
```

### Modes de Configuration

```python
# Mode développement
config = load_config("aegis.config.yaml", environment="development")

# Mode production
config = load_config("aegis.config.yaml", environment="production")

# Mode test
config = load_config("aegis.config.yaml", environment="test")
```

---

## 🚀 Déploiement

### Docker Compose

```yaml
version: '3.8'

services:
  aegis-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://aegisuser:aegispass@postgres:5432/aegis_iam_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: aegisuser
      POSTGRES_PASSWORD: aegispass
      POSTGRES_DB: aegis_iam_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts:/etc/prometheus/alerts
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  redis_data:
  grafana_data:
```

### Commandes de Déploiement

```bash
# Construire et démarrer
docker-compose up -d

# Exécuter les migrations
docker-compose exec aegis-api alembic upgrade head

# Vérifier les logs
docker-compose logs -f aegis-api

# Arrêter
docker-compose down
```

### Migrations Alembic

```bash
# Créer une nouvelle migration
alembic revision --autogenerate -m "description"

# Appliquer les migrations
alembic upgrade head

# Revenir à une version spécifique
alembic downgrade <revision>

# Voir l'historique
alembic history
```

---

## 🔒 Sécurité

### Hachage de Mot de Passe

```python
from aegis.drivers.inmemory import Pbkdf2PasswordHasher

# Créer un hasher avec paramètres sécurisés
hasher = Pbkdf2PasswordHasher(
    iterations=100000,
    algorithm="pbkdf2_sha256"
)

# Hacher un mot de passe
hashed = hasher.hash("user_password")

# Vérifier un mot de passe
is_valid = hasher.verify("user_password", hashed)
```

### Anonymisation des Données

```python
from aegis.core.application.gdpr import StandardDataAnonymizer

anonymizer = StandardDataAnonymizer()

# Anonymiser un email
email = anonymizer.anonymize_email("alice.smith@enterprise.com")
# Résultat: "a***@enterprise.com"

# Anonymiser une IP
ip = anonymizer.anonymize_ip("192.168.1.100")
# Résultat: "192.168.***.***"
```

### Politique de Sessions

```python
from aegis.core.application.sessions import SessionSecurityPolicy

policy = SessionSecurityPolicy(
    max_concurrent_sessions=5,
    session_timeout_seconds=3600,
    idle_timeout_seconds=1800,
    revoke_on_password_change=True,
    revoke_on_security_event=True
)
```

### Tests de Sécurité

```bash
# Exécuter les tests de sécurité
pytest tests/test_security.py -v

# Scanner avec Bandit
bandit -r src/

# Vérifier avec Safety
safety check
```

---

## ⚡ Performance

### Indexes de Base de Données

Les indexes suivants sont configurés dans les migrations :

- **aegis_subjects**: tenant_id, subject_type, is_active, email
- **aegis_roles**: tenant_id, is_system_role, name
- **aegis_role_assignments**: subject_id, role_id, tenant_id, expires_at
- **aegis_tenants**: parent_tenant_id, level, is_active
- **aegis_outbox_events**: status, created_at, event_type, aggregate_id
- **aegis_sessions**: subject_id, status, expires_at, last_activity

### Stratégies de Cache

```python
# Cache haute performance
cache = CacheFactory.create_high_performance_cache()

# Cache conservateur
cache = CacheFactory.create_conservative_cache()

# Cache personnalisé
cache = InMemoryAuthorizationCache(
    max_size=50000,
    eviction_policy=CacheEvictionPolicy.LRU
)
```

### Monitoring des Performances

```python
# Statistiques du cache
stats = cache.get_statistics()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Size: {stats['size']}/{stats['max_size']}")
```

---

## 🔌 Extensibilité

### Plugins Personnalisés

```python
from aegis.core.plugins import Plugin, hook, HookType

class CustomPlugin(Plugin):
    def __init__(self):
        super().__init__(
            name="Custom Plugin",
            version="1.0.0",
            priority=100
        )
    
    @hook(HookType.PRE_USE_CASE)
    def before_use_case(self, context: HookContext) -> HookResult:
        """Hook exécuté avant chaque use case."""
        print(f"Exécution avant: {context.data}")
        return HookResult(success=True, data={})
    
    @hook(HookType.POST_USE_CASE)
    def after_use_case(self, context: HookContext) -> HookResult:
        """Hook exécuté après chaque use case."""
        print(f"Exécution après: {context.data}")
        return HookResult(success=True, data={})

# Enregistrer le plugin
manager = PluginManager()
manager.register_plugin(CustomPlugin())
```

### Validateurs Personnalisés

```python
from aegis.core.validation import Validator, ValidationResult

class CustomValidator(Validator):
    def validate(self, value: Any) -> ValidationResult:
        if value == "forbidden":
            return ValidationResult(
                is_valid=False,
                errors=[("field", "Value is forbidden")]
            )
        return ValidationResult(is_valid=True)

# Enregistrer le validateur
engine = ValidationEngine()
engine.register_custom_validator("custom", CustomValidator())
```

### Conditions ABAC Personnalisées

```python
from aegis.core.policies.abac import CustomCondition

class CustomGeoCondition(CustomCondition):
    def evaluate(self, context: EvaluationContext) -> bool:
        """Évalue une condition géographique."""
        ip = context.ip_address
        # Logique géographique personnalisée
        return self._is_ip_in_allowed_region(ip)

# Utiliser dans une politique
policy = ABACPolicy(
    id="geo-policy",
    effect=PolicyEffect.ALLOW,
    conditions=[CustomGeoCondition(allowed_regions=["US", "EU"])]
)
```

---

## 🧪 Tests

### Structure des Tests

```
tests/
├── test_domain.py              # Tests des entités de domaine
├── test_new_components.py      # Tests des nouveaux composants
├── test_rbac_engine.py         # Tests du moteur RBAC
├── test_security.py            # Tests de sécurité
├── test_use_cases.py           # Tests des use cases
├── test_fastapi_driver.py      # Tests du driver FastAPI
└── test_health_and_observability.py  # Tests de santé
```

### Exécution des Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_domain.py -v

# Tests avec couverture
pytest tests/ --cov=src/aegis --cov-report=html

# Tests de sécurité
pytest tests/test_security.py -v
```

### Types de Tests

- **Tests Unitaires**: Tests isolés de composants individuels
- **Tests d'Intégration**: Tests d'intégration entre composants
- **Tests de Sécurité**: Tests de sécurité automatisés
- **Tests de Performance**: Tests de performance et charge

---

## 📊 Monitoring

### Metrics Prometheus

Les metrics suivants sont exposés :

- `aegis_pending_audit_events`: Nombre d'événements en attente
- `aegis_authorization_decisions_total`: Total des décisions d'autorisation
- `aegis_authorization_denials_total`: Total des refus d'autorisation
- `aegis_total_subjects`: Nombre total de sujets
- `aegis_active_sessions`: Nombre de sessions actives
- `aegis_cache_hits`: Nombre de hits du cache
- `aegis_cache_misses`: Nombre de misses du cache

### Alertes Prometheus

```yaml
groups:
  - name: aegis_alerts
    rules:
      - alert: HighPendingAuditEvents
        expr: aegis_pending_audit_events > 100
        for: 5m
        labels:
          severity: warning
      
      - alert: CriticalPendingAuditEvents
        expr: aegis_pending_audit_events > 1000
        for: 1m
        labels:
          severity: critical
      
      - alert: HighAuthorizationDenials
        expr: rate(aegis_authorization_denials_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
```

### Dashboard Grafana

Un dashboard Grafana préconfiguré est disponible dans `prometheus/grafana-dashboard.json` avec :

- Panneau d'événements d'audit en attente
- Panneau de décisions d'autorisation
- Panneau de sujets totaux
- Panneau de disponibilité du service
- Panneau de taux de succès d'authentification
- Panneau d'activité de sessions
- Panneau de conformité GDPR
- Panneau de performance du cache

---

## 🔧 Maintenance

### Sauvegardes Automatisées

```bash
# Configurer les sauvegardes automatisées
./scripts/setup_automated_backups.sh

# Sauvegarde manuelle
./scripts/backup_postgres.sh

# Restauration
./scripts/restore_postgres.sh ./backups/aegis_postgres_20260904_120000.sql.gz
```

### Mises à Jour

```bash
# Mettre à jour les dépendances
pip install --upgrade -e ".[dev]"

# Exécuter les migrations
alembic upgrade head

# Redémarrer le service
docker-compose restart aegis-api
```

### Health Checks

```bash
# Vérifier la santé du service
curl http://localhost:8000/health

# Vérifier les metrics
curl http://localhost:8000/metrics
```

### Logs

```bash
# Voir les logs du service
docker-compose logs -f aegis-api

# Voir les logs avec filtre
docker-compose logs aegis-api | grep "ERROR"
```

---

## 📚 Ressources Supplémentaires

- [Guide de Contribution](CONTRIBUTING.md)
- [Documentation API](API.md)
- [Tutoriels d'Intégration](INTEGRATION.md)
- [Changelog](CHANGELOG.md)
- [README Principal](README.md)

---

**Aegis IAM v0.2.0** - *Universal, Pluggable & Domain-Driven Identity & Access Management Foundation*