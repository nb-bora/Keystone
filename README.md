# Aegis

**The Universal, Pluggable & Domain-Driven IAM Engine for Python & Django**

> Un socle universel, modulaire et entièrement personnalisable pour la gestion des identités, de l’authentification et du contrôle d’accès (RBAC, ABAC, ReBAC), réutilisable sur n'importe quel projet Python (Django, FastAPI, Flask, Microservices) sans aucun couplage imposé.

---

## 0. Évaluation impartiale de l'idée & Plan vers le 20/20

### 📊 Note Impartiale Initiale : 16.5 / 20

| Critère d'évaluation | Note | Analyse Impartiale |
| :--- | :---: | :--- |
| **Vision & Problématique** | **4.0 / 4** | **Excellente**. Identifie parfaitement la douleur centrale des projets web (spaghetti d'authentification, dépendance aux vues/ORM, réinvention permanente du RBAC). |
| **Architecture & DDD** | **4.0 / 4** | **Très Solide**. La découpe en Bounded Contexts (Identity, Auth, Authz, Org) est claire et respecte les principes de la Clean Architecture. |
| **Réutilisabilité Universelle** | **2.5 / 4** | **À Améliorer**. Le concept initial était trop centré sur Django. Pour un 20/20, le cœur doit être `Python Framework-Agnostic` (`aegis-core`) avec un driver Django de premier ordre (`aegis-django`). |
| **Modularité & Personnalisation** | **3.0 / 4** | **À Améliorer**. Manquait d'un moteur de règles d'autorisation pluggable (passer de RBAC simple à ABAC/ReBAC) et de stratégies de stockage dynamiques. |
| **Product-Readiness & Sécurité** | **3.0 / 4** | **À Améliorer**. Nécessite l'intégration native d'acteurs non-humains (M2M, Clés API, Agents IA), du Tracing d'Audit (Outbox Pattern) et des pipelines RGPD. |

---

### 🚀 Plan de transformation vers un 20 / 20 Parfait

Pour atteindre un **20/20 incontestable**, le projet a été enrichi avec **5 Piliers d'Équivalence Universelle** :

1. **Découplage Framework Total (`aegis-core`)** : Le domaine et l'application s'exécutent en Pure Python et fonctionnent avec **Django**, **FastAPI**, **Flask**, ou en **Microservice gRPC/REST**.
2. **Modèle d'Acteur Universel (Subject Abstraction)** : Aegis ne gère pas seulement les humains (`Identity`), mais aussi les **Machine-to-Machine (M2M)**, les **Clés API**, et les **Agents IA**.
3. **Moteur d'Autorisation Pluggable (Policy Engine)** : Interchangez à chaud ou combinez **RBAC** (Rôles), **ABAC** (Attributs), **ReBAC** (Relations type Google Zanzibar), ou des **Règles Python Personnalisées**.
4. **Multi-Tenancy Dynamique & Hiérarchique** : Supporte du mode mono-tenant simple jusqu'à la hiérarchie d'entreprise (*Enterprise -> Organization -> Workspace -> Project*).
5. **Contrats de Sécurité & RGPD Natifs** : Audit Log fiable via *Transactional Outbox*, gestion du consentement, et pipeline automatisé d'anonymisation / droit à l'oubli.

---

## Table des matières

0. [Évaluation impartiale & Plan vers le 20/20](#0-évaluation-impartiale--plan-vers-le-2020)
1. [Vision Universelle](#1-vision-universelle)
2. [Le problème que nous résolvons](#2-le-problème-que-nous-résolvons)
3. [Philosophie & Principes (Core Agnostique & Drivers)](#3-philosophie--principes-core-agnostique--drivers)
4. [Architecture globale & Contrats Pluggables](#4-architecture-globale--contrats-pluggables)
5. [Bounded Contexts (Humains, Machines & Agents IA)](#5-bounded-contexts-humains-machines--agents-ia)
6. [Modèle de domaine & Policy Engines](#6-modèle-de-domaine--policy-engines)
7. [Couches de la Clean Architecture](#7-couches-de-la-clean-architecture)
8. [Authentification & Stratégies Pluggables](#8-authentification--stratégies-pluggables)
9. [Moteur d'Autorisation (RBAC, ABAC, ReBAC)](#9-moteur-dautorisation-rbac-abac-rebac)
10. [Guide de Personnalisation & Extensibilité Totale](#10-guide-de-personnalisation--extensibilité-totale)
11. [Décisions de conception majeures](#11-décisions-de-conception-majeures)
12. [Ce que Aegis n’est pas](#12-ce-que-aegis-nest-pas)
13. [Public cible](#13-public-cible)
14. [Valeur ajoutée par rapport à l’existant](#14-valeur-ajoutée-par-rapport-à-lexistant)
15. [Roadmap d'Excellence (20/20)](#15-roadmap-dexcellence-2020)
16. [Axes d’amélioration & Recommandations](#16-axes-damélioration--recommandations)
17. [Principes de contribution](#17-principes-de-contribution)
18. [Licence](#18-licence)

---

## 1. Vision Universelle

Aegis n’est pas un énième starter monolithique ni un simple wrapper autour de `django-allauth`.

C’est un **moteur IAM universel (Identity & Access Management Engine)** conçu dès le départ avec une approche **Domain-Driven Design (DDD)** et **Clean Architecture**.

L’objectif est de fournir un socle :

- **Universel & Agnostique (`aegis-core`)** : Exécutable en Pure Python avec n'importe quel framework (**Django**, **FastAPI**, **Flask**, ou **Microservice gRPC/REST**).
- **100% Personnalisable & Pluggable** : Chaque brique (Authentification, Stockage ORM, Moteur de règles d'accès, Multi-tenancy) est interchangeable par injection de dépendances.
- **Modèle d'Acteur Universel (Subject)** : Gère nativement les humains (`Identity`), les **Service Accounts (M2M)**, les **Clés API**, et les **Agents IA**.
- **Évolutif sans refactoring** : Passez d'un RBAC simple à un ABAC contextuel ou ReBAC (style Google Zanzibar) par simple configuration.
- **Prêt pour la production & Conforme** : Traçabilité d'audit via *Outbox Pattern*, gestion de session centralisée et pipelines RGPD natifs.

---

## 2. Le problème que nous résolvons

Dans la majorité des projets Python (Django, FastAPI...), on observe les mêmes patterns problématiques :

- Le modèle `User` du framework est modifié de façon ad-hoc et surchargé de champs non métier.
- L’authentification est verrouillée dans des bibliothèques spécifiques au framework sans réflexion sur le domaine.
- Les règles d’autorisation sont dispersées dans des décorateurs de vues, mixins, serializers ou middlewares.
- Les rôles sont rigides et incapables de gérer des permissions contextuelles (multi-tenant, objets, hiérarchies).
- Les accès non-humains (Webhooks, Microservices M2M, Agents IA) sont gérés de manière découplée et non sécurisée.
- Chaque nouveau projet recommence quasi intégralement le même travail.

Aegis part du constat suivant :

> La gestion des identités, des accès et des politiques de sécurité est un **domaine métier universel**.  
> Elle mérite d’être modélisée comme un moteur autonome et indépendant de tout framework web.

---

## 3. Philosophie & Principes

### 3.1 Architecture Découplée : Core Pure Python + Drivers

```
┌─────────────────────────────────────────────────────────────┐
│                    Aegis Applications                       │
│      (Vues Django, Endpoints FastAPI, CLI, Gateways)       │
└──────────────────────────────┬──────────────────────────────┘
                               │ (DTP / Requests)
┌──────────────────────────────▼──────────────────────────────┐
│                    aegis-core (Pure Python)                 │
│   Domain Entities  •  Use Cases  •  Pluggable Policy Engines│
└──────────────────────────────▲──────────────────────────────┘
                               │ (Ports & Interfaces)
┌──────────────────────────────┴──────────────────────────────┐
│                  Aegis Infrastructure Drivers               │
│  Django ORM  │ SQLAlchemy │ Redis Cache │ Allauth │ OIDC    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Principes directeurs (Le Standard 20/20)

| Principe | Application dans Aegis |
|---------|------------------------|
| **Modèle d'Acteur Universel** | Humains, Machines (M2M), Clés API & Agents IA sont des `Subjects` uniformes |
| **Agnostisme Framework** | Cœur 100% Pure Python (`aegis-core`), sans aucune dépendance envers Django ou FastAPI |
| **Moteur d'Autorisation Pluggable** | Support natif et interchangeable de **RBAC**, **ABAC**, **ReBAC** ou **Custom Rules** |
| **Multi-Tenancy Hiérarchique** | Stratégie d'isolation dynamique (`Flat`, `Single`, `Hierarchical Enterprise`) |
| **Audit Outbox & Compliance** | Transactions d'audit fiables (*Outbox Pattern*) et anonymisation RGPD native |

---

## 4. Architecture globale & Contrats Pluggables

Aegis est structuré autour de quatre couches isolées :

1. **Domaine Pur (`aegis-core/domain`)** : Contient le langage ubiquitaire, les Aggregates, Value Objects et les contrats de Policy Engines.
2. **Couche Application (`aegis-core/application`)** : Orchestre les Use Cases (*RegisterIdentity*, *AuthenticateSubject*, *EvaluatePolicy*, *RevokeSession*).
3. **Moteurs & Plugins (`aegis-core/plugins`)** : Définissent les contrats d'extension pour les politiques d'accès, l'authentification et les stratégies de stockage.
4. **Drivers d'Infrastructure (`aegis-drivers`)** : Fournissent les implémentations clés en main (**Django ORM Driver**, **FastAPI/SQLAlchemy Driver**, **Allauth Driver**, **OAuth/OIDC Driver**).

---

## 5. Bounded Contexts (Humains, Machines & Agents IA)

### 5.1 Identity & Subject Context

**Responsabilité** : Répondre à la question « *Qui ou quoi tente d'agir dans le système ?* »

Concepts principaux :
- `Subject` (Interface / Abstraction racine)
- `Identity` (Humain - Aggregate root)
- `ServiceAccount` (Machine-to-Machine / Microservice)
- `ApiKey` (Acteur programmatique)
- `AIAgentActor` (Agent IA autonome ou supervisé)
- `EmailAddress`, `TenantId`, `ActorMetadata` (Value Objects)

### 5.2 Authentication Context

**Responsabilité** : Répondre à la question « *Comment cet acteur prouve-t-il son identité ?* »

Concepts principaux :
- `AuthenticationStrategy` (Interface pluggable : Password, OIDC/OAuth2, SAML, MagicLink, Passkey/WebAuthn, M2M Token)
- `Credential` & `Proof`
- `SessionState` & `TokenSubject` (Gestion centralisée du cycle de vie des sessions et révocation globale)

### 5.3 Authorization & Policy Context

**Responsabilité** : Répondre à la question « *Cet acteur peut-il exécuter l'action X sur la ressource Y dans le contexte Z ?* »

Concepts principaux :
- `PolicyEngine` (Contrat central d'évaluation)
- `Role` & `Permission` (RBAC)
- `AttributePolicy` (ABAC : heure, IP, statut de l'objet, niveau de risque)
- `RelationshipTuple` (ReBAC : sujet ↔ relation ↔ ressource)
- `PolicyDecision` (`ALLOW`, `DENY`, `CONDITIONAL`)

### 5.4 Organization & Multi-Tenancy Context

**Responsabilité** : Modéliser le découpage des données et les hiérarchies d'organisation.

Concepts principaux :
- `Tenant` (Aggregate Root)
- `ScopeHierarchy` (Racine -> Organisation -> Espace de travail -> Projet)
- `TenantIsolationPolicy` (Strict Isolation, Shared DB Row-Level, Cross-Tenant Delegation)

---

## 6. Modèle de domaine & Policy Engines

### 6.1 Unified Subject Aggregate

```python
class Subject(ABC):
    id: SubjectId
    tenant_id: Optional[TenantId]
    is_active: bool

class HumanIdentity(Subject):
    email: EmailAddress
    profile: UserProfile
    verification_status: VerificationStatus

class ServiceAccount(Subject):
    client_id: str
    allowed_scopes: List[str]

class AIAgentActor(Subject):
    agent_id: str
    owner_identity_id: SubjectId
    max_autonomy_level: AutonomyLevel
```

### 6.2 Moteurs de Politiques d'Autorisation Pluggables

Aegis permet de choisir ou de combiner les moteurs d'autorisation :

- **`RBACPolicyEngine`** : Vérification basée sur les rôles et permissions classiques.
- **`ABACPolicyEngine`** : Évaluation basée sur des attributs dynamiques (ex: *L'utilisateur peut éditer le document D uniquement pendant les heures ouvrées et si statut == DRAFT*).
- **`ReBACPolicyEngine`** : Évaluation orientée graphe de relations (ex: *L'utilisateur U est membre de l'équipe E qui possède le dossier F contenant la ressource R*).
- **`CompositePolicyEngine`** : Combine plusieurs moteurs en cascade avec stratégie de résolution (*Unanimous*, *Affirmative*, *First-Applicable*).

### 5.3 Authorization Context (Access Control)

**Responsabilité** : Répondre à la question « Que peut-elle faire, et dans quel contexte ? »

Concepts principaux :
- Role
- Permission
- Assignment (User ↔ Role)
- Policy (évolution future vers ABAC/PBAC)
- Scope / Context (global, organization, project…)

### 5.4 Organization Context (optionnel / évolutif)

Préparé dès le départ, mais non obligatoire au démarrage.

Permet d’introduire la multi-tenancy sans refactoring majeur :
- Organization
- Membership
- Role scoped to an Organization

---

## 6. Modèle de domaine

### 6.1 Aggregates principaux

**Identity Aggregate**
- Root : `Identity`
- Contient les informations stables d’identité
- Garantit l’unicité de l’email
- Gère les transitions d’état (vérification, suspension…)

**Role Aggregate**
- Root : `Role`
- Possède un ensemble de `Permission`
- Peut porter des métadonnées (description, niveau, etc.)

**Assignment Aggregate**
- Lie une Identity à un Role
- Peut être contextualisé (Scope)

### 6.2 Value Objects

- `EmailAddress` (normalisation + validation)
- `PermissionCode`
- `RoleName`
- `AuthenticationProvider`
- `Scope`

### 6.3 Domain Services

- `AuthenticationService` : orchestre la vérification d’un credential
- `AuthorizationService` : répond à `can(identity, permission, context)`
- `RoleAssignmentService` : gère l’attribution et la révocation de rôles

### 6.4 Domain Events (exemples)

- `IdentityRegistered`
- `EmailVerified`
- `AuthenticationSucceeded`
- `AuthenticationFailed`
- `RoleAssigned`
- `RoleRevoked`
- `IdentitySuspended`

Ces événements permettent de découpler les contextes et d’ouvrir la porte à de l’audit, des notifications, etc.

---

## 7. Couches de la Clean Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Framework / Delivery Layer                      │
│      (Django Views, DRF ViewSets, FastAPI Routers, CLI Commands)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Call Use Cases / DTOs
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Application Layer (aegis-core)                      │
│   Use Cases (Register, Authenticate, Authorize, ManageTenant, Audit)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Invokes Domain Contracts
┌───────────────────────────────────▼────────────────────────────────────┐
│                       Domain Layer (aegis-core)                        │
│   Aggregates (Subject, Identity, Tenant)  •  Policy Engine Contracts   │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ Implements Ports
┌───────────────────────────────────┴────────────────────────────────────┘
│                    Infrastructure Drivers Layer                        │
│  Django ORM Mapper │ SQLAlchemy Repository │ Redis Session │ OIDC Provider│
└────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Domain Layer (`aegis-core/domain`)
- Pure Python (aucune dépendance externe, ni à Django, ni à FastAPI, ni à un ORM).
- Invariants métier stricts, Value Objects immutables, événements de domaine.

### 7.2 Application Layer (`aegis-core/application`)
- Orchestration des Use Cases à travers des DTOs (Data Transfer Objects).
- Définition des **Ports** (Interfaces abstraites pour les Repositories, EventBus, Mailer, Hashers).

### 7.3 Infrastructure Drivers Layer (`aegis-drivers`)
- Contient les implémentations concrètes :
  - **`DjangoDriver`** : Models ORM Django, Custom User Model Data Mapper, Admin Django.
  - **`SQLAlchemyDriver`** : Modèles SQLAlchemy pour FastAPI / Litestar / Flask.
  - **`AllauthAdapter`** : Pont entre les signaux/flux allauth et les Use Cases Aegis.

---

## 8. Authentification & Stratégies Pluggables

Aegis traite l'authentification comme une **stratégie interchangeable** (`AuthenticationStrategy`).

### 8.1 Stratégies d'Authentification Prêtes à l'Emploi

- **`PasswordAuthStrategy`** : Email/Login + Mot de passe (avec hachage PBKDF2/Argon2 abstrait).
- **`OAuthOIDCStrategy`** : Google, GitHub, Microsoft Azure AD, OIDC générique.
- **`MagicLinkStrategy`** : Authentification sans mot de passe via liens temporaires signés.
- **`PasskeyWebAuthnStrategy`** : Authentification biométrique / FIDO2.
- **`M2MTokenStrategy`** : Jetons HMAC / JWT pour les échanges entre services et Agents IA.

---

## 9. Moteur d'Autorisation (RBAC, ABAC, ReBAC)

### 9.1 Évaluation Universelle

Le `AuthorizationService` interroge le `PolicyEngine` configuré :

```python
decision: PolicyDecision = policy_engine.evaluate(
    subject=subject,
    action=PermissionCode("document:edit"),
    resource=resource_entity,
    context=EvaluationContext(ip="192.168.1.1", time=now())
)

if decision.is_allowed:
    # Action autorisée
```

### 9.2 Stratégies d'Autorisation Supportées

1. **RBAC (Role-Based Access Control)** : Matrice classique Rôles ↔ Permissions.
2. **ABAC (Attribute-Based Access Control)** : Évaluation de conditions dynamiques (Heure, IP, Statut, Métadonnées).
3. **ReBAC (Relationship-Based Access Control)** : Contrôle d'accès basé sur les graphes de relations (style Google Zanzibar).

---

## 10. Guide de Personnalisation & Extensibilité Totale

Aegis est conçu pour être réutilisable et personnalisable à 100% sur tout type de projet via un fichier de configuration déclaratif :

```python
# aegis_config.py
AEGIS_CONFIG = {
    # 1. Sélection de l'ORM / Stockage
    "STORAGE_DRIVER": "aegis.drivers.django.DjangoStorageDriver", 
    # Alternative : "aegis.drivers.sqlalchemy.SQLAlchemyStorageDriver"
    
    # 2. Modèle d'Acteurs Actifs
    "SUBJECT_TYPES": [
        "HUMAN",          # Utilisateurs physiques
        "SERVICE_ACCOUNT", # Microservices M2M
        "AI_AGENT",       # Agents IA autonomes
    ],

    # 3. Moteur d'Autorisation Principal
    "POLICY_ENGINE": "aegis.core.policies.CompositePolicyEngine",
    "POLICY_ENGINES_CASCADE": [
        "aegis.core.policies.RBACPolicyEngine",
        "aegis.core.policies.ABACPolicyEngine",
    ],

    # 4. Stratégie Multi-Tenant
    "TENANCY_MODE": "HIERARCHICAL", # FLAT, SINGLE, ou HIERARCHICAL
    
    # 5. Traçabilité & Conformité
    "AUDIT_OUTBOX_ENABLED": True,
    "GDPR_AUTOMATIC_ERASURE": True,
}
```

### 9.2 Évolutions prévues

- Permissions contextualisées (par Organisation, par projet…)
- Object-level permissions
- Évolution progressive vers un moteur de politiques plus riche (ABAC / PBAC) si nécessaire

### 9.3 Principe directeur

> L’autorisation est une question de **domaine**, pas une question de décorateur dispersé dans les vues.

Les checks d’autorisation passent par le `AuthorizationService` du domaine (ou une façade application).

---

## 11. Décisions de conception majeures

| Décisions de Conception | Justification Architecturale (Standard 20/20) |
| :--- | :--- |
| **Cœur Pure Python Framework-Agnostic (`aegis-core`)** | Permet la réutilisation sur n'importe quel projet Python (Django, FastAPI, Flask, CLI, Microservices). |
| **Modèle d'Acteur Universel (`Subject`)** | Unifie la gestion de sécurité pour les Humains, les Service Accounts (M2M), les Clés API et les Agents IA. |
| **Policy Engines Interchangeables** | Permet de faire évoluer dynamiquement le système de RBAC simple à ABAC ou ReBAC (Zanzibar style) sans refactoring. |
| **Custom User Model comme Adapter** | Garde le modèle Django ORM strictement dans l'Infrastructure via un Data Mapper. |
| **Anti-Corruption Layer pour allauth & OAuth** | Protège le domaine d'un couplage fort avec des bibliothèques d'infrastructure tierces. |
| **Audit Outbox & Conformité RGPD Native** | Garantit la traçabilité transactionnelle des événements de sécurité et le respect du droit à l'oubli. |

---

## 12. Ce que Aegis n’est pas

- Ce n’est **pas** un simple starter Django monolithique dépendant d'un ORM spécifique.
- Ce n’est **pas** un Identity Provider externe lourd à maintenir (comme Keycloak ou Zitadel).
- Ce n’est **pas** une solution magique « zero-config » qui masque la complexité métier.

Aegis est un **moteur IAM universel et personnalisable** à intégrer au cœur de vos applications Python pour prendre le contrôle total sur la sécurité, l'identité et les accès.

---

## 13. Public cible

- Développeurs et architectes construisant des applications Python/Django modernes et évolutives.
- Équipes SaaS développant des applications multi-tenants avec gestion de permissions complexes.
- Projets API-First, Microservices ou workflows intégrant des Agents IA et des accès M2M.
- Freelances et agences souhaitant un socle IAM unique et réutilisable d'un projet à l'autre.

---

## 14. Valeur ajoutée par rapport à l’existant

Aegis se différencie des wrappers d'authentification traditionnels et des boilerplates SaaS par :

1. **Un Moteur de Domaine Universel (`aegis-core`)** 100% indépendant des frameworks.
2. **Une Modularité Totale (Pluggable Policy & Storage Engines)** pour une personnalisation sans limite.
3. **Le Support Natif des Acteurs Non-Humains** (M2M, Agents IA, Clés API).
4. **Une Architecture Hexagonale Rigoureuse** éliminant la dette technique d'authentification.
5. **Une Documentation de Niveau Produit** avec stratégie de test pyramidale.

---

## 15. Roadmap d'Excellence (20/20)

### Phase 1 — Cœur Agnostique & Driver Django (Actuelle)
- Package Pure Python `aegis-core` (Entities, Use Cases, Ports)
- Driver `aegis-django` (ORMMapper, Custom UserModel Adapter, Views/Admin)
- Support RBAC & Authentication Strategies (Password, OIDC/Google)

### Phase 2 — Multi-Tenancy & Moteurs Avancés
- Support des Policy Engines ABAC & ReBAC (Graphes de relation)
- Hiérarchies de Tenancy (`Flat`, `Hierarchical Enterprise`)
- Driver `aegis-fastapi` / SQLAlchemy

### Phase 3 — Acteurs IA & Transactional Outbox Audit
- Abstraction native des Agents IA (`AIAgentActor`) avec niveaux d'autonomie
- Implémentation du *Transactional Outbox Pattern* pour l'Audit Logging
- Pipeline automatisé de purge & anonymisation RGPD

### Phase 4 — Ecosystème & Maturité Enterprise
- Support WebAuthn / Passkeys
- CLI Aegis pour la génération de règles de sécurité et benchmarks
- Certification & Versioning Stable 1.0

---

## 16. Axes d’amélioration & Recommandations

Dans le but de faire évoluer **Aegis** d’un concept architectural solide vers un framework de production prêt à l'emploi, voici les axes prioritaires d’amélioration identifiés :

### 16.1 Clarification de l'identité du projet (Aegis vs Keystone)
- **Harmonisation du nommage** : Le dépôt se nomme `Keystone` tandis que la documentation fait référence à `Aegis`. Il convient de formaliser la relation (ex. : *Keystone* comme nom de dépôt/projet et *Aegis* comme cœur de package IAM) afin d'assurer la cohérence des namespaces Python (`import aegis` vs `import keystone`).

### 16.2 Mapping ORM & Pattern Repository (Clean Architecture en Django)
- **Anti-Corruption Layer (ACL) explicite** : Le modèle `User` de Django ORM doit appartenir strictly à la couche `Infrastructure`. La conversion entre `DjangoUserModel` et l'Aggregate Root `Identity` nécessite un Data Mapper dédié pour éviter que des exceptions ORM (`DoesNotExist`, `IntegrityError`) ne fassent irruption dans la couche Domaine.
- **Unit of Work & Boundary de Transaction** : Formaliser la gestion des transactions (ex. : création d'une identité + attribution du rôle par défaut) au niveau de la couche Application (Use Cases) via un pattern *Unit of Work* ou un gestionnaire de contexte transactionnel abstrait, plutôt que de s'appuyer sur des signaux Django implicites.

### 16.3 Robustesse Événementielle (Transactional Outbox Pattern)
- **Fiabilité des Domain Events** : Pour l'audit, l'envoi d'emails ou l'intégration avec des brokers (Celery, Redis, RabbitMQ), l'émission directe d'événements lors d'une requête HTTP peut échouer en cas de problème réseau post-commit DB.
- **Recommandation** : Adopter le pattern *Transactional Outbox* (sauvegarde des événements de domaine dans une table d'outbox au sein de la même transaction DB, puis dépilement asynchrone par un worker).

### 16.4 Sécurité, Audit & Conformité (RGPD)
- **Gestion des sessions & Révocation globale** : Intégrer au contexte d'Authentification la capacité d'invalider toutes les sessions d'une `Identity` (ex. : lors d'une réinitialisation de mot de passe ou d'une alerte sécurité).
- **Privacy & Droit à l'oubli (RGPD)** : Intégrer les invariants métier d'anonymisation et de suppression de compte directement dans l'Aggregate `Identity`, en séparant les identifiants techniques des données personnelles (PII).
- **Rate Limiting sur Use Cases sensibles** : Définir quel composant (Middleware Infrastructure ou Gateway) applique le throttling / la protection contre le brute-force lors des appels aux Use Cases d'authentification.

### 16.5 Structure de Répertoire Recommandée (Layout de Code)
Pour guider l'implémentation dès le premier commit, nous recommandons le layout de code suivant :

```text
src/
├── aegis/
│   ├── domain/               # Pure Python (Entities, Value Objects, Domain Events, Domain Services)
│   │   ├── identity/
│   │   ├── authentication/
│   │   └── authorization/
│   ├── application/          # Use Cases, DTOs, Ports/Interfaces (Repositories, Mailers, EventBus)
│   │   ├── identity/
│   │   ├── authentication/
│   │   └── authorization/
│   └── infrastructure/       # Django ORM Models, Repositories Impl, Allauth Adapters, Celery Worker
│       ├── persistence/
│       ├── adapters/
│       └── django_app/
```

### 16.6 Multi-Tenancy & Isolation de Contexte
- **Propagation du Contexte Tenant** : Clarifier la stratégie d'isolation (ex. : `TenantContext` véhiculé explicitement dans les Use Cases ou via des `ContextVar` Python dans les middlewares). Cela garantit que les contrôles de permissions du service `AuthorizationService` soient toujours étanches entre organisations.

### 16.7 Stratégie de Test Pyramidale
- **Tests Domaine/Application ultra-rapides** : Tirer profit du découplage Clean Architecture pour exécuter 80% de la suite de tests en pure Python (sans chargement de l'ORM ni de la base de données Django).
- **Tests d'Intégration ciblés** : Limiter l'utilisation de `TestCase` / DB Django aux réels adapters d'infrastructure (Repositories, Vues, Signaux Allauth).

---

## 17. Principes de contribution

- Toute contribution doit respecter les Bounded Contexts et le langage ubiquitaire
- Le Domain Layer doit rester pur (aucune dépendance framework)
- Les règles métier appartiennent au domaine ou aux Use Cases, jamais aux adapters
- La documentation meublant le projet est considérée comme une partie critique du code
- Les décisions d’architecture importantes font l’objet d’ADR (Architecture Decision Records)

---

## 18. Licence

MIT License

---

**Aegis** — *Protect the identity. Control the access. Own the domain.*