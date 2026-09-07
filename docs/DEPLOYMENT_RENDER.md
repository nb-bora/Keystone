# Guide de Déploiement sur Render.com

## 📋 Prérequis

- Compte Render.com (gratuit ou payant)
- Compte GitHub
- Applications OAuth configurées (Google, GitHub, LinkedIn)
- Docker installé localement (pour tests)

## 🚀 Étape 1: Préparation du Repository

### 1.1 Créer un fichier `render.yaml`

Créez un fichier `render.yaml` à la racine du projet:

```yaml
services:
  - type: web
    name: aegis-iam-api
    env: python
    buildCommand: pip install -e ".[fastapi,sqlalchemy]"
    startCommand: uvicorn aegis.drivers.fastapi.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
      - key: PORT
        value: 8000
      - key: DATABASE_URL
        fromDatabase:
          name: aegis-postgres
          property: connectionString
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: GOOGLE_CLIENT_SECRET
        sync: false
      - key: GITHUB_CLIENT_ID
        sync: false
      - key: GITHUB_CLIENT_SECRET
        sync: false
      - key: LINKEDIN_CLIENT_ID
        sync: false
      - key: LINKEDIN_CLIENT_SECRET
        sync: false

databases:
  - name: aegis-postgres
    databaseName: aegis_iam
    user: aegis_user
```

### 1.2 Créer un fichier `Dockerfile` (si nécessaire)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[fastapi,sqlalchemy]"

EXPOSE 8000

CMD ["uvicorn", "aegis.drivers.fastapi.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.3 Créer un fichier `.renderignore`

```
.git
.gitignore
__pycache__
*.pyc
.env
.venv
docs
tests
*.md
```

## 🗄️ Étape 2: Configuration de la Base de Données

### 2.1 Créer une instance PostgreSQL sur Render

1. Connectez-vous à Render.com
2. Cliquez sur "New" → "PostgreSQL"
3. Configurez:
   - **Name**: `aegis-postgres`
   - **Database**: `aegis_iam`
   - **User**: `aegis_user`
   - **Region**: Choisissez la région la plus proche de vos utilisateurs
   - **Plan**: Free (dev) ou Paid (production)
4. Cliquez sur "Create Database"

### 2.2 Récupérer les informations de connexion

Render va générer automatiquement:
- **Internal Database URL**: Pour les connexions depuis Render
- **External Database URL**: Pour les connexions externes

Sauvegardez ces informations.

## 🔐 Étape 3: Configuration OAuth

### 3.1 Google OAuth

1. Allez sur [Google Cloud Console](https://console.cloud.google.com)
2. Créez ou sélectionnez un projet
3. Activez "Google+ API" ou "Google Identity"
4. Créez des identifiants OAuth 2.0:
   - **Type**: Web application
   - **Authorized redirect URIs**: `https://your-app-name.onrender.com/api/v1/auth/oauth/callback/google`
5. Copiez **Client ID** et **Client Secret**

### 3.2 GitHub OAuth

1. Allez sur [GitHub Developer Settings](https://github.com/settings/developers)
2. Cliquez "New OAuth App"
3. Configurez:
   - **Application name**: `Aegis IAM - Render`
   - **Homepage URL**: `https://your-app-name.onrender.com`
   - **Authorization callback URL**: `https://your-app-name.onrender.com/api/v1/auth/oauth/callback/github`
4. Copiez **Client ID** et **Client Secret**

### 3.3 LinkedIn OAuth

1. Allez sur [LinkedIn Developer Portal](https://www.linkedin.com/developers)
2. Créez une nouvelle application
3. Configurez:
   - **Redirect URLs**: `https://your-app-name.onrender.com/api/v1/auth/oauth/callback/linkedin`
4. Copiez **Client ID** et **Client Secret**

## 🌐 Étape 4: Déploiement sur Render

### 4.1 Connecter GitHub à Render

1. Sur Render.com, cliquez sur "New" → "Web Service"
2. Sélectionnez "Connect GitHub"
3. Autorisez Render à accéder à votre repository
4. Sélectionnez le repository `Keystone` et la branche `ivory-ratchet`

### 4.2 Configurer le Web Service

#### Option A: Utiliser `render.yaml` (Recommandé)

Si vous avez créé le fichier `render.yaml`, Render détectera automatiquement la configuration.

#### Option B: Configuration Manuelle

1. **Name**: `aegis-iam-api`
2. **Region**: Choisissez la même région que la base de données
3. **Branch**: `ivory-ratchet`
4. **Runtime**: `Python 3`
5. **Build Command**:
   ```bash
   pip install -e ".[fastapi,sqlalchemy]"
   ```
6. **Start Command**:
   ```bash
   uvicorn aegis.drivers.fastapi.app:app --host 0.0.0.0 --port $PORT
   ```

### 4.3 Configurer les Variables d'Environnement

Ajoutez les variables d'environnement suivantes dans la section "Environment":

#### Variables Système
```
PYTHON_VERSION=3.11
PORT=8000
```

#### Variables Base de Données
Render ajoute automatiquement `DATABASE_URL` depuis la base de données PostgreSQL.

#### Variables OAuth
```
GOOGLE_CLIENT_ID=votre-google-client-id
GOOGLE_CLIENT_SECRET=votre-google-client-secret
GITHUB_CLIENT_ID=votre-github-client-id
GITHUB_CLIENT_SECRET=votre-github-client-secret
LINKEDIN_CLIENT_ID=votre-linkedin-client-id
LINKEDIN_CLIENT_SECRET=votre-linkedin-client-secret
```

**Important**: Cochez "Sensitive" pour les secrets (CLIENT_SECRET).

### 4.4 Lancer le Déploiement

Cliquez sur "Create Web Service". Render va:
1. Cloner le repository
2. Installer les dépendances
3. Exécuter le serveur FastAPI
4. Configurer un load balancer
5. Générer une URL HTTPS

## 🧪 Étape 5: Vérification du Déploiement

### 5.1 Vérifier les Logs

1. Allez sur le web service "aegis-iam-api"
2. Cliquez sur "Logs"
3. Vérifiez qu'il n'y a pas d'erreurs
4. Cherchez "Application started successfully"

### 5.2 Tester les Endpoints

#### Health Check
```bash
curl https://your-app-name.onrender.com/health/live
```

Devrait retourner:
```json
{
  "status": "ok",
  "service": "aegis-api",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Swagger UI
Ouvrez dans votre navigateur:
```
https://your-app-name.onrender.com/docs
```

#### Liste des Providers OAuth
```bash
curl https://your-app-name.onrender.com/api/v1/auth/oauth/providers
```

Devrait retourner:
```json
[
  {
    "name": "google",
    "display_name": "Google"
  },
  {
    "name": "github",
    "display_name": "GitHub"
  },
  {
    "name": "linkedin",
    "display_name": "LinkedIn"
  }
]
```

## 🔧 Étape 6: Configuration Production

### 6.1 Migrations de Base de Données

Créez un script de migration:

```python
# scripts/migrate_render.py
import asyncio
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

async def run_migrations():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Créer les tables Aegis
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS subjects (
                id VARCHAR(255) PRIMARY KEY,
                subject_type VARCHAR(50) NOT NULL,
                tenant_id VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                subject_id VARCHAR(255) REFERENCES subjects(id),
                permission_code VARCHAR(255) NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.commit()
    
    print("Migrations completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
```

Exécutez le script via Render Shell:
```bash
python scripts/migrate_render.py
```

### 6.2 Configuration CORS

Mettez à jour `aegis.config.yaml` ou les variables d'environnement:

```yaml
aegis:
  cors_origins:
    - "https://your-frontend-app.onrender.com"
    - "https://your-app-name.onrender.com"
```

Ou via variables d'environnement:
```
CORS_ORIGINS=https://your-frontend-app.onrender.com,https://your-app-name.onrender.com
```

### 6.3 Monitoring

#### Activer les métriques
```bash
curl https://your-app-name.onrender.com/metrics
```

#### Configurer les alertes Render
1. Allez sur "Settings" → "Alerts"
2. Configurez les alertes pour:
   - CPU > 80%
   - Memory > 80%
   - Response time > 1s
   - Error rate > 5%

## 🔄 Étape 7: Mise à jour Continue

### 7.1 Configuration Auto-Deploy

Render déploie automatiquement lors de chaque push sur la branche configurée.

Pour contrôler quand déployer:

1. Allez sur "Settings" → "Auto-Deploy"
2. Désactivez "Auto-Deploy" si nécessaire
3. Déployez manuellement via "Manual Deploy"

### 7.2 Configuration Zero-Downtime

Render utilise déjà zero-downtime deploys par défaut.

Pour optimiser:
1. Utilisez des health checks
2. Configurez les timeouts
3. Utilisez des connexions DB persistantes

## 📊 Étape 8: Monitoring et Debugging

### 8.1 Logs en Temps Réel

```bash
# Via Render CLI
render logs aegis-iam-api

# Via Dashboard
Services → aegis-iam-api → Logs
```

### 8.2 Shell Access

```bash
# Via Render CLI
render shell aegis-iam-api

# Commandes utiles
python -c "import aegis; print(aegis.__version__)"
python -m pytest tests/
```

### 8.3 Metrics Integration

Intégrez avec Prometheus/Grafana:

```python
# Dans aegis/drivers/fastapi/app.py
from prometheus_client import make_asgi_app

app.mount("/metrics", make_asgi_app())
```

## 🚨 Étape 9: Gestion des Erreurs

### 9.1 Erreurs Courantes

#### Erreur: "Module not found"
**Solution**: Vérifiez que toutes les dépendances sont dans `pyproject.toml`

#### Erreur: "Database connection failed"
**Solution**: Vérifiez que `DATABASE_URL` est correctement configuré

#### Erreur: "OAuth redirect URI mismatch"
**Solution**: Mettez à jour les redirect URIs dans les applications OAuth

#### Erreur: "Port already in use"
**Solution**: Utilisez `$PORT` au lieu d'un port hardcoded

### 9.2 Rollback

Si un déploiement échoue:
1. Render rollback automatiquement
2. Ou allez sur "Deploys" → Cliquez sur le déploiement précédent → "Redeploy"

## 🎯 Étape 10: Performance Optimization

### 10.1 Caching

Ajoutez Redis pour le cache:

```yaml
# render.yaml
services:
  - type: redis
    name: aegis-redis
    maxmemory: 256
```

### 10.2 Scaling

Configurez le scaling dans Render:
1. Allez sur "Settings" → "Scale"
2. Configurez:
   - **Min instances**: 1 (dev) ou 2 (prod)
   - **Max instances**: 10
   - **CPU threshold**: 60%
   - **Memory threshold**: 60%

## 📝 Checklist de Déploiement

- [ ] Repository GitHub connecté à Render
- [ ] Base de données PostgreSQL créée
- [ ] Applications OAuth configurées
- [ ] Variables d'environnement configurées
- [ ] `render.yaml` créé
- [ ] Web service déployé
- [ ] Health check passant
- [ ] Swagger UI accessible
- [ ] OAuth providers listés
- [ ] Migrations exécutées
- [ ] CORS configuré
- [ ] Monitoring activé
- [ ] Alertes configurées
- [ ] Zero-downtime déploy testé

## 🔗 Liens Utiles

- [Render Documentation](https://render.com/docs)
- [Render Python Guide](https://render.com/docs/deploy-python)
- [Render PostgreSQL Guide](https://render.com/docs/databases-postgresql)
- [Aegis IAM Documentation](./OAUTH.md)

## 💡 Pro Tips

1. **Utilisez Render CLI** pour une gestion plus rapide
2. **Configurez les secrets** dès le début (ne les exposez jamais)
3. **Testez localement** avec les mêmes variables d'environnement
4. **Utilisez des health checks** pour le monitoring
5. **Configurez les timeouts** pour éviter les connexions bloquées
6. **Utilisez des connexions DB persistantes** pour améliorer la performance
7. **Activez les logs structurés** pour un meilleur debugging
8. **Configurez les alertes** pour être notifié des problèmes
9. **Utilisez zero-downtime deploys** pour éviter les interruptions
10. **Documentez votre configuration** pour les futurs déploiements

## 🎉 Déploiement Réussi!

Votre application Aegis IAM est maintenant déployée sur Render.com avec:
- ✅ Base de données PostgreSQL
- ✅ Authentification OAuth 2.0 (Google, GitHub, LinkedIn)
- ✅ API REST FastAPI
- ✅ Documentation Swagger
- ✅ Monitoring et alertes
- ✅ Zero-downtime deploys
- ✅ Scaling automatique

Vous pouvez maintenant accéder à votre application via:
```
https://your-app-name.onrender.com
```
