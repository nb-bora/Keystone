# Changelog

All notable changes to Aegis IAM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Core Architecture: Clean Architecture avec Domain-Driven Design
- Configuration System: Système de configuration déclarative YAML avec substitution de variables d'environnement
- Anti-Corruption Layer: Data Mapper et Unit of Work pour isoler le Domain de l'infrastructure
- Validation Engine: Système de validation personnalisable avec registry et validateurs configurables
- ABAC Policy Engine: Implémentation complète avec conditions temporelles, IP, ressources, custom
- ReBAC Policy Engine: Système de graphes de relations style Google Zanzibar
- Role System: Rôles avec héritage, permissions, système de résolution de hiérarchie
- Multi-Tenancy: Isolation row_level/database/schema, hiérarchies Enterprise->Org->Workspace->Project
- Authentication Strategies: Password, OIDC, Magic Link, M2M Token avec manager unifié
- Transactional Outbox: Worker asynchrone, retry logic, publishers HTTP/Redis/Console
- Session Management: Création, révocation globale, security policy, multi-device
- GDPR Pipeline: Anonymisation, droit à l'oubli, export de données, consent management
- Plugin System: Hooks d'extension avec priorités, chargement dynamique, decorators
- Domain Events: 15 nouveaux événements (auth, autorisation, RGPD, sessions, tenants)
- Alembic Migrations: Configuration complète avec support async/sync, schéma initial complet
- Unit Tests: Pyramide de tests unitaires pour tous les nouveaux composants
- Documentation: Guide de contribution détaillé (CONTRIBUTING.md)
- API Documentation: Documentation API complète avec exemples

### Changed
- Architecture: Migration vers Clean Architecture stricte
- Code Quality: Introduction de Ruff pour linting et formatting
- Type Safety: MyPy strict mode activé

### Deprecated
- None

### Removed
- None

### Fixed
- None

### Security
- Implementation de l'anonymisation des IP dans les logs d'audit
- Validation stricte des entrées configurables
- Politique de sessions avec timeout et révocation

## [0.1.0] - 2026-09-03

### Added
- Initial release of Aegis IAM
- Core domain entities (HumanIdentity, ServiceAccount, ApiKeyActor, AIAgentActor)
- RBAC Policy Engine implementation
- In-memory driver for testing
- FastAPI REST API driver
- SQLAlchemy database driver
- Basic health check endpoints
- Audit outbox system (in-memory)
- Domain events (SubjectRegisteredEvent, SubjectStatusChangedEvent)
- Value objects (SubjectId, TenantId, PermissionCode, EmailAddress, EvaluationContext)
- Application ports (SubjectRepository, EventOutbox, PasswordHasher)
- Docker Compose infrastructure (PostgreSQL, Redis, Prometheus, Grafana)
- Pre-commit hooks configuration
- Basic unit tests

### Changed
- Initial public API structure

### Security
- PBKDF2 password hashing with configurable iterations
- Basic subject activation/suspension

## [0.0.1] - 2026-08-01

### Added
- Project initialization
- Basic package structure
- Initial README documentation
- pyproject.toml configuration

---

## Versioning Guide

Aegis IAM follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality in a backwards compatible manner
- **PATCH**: Backwards compatible bug fixes

### Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v0.1.0 -m "Release v0.1.0"`
4. Push tag: `git push origin v0.1.0`
5. GitHub Actions will automatically build and publish to PyPI

### Breaking Changes Policy

Breaking changes will be:
- Documented in the CHANGELOG
- Announced in advance via GitHub Issues
- Accompanied by migration guides when possible
- Minimized and justified by significant benefits

---

## Conventional Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Maintenance tasks
- `perf:` Performance improvements
- `ci:` CI/CD changes

Example:
```
feat(authentication): add OIDC authentication strategy

- Added OIDCAuthStrategy with Google/GitHub/Microsoft support
- Implemented token exchange flow
- Added unit tests for OIDC authentication
- Updated API documentation with OIDC examples

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```