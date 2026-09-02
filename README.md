# Aegis

**A Domain-Driven, Clean Architecture foundation for Identity & Access Management in Django**

> Un socle réutilisable, préconfiguré et architecturé pour la gestion des identités, de l’authentification et du contrôle d’accès (RBAC) dans les projets Django modernes.

---

## Table des matières

1. [Vision](#1-vision)
2. [Le problème que nous résolvons](#2-le-problème-que-nous-résolvons)
3. [Philosophie & Principes](#3-philosophie--principes)
4. [Architecture globale](#4-architecture-globale)
5. [Bounded Contexts](#5-bounded-contexts)
6. [Modèle de domaine](#6-modèle-de-domaine)
7. [Couches de la Clean Architecture](#7-couches-de-la-clean-architecture)
8. [Authentification](#8-authentification)
9. [Autorisation & RBAC](#9-autorisation--rbac)
10. [Décisions de conception majeures](#10-décisions-de-conception-majeures)
11. [Ce que Aegis n’est pas](#11-ce-que-aegis-nest-pas)
12. [Public cible](#12-public-cible)
13. [Valeur ajoutée par rapport à l’existant](#13-valeur-ajoutée-par-rapport-à-lexistant)
14. [Roadmap](#14-roadmap)
15. [Principes de contribution](#15-principes-de-contribution)
16. [Licence](#16-licence)

---

## 1. Vision

Aegis n’est pas un énième starter Django ni un simple wrapper autour de `django-allauth`.

C’est une **fondation d’Identity & Access Management (IAM)** conçue dès le départ avec une approche **Domain-Driven Design** et **Clean Architecture**.

L’objectif est de fournir un socle :

- **Réutilisable** d’un projet à l’autre
- **Évolutif** (du simple RBAC global jusqu’à des politiques contextuelles et multi-tenant)
- **Découplé** des détails d’infrastructure (Django, allauth, OAuth, sessions, JWT…)
- **Explicite** dans ses règles métier
- **Testable** sans base de données ni framework
- **Documenté** de façon exemplaire

Aegis vise à devenir le point de départ sérieux pour tout projet Django qui refuse de recommencer la gestion des utilisateurs et des permissions depuis zéro, tout en évitant la sur-ingénierie et les boilerplates monolithiques.

---

## 2. Le problème que nous résolvons

Dans la majorité des projets Django, on observe les mêmes patterns problématiques :

- Le modèle `User` est modifié de façon ad-hoc
- L’authentification email + Google est collée avec `django-allauth` sans réflexion sur le domaine
- Les règles d’autorisation sont dispersées dans les vues, les mixins, les serializers et les templates
- Les rôles sont gérés via des Groupes Django de façon opaque
- Aucune séparation claire entre **Identité**, **Authentification** et **Autorisation**
- L’évolution vers le multi-tenant, les permissions par objet ou les politiques contextuelles devient extrêmement coûteuse
- Chaque nouveau projet recommence quasi intégralement le même travail

Aegis part du constat suivant :

> La gestion des identités et des accès est un **domaine métier à part entière**.  
> Elle mérite d’être modélisée comme telle, et non comme un simple détail technique de Django.

---

## 3. Philosophie & Principes

### 3.1 Domain-Driven Design (pragmatique)

Nous appliquons DDD de façon **pragmatique**, pas dogmatique.

- Identification claire de **Bounded Contexts**
- Langage ubiquitaire strict à l’intérieur de chaque contexte
- Aggregates, Entities et Value Objects pour les concepts centraux
- Domain Services pour les règles qui ne appartiennent pas naturellement à un Aggregate
- Événements de domaine pour découpler les contextes

Nous refusons la pureté extrême qui rendrait le projet inutilisable pour la majorité des développeurs Django.

### 3.2 Clean Architecture / Hexagonal Architecture

Le domaine est au centre.  
Tout le reste (Django, allauth, base de données, OAuth, email, cache…) est un **détail d’infrastructure**.

Les dépendances pointent toujours vers l’intérieur :

```
Interface Adapters  →  Application Layer  →  Domain Layer
         ↑                    ↑
   Infrastructure  ←──────────┘
```

### 3.3 Principes directeurs

| Principe | Application dans Aegis |
|---------|------------------------|
| **Séparation Identité / Authentification / Autorisation** | Trois contextes distincts |
| **Le domaine ne connaît pas Django** | Anti-Corruption Layer systématique |
| **Progressivité** | On peut commencer simple et monter en puissance |
| **Explicitité** | Les règles métier sont nommées et centralisées |
| **Réutilisabilité réelle** | Package + modèle de domaine + ports |
| **Documentation comme produit** | La qualité de la doc fait partie de la valeur |

---

## 4. Architecture globale

Aegis est structuré autour de trois grands axes :

1. **Un modèle de domaine riche** (Identity + Authentication + Authorization)
2. **Une couche d’application** (Use Cases / Application Services)
3. **Des adapters d’infrastructure** (Django ORM, allauth, Google OAuth, etc.)

Le projet peut être utilisé de deux manières :

- **Mode simple** : on consomme les adapters Django fournis et on ignore largement le domaine
- **Mode avancé** : on travaille directement avec le domaine, les Use Cases et les ports

Cette dualité est volontaire. Elle permet une adoption progressive.

---

## 5. Bounded Contexts

### 5.1 Identity Context

**Responsabilité** : Répondre à la question « Qui est cette personne ? »

Concepts principaux :
- Identity (Aggregate root)
- EmailAddress (Value Object)
- Profile information
- Statut de vérification
- Statut du compte (actif, suspendu, archivé…)

Ce contexte ne s’occupe **pas** de savoir comment la personne s’authentifie, ni de ce qu’elle a le droit de faire.

### 5.2 Authentication Context

**Responsabilité** : Répondre à la question « Comment prouve-t-elle son identité ? »

Concepts principaux :
- AuthenticationMethod (Local Password, Google, futur Passkey, Magic Link…)
- Credential
- Challenge / Verification
- Session / Token (représentation abstraite)
- AuthenticationProvider

Ce contexte collabore avec Identity, mais reste distinct.

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

### 7.1 Domain Layer

- Aucune dépendance vers Django, allauth, ou quelque framework que ce soit
- Pure Python
- Contient les règles métier, les invariants et le langage ubiquitaire

### 7.2 Application Layer

- Contient les **Use Cases** (RegisterIdentity, AuthenticateWithPassword, AuthenticateWithGoogle, AssignRole, CheckPermission…)
- Orchestre les Aggregates et les Domain Services
- Définit les **Ports** (interfaces) vers l’extérieur

### 7.3 Interface Adapters

- Traduction entre le monde extérieur et le domaine
- Adapters Django (views, DRF viewsets, admin, management commands)
- Adapters allauth (custom adapters qui traduisent les signaux/événements allauth en commandes du domaine)

### 7.4 Infrastructure

- Implémentation concrète des ports
- Django ORM
- django-allauth
- Google OAuth
- Système de mail
- Cache / sessions
- etc.

---

## 8. Authentification

Aegis s’appuie sur `django-allauth` comme **adapter d’infrastructure**, pas comme cœur métier.

### 8.1 Méthodes supportées (v1)

- Email + Password
- Google OAuth 2.0

### 8.2 Principes

- Le Custom User Model Django est un **modèle d’infrastructure** qui mappe vers l’Aggregate `Identity`
- Les flux allauth sont capturés via une Anti-Corruption Layer
- Les règles métier (ex. : « un compte Google nouvellement créé reçoit automatiquement le rôle X ») vivent dans le domaine ou dans les Use Cases, pas dans les templates ou les vues allauth

### 8.3 Extensibilité

L’architecture est conçue pour accueillir facilement :
- Magic Links
- Passkeys / WebAuthn
- 2FA / MFA
- SSO entreprise (SAML / OIDC)

sans modifier le cœur du domaine.

---

## 9. Autorisation & RBAC

### 9.1 Approche initiale (v1)

- RBAC classique basé sur des Rôles et des Permissions
- S’appuie sur le système de Groupes/Permissions de Django en infrastructure, tout en exposant un modèle de domaine plus riche et explicite
- Helpers et services de domaine pour interroger les droits de façon claire

### 9.2 Évolutions prévues

- Permissions contextualisées (par Organisation, par projet…)
- Object-level permissions
- Évolution progressive vers un moteur de politiques plus riche (ABAC / PBAC) si nécessaire

### 9.3 Principe directeur

> L’autorisation est une question de **domaine**, pas une question de décorateur dispersé dans les vues.

Les checks d’autorisation passent par le `AuthorizationService` du domaine (ou une façade application).

---

## 10. Décisions de conception majeures

| Décision | Justification |
|---------|---------------|
| Custom User Model dès le départ | Best practice Django absolue |
| Séparation Identity / Authentication / Authorization | Clarté du langage et évolutivité |
| allauth comme adapter, pas comme domaine | Évite de couvrir le domaine avec une librairie |
| DDD pragmatique | Équilibre entre pureté et adoptabilité |
| Support progressif du multi-tenant | Évite le refactoring douloureux plus tard |
| Documentation extrêmement détaillée | La qualité de la doc est un produit en soi |
| Double mode d’utilisation (simple / avancé) | Réduit la barrière d’entrée |

---

## 11. Ce que Aegis n’est pas

- Ce n’est **pas** un Identity Provider complet (Keycloak, Zitadel, Authentik…)
- Ce n’est **pas** un boilerplate SaaS complet avec billing, teams, etc.
- Ce n’est **pas** une solution « zero-config » magique qui cache toute la complexité
- Ce n’est **pas** une réinvention d’allauth ou du système d’auth de Django

Aegis est une **fondation architecturée** pour construire des systèmes d’identité et d’accès solides **à l’intérieur** de projets Django.

---

## 12. Public cible

- Développeurs et équipes qui démarrent un nouveau projet Django sérieux
- Freelances et agences qui en ont assez de reconstruire la même base à chaque mission
- Projets qui anticipent une évolution vers le multi-tenant ou des règles d’accès plus complexes
- Développeurs intéressés par DDD et Clean Architecture dans l’écosystème Django
- Mainteneurs qui veulent un socle clair, testable et documenté

---

## 13. Valeur ajoutée par rapport à l’existant

La plupart des solutions existantes se situent sur l’un de ces axes :

- Configuration + wrappers autour d’allauth
- Boilerplates SaaS très complets (et souvent complexes ou payants)
- Bibliothèques RBAC purement techniques

Aegis se différencie par :

1. **Un vrai modèle de domaine** d’Identity & Access
2. **Une architecture Clean / Hexagonale** assumée
3. **Une séparation claire** des contextes
4. **Une progressivité** d’utilisation
5. **Une documentation de niveau produit**
6. **Une intention de maintenance long terme**

Il ne prétend pas être le plus complet. Il prétend être le plus **proprement architecturé** et le plus **évolutif** dans sa catégorie.

---

## 14. Roadmap

### Phase 1 — Fondation (actuelle)
- Modèle de domaine Identity + Authentication + Authorization
- Intégration allauth (email/password + Google)
- RBAC classique
- Adapters Django de base
- Documentation approfondie

### Phase 2 — Robustesse
- Tests de domaine exhaustifs
- Audit logging de base
- Meilleure gestion des erreurs et des événements
- Amélioration de l’expérience développeur

### Phase 3 — Évolution
- Support multi-tenant (Organizations)
- Permissions contextualisées
- Hooks pour 2FA / Passkeys
- Mode API-first (DRF) plus abouti

### Phase 4 — Maturité
- Moteur de politiques plus riche (optionnel)
- Exemples d’intégration avancés
- Packaging et versioning stables
- Éventuelle communauté

---

## 15. Principes de contribution

- Toute contribution doit respecter les Bounded Contexts et le langage ubiquitaire
- Le Domain Layer doit rester pur (aucune dépendance framework)
- Les règles métier appartiennent au domaine ou aux Use Cases, jamais aux adapters
- La documentation est considérée comme une partie critique du code
- Les décisions d’architecture importantes font l’objet d’ADR (Architecture Decision Records)

---

## 16. Licence

MIT License

---

**Aegis** — *Protect the identity. Control the access. Own the domain.*