# Guide de Contribution Aegis IAM

Bienvenue dans le projet Aegis IAM ! Nous apprécions votre intérêt pour contribuer à ce moteur IAM universel et open source.

## 🎯 Philosophie de Contribution

Aegis suit une approche **Domain-Driven Design (DDD)** et **Clean Architecture** rigoureuse. Toute contribution doit respecter ces principes architecturaux :

- **Domain Layer Pure** : Le cœur (`aegis-core/domain`) doit rester 100% Pure Python sans dépendances externes
- **Infrastructure Isolée** : Toute logique liée aux frameworks (Django, FastAPI, SQLAlchemy) va dans `aegis-drivers`
- **Contrats Pluggables** : Les extensions se font via interfaces abstraites, pas par héritage direct
- **Testabilité Maximale** : Le code doit être testable sans infrastructure lourde

## 🚀 Processus de Contribution

### 1. Fork et Clone

```bash
# Forker le dépôt sur GitHub
git clone https://github.com/votre-username/Keystone-ivory-ratchet.git
cd Keystone-ivory-ratchet
git remote add upstream https://github.com/original-repo/Keystone-ivory-ratchet.git
```

### 2. Créer une Branche

```bash
git checkout -b feature/ma-nouvelle-fonctionnalité
# ou
git checkout -b fix/correction-bug-123
```

### 3. Installer l'Environnement de Développement

```bash
# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate

# Installer les dépendances
pip install -e ".[dev,sqlalchemy,redis]"

# Installer les dépendances de test
pip install pytest pytest-cov mypy ruff
```

### 4. Lancer les Tests

```bash
# Tests unitaires (rapides, Pure Python)
pytest tests/test_domain.py -v
pytest tests/test_new_components.py -v

# Tests d'intégration (requiert infrastructure)
pytest tests/test_fastapi_driver.py -v

# Tous les tests avec couverture
pytest tests/ -v --cov=src/aegis --cov-report=html
```

### 5. Linter et Type Checking

```bash
# Linter
ruff check src/ tests/

# Formatter
ruff format src/ tests/

# Type checking
mypy src/aegis/
```

### 6. Créer un Commit

```bash
git add .
git commit -m "feat: ajouter fonctionnalité X

- Description détaillée de la fonctionnalité
- Impact sur l'architecture
- Tests ajoutés

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
```

### 7. Push et Créer une Pull Request

```bash
git push origin feature/ma-nouvelle-fonctionnalité
```

Ensuite, créez une Pull Request sur GitHub avec :
- Description claire des changements
- Référence aux issues pertinentes
- Captures d'écran si applicable
- Tests passants

## 📋 Normes de Code

### Style

- **Linter** : Ruff (configuration dans `pyproject.toml`)
- **Formatter** : Ruff (auto-formatting)
- **Type Hints** : MyPy strict mode obligatoire
- **Line Length** : 120 caractères maximum

### Structure des Fichiers

```
src/aegis/
├── core/                    # Pure Python (zéro dépendance externe)
│   ├── domain/              # Entities, Value Objects, Domain Events
│   ├── application/         # Use Cases, DTOs, Ports/Interfaces
│   └── policies/            # Policy Engines (RBAC, ABAC, ReBAC)
├── drivers/                 # Adaptateurs d'infrastructure
│   ├── fastapi/             # REST API FastAPI
│   ├── sqlalchemy/          # Driver SQLAlchemy
│   └── inmemory/            # Driver In-Memory pour tests
└── sdk/                     # Façade SDK pour développeurs
```

### Conventions de Nommage

- **Classes** : `PascalCase` (ex: `HumanIdentity`, `PolicyEngine`)
- **Fonctions/Méthodes** : `snake_case` (ex: `create_session`, `validate_permission`)
- **Constantes** : `UPPER_SNAKE_CASE` (ex: `MAX_SESSIONS_PER_USER`)
- **Privées** : Préfix `_` (ex: `_internal_method`)

### Documentation

- **Docstrings** : Google Style ou NumPy Style pour tous les modules, classes, fonctions publiques
- **Comments** : Utiliser uniquement pour expliquer le "pourquoi", pas le "quoi"
- **Type Hints** : Obligatoires pour toutes les fonctions publiques

## 🏗️ Architecture Décision Records (ADR)

Les décisions architecturales majeures doivent être documentées via des ADR dans le dossier `docs/architecture/adr/` :

### Format ADR

```markdown
# ADR-001: Choix de Clean Architecture pour Aegis

## Statut
Accepté

## Contexte
Pourquoi cette décision a été nécessaire...

## Décision
Description de la décision architecturale...

## Conséquences
Impact positif et négatif...
```

## 🧪 Guidelines de Tests

### Pyramide de Tests

1. **Tests Unitaires (80%)** : Tests Pure Python sans infrastructure
   - Cible : `aegis-core/domain`, `aegis-core/application`
   - Vitesse : < 1s par test
   - Mock : Utiliser `unittest.mock` pour les dépendances

2. **Tests d'Intégration (15%)** : Tests avec infrastructure réelle
   - Cible : `aegis-drivers`, `tests/integration/`
   - Vitesse : < 10s par test
   - Infrastructure : Docker Compose pour PostgreSQL, Redis

3. **Tests E2E (5%)** : Tests de bout en bout
   - Cible : `tests/e2e/`
   - Vitesse : < 30s par test
   - Scénarios : Flux utilisateur complets

### Conventions de Tests

```python
class TestExample(unittest.TestCase):
    def setUp(self) -> None:
        """Initialisation commune aux tests."""
        self.container = AegisContainer()
    
    def test_feature_success(self) -> None:
        """Teste qu'une fonctionnalité fonctionne correctement."""
        result = self.container.client.can("user-1", "document:read")
        self.assertTrue(result)
    
    def test_feature_error_handling(self) -> None:
        """Teste la gestion d'erreurs."""
        with self.assertRaises(ValueError):
            self.container.client.register_human(email="invalid")
```

## 🔒 Sécurité

### Principes de Sécurité

- **Jamais de secrets en clair** : Utiliser les variables d'environnement
- **Validation Stricte** : Toutes les entrées doivent être validées
- **Audit Trail** : Toutes les actions sensibles doivent être auditées
- **Rate Limiting** : Protéger contre les attaques par force brute

### Review de Sécurité

Toute contribution touchant à :
- L'authentification
- L'autorisation
- La gestion des sessions
- Le stockage de données personnelles

Doit passer un review de sécurité approfondi.

## 📚 Types de Contributions

### Bug Fixes

- Priorité aux bugs critiques et majeurs
- Inclure un test qui reproduit le bug
- Documenter la cause racine

### Nouvelles Fonctionnalités

- Ouvrir une issue de discussion d'abord
- Éviter le "scope creep" (dérapement de périmètre)
- Respecter l'architecture existante

### Documentation

- Mise à jour du README pour les changements utilisateur
- Ajout de docstrings pour le code public
- Création de tutoriels pour les nouvelles fonctionnalités

### Refactoring

- Justifier l'amélioration dans la PR
- Maintenir la compatibilité API
- Inclure des tests de régression

## 🤝 Communication

### GitHub Issues

- **Bugs** : Template avec reproduction steps, environnement attendu
- **Features** : Description détaillée, cas d'usage, impact sur l'architecture
- **Questions** : Poser des questions ciblées, éviter les généralités

### Pull Requests

- **Titre** : `feat: description courte` ou `fix: description courte`
- **Description** : Explication claire du "quoi" et du "comment"
- **Tests** : Démontrer que les tests passent
- **Documentation** : Mentionner les docs mises à jour

### Code Review

- **Constructif** : Feedback objectif, focus sur le code et l'architecture
- **Respectueux** : Critiquer le code, pas la personne
- **Collaboratif** : Être ouvert aux suggestions et itérer

## 🛠️ Outils Recommandés

### IDE

- **VS Code** avec extensions Python, Ruff, MyPy
- **PyCharm** Community Edition

### Outils de Ligne de Commande

```bash
# Développement
ruff check src/          # Linter
ruff format src/         # Formatter
mypy src/aegis/         # Type checking
pytest tests/            # Tests

# Git
git status
git diff
git log --oneline -10
```

### Docker

```bash
# Environnement de développement
docker-compose up -d

# Tests avec infrastructure
docker-compose run --rm aegis-api pytest tests/integration/

# Nettoyage
docker-compose down -v
```

## 🌟 Processus de Release

### Versioning

Aegis utilise **Semantic Versioning** (MAJEUR.MINEUR.PATCH) :
- **MAJEUR** : Changements breaking de l'API publique
- **MINEUR** : Nouvelles fonctionnalités rétrocompatibles
- **PATCH** : Bug fixes rétrocompatibles

### Changelog

Un changelog est généré automatiquement dans `CHANGELOG.md` basé sur les messages de commit qui suivent le format Conventional Commits.

### Publication

Les releases sont gérées par les maintainers via GitHub Actions.

## 📞 Obtenir de l'Aide

### Canaux

- **GitHub Issues** : Pour les bugs et discussions techniques
- **GitHub Discussions** : Pour les questions générales et idées
- **Email** : Pour les questions de sécurité sensibles

### Response Time

Les maintainers visent à répondre dans les 48h ouvrées pour les questions importantes.

## ⚡ Quick Start pour les Contributeurs

```bash
# 1. Fork et clone
git clone https://github.com/votre-username/Keystone-ivory-ratchet.git
cd Keystone-ivory-ratchet

# 2. Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Branch
git checkout -b feature/ma-contribution

# 4. Développement et tests
pytest tests/ -v
ruff check src/

# 5. Commit et push
git add .
git commit -m "feat: ma contribution"
git push origin feature/ma-contribution

# 6. PR sur GitHub
```

## 🎓 Ressources d'Apprentissage

- **Clean Architecture** : https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- **Domain-Driven Design** : https://domainlanguage.com/ddd/
- **Python Testing** : https://docs.pytest.org/
- **Type Hints** : https://docs.python.org/3/library/typing.html

## 🏆 Reconnaissance

Les contributeurs sont reconnus dans le fichier `CONTRIBUTORS.md` et dans les notes de release de chaque version.

---

**Merci de contribuer à Aegis IAM !** 🚀

N'oubliez pas : ce projet vise l'excellence architecturale (Standard 20/20). Chaque contribution compte vers cet objectif.