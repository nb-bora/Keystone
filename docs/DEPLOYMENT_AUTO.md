# Configuration du Déploiement Automatique sur Render avec Notifications Discord

## 📋 Vue d'ensemble

Ce guide configure:
- ✅ Déploiement automatique sur Render lors du merge vers `main`
- ✅ Notifications Discord pour succès/échec du déploiement
- ✅ Intégration GitHub Actions → Render → Discord

## 🎯 Flux Complet

```
┌─────────────────────────────────────────────────────────┐
│              PR Merge vers main                        │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Push sur main
                     │
┌─────────────────────────────────────────────────────────┐
│          GitHub Actions Triggered                       │
│  .github/workflows/deploy-notify.yml                  │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Notification Discord: Début
                     │
┌─────────────────────────────────────────────────────────┐
│              Render Auto-Deploy                         │
│  (déploye automatiquement depuis main)                 │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Succès ou Échec
                     │
┌─────────────────────────────────────────────────────────┐
│          GitHub Actions Check Status                    │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Notification Discord: Résultat
                     │
┌─────────────────────────────────────────────────────────┐
│            Discord Message Final                        │
│  ✅ Succès: URL de l'application                       │
│  ❌ Échec: Message d'erreur                              │
└─────────────────────────────────────────────────────────┘
```

## 🔧 Étape 1: Configuration Discord Webhook

### 1.1 Créer un Serveur Discord (si nécessaire)

1. Connectez-vous à Discord
2. Cliquez sur "+" pour créer un serveur
3. Nommez-le "Aegis IAM Deployments"

### 1.2 Créer un Channel pour les Notifications

1. Dans votre serveur Discord
2. Cliquez sur "+" → "Create Channel"
3. Nommez-le "deployments"
4. Configurez comme "Text Channel"
5. Cliquez sur "Create Channel"

### 1.3 Créer le Webhook

1. Cliquez sur le channel "deployments"
2. Cliquez sur les paramètres du channel (⚙️)
3. Allez dans "Integrations" → "Webhooks"
4. Cliquez "New Webhook"
5. Configurez:
   - **Name**: Aegis IAM Bot
   - **Avatar**: Upload une image (optionnel)
6. Cliquez "Copy Webhook URL"
7. **Important**: Sauvegardez cette URL!

**Exemple de Webhook URL:**
```
https://discord.com/api/webhooks/1234567890/ABCDEFghijklmnop
```

## 🔐 Étape 2: Configuration GitHub Secrets

### 2.1 Ajouter le Webhook Discord aux Secrets GitHub

1. Allez sur votre repository GitHub
2. Cliquez sur "Settings" → "Secrets and variables" → "Actions"
3. Cliquez "New repository secret"
4. Configurez:
   - **Name**: `DISCORD_WEBHOOK_URL`
   - **Secret**: Collez votre Discord Webhook URL
5. Cliquez "Add secret"

### 2.2 Autres Secrets Requis (Optionnels)

Si vous avez d'autres secrets à ajouter:
- `DISCORD_WEBHOOK_URL` (Obligatoire)
- `DATABASE_URL` (si nécessaire)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
- `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`

## 🚀 Étape 3: Configuration Render Auto-Deploy

### 3.1 Vérifier la Configuration Render

1. Connectez-vous à Render.com
2. Allez sur votre web service "aegis-iam-api"
3. Cliquez sur "Settings" → "Auto-Deploy"
4. Vérifiez que:
   - ✅ "Auto-Deploy" est activé
   - ✅ Branch: `main`
   - ✅ "Push events" est activé

### 3.2 Configuration Alternative: render.yaml

Le fichier `render.yaml` à la racine du projet configure automatiquement:

```yaml
services:
  - type: web
    name: aegis-iam-api
    env: python
    buildCommand: pip install -e ".[fastapi,sqlalchemy]"
    startCommand: uvicorn aegis.drivers.fastapi.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: aegis-postgres
          property: connectionString
```

### 3.3 Test du Déploiement Automatique

1. Faites un push sur `main`:
   ```bash
   git checkout main
   git merge ivory-ratchet
   git push origin main
   ```

2. Vérifiez Render:
   - Allez sur votre service Render
   - Cliquez sur "Deploys"
   - Vous devriez voir un nouveau déploiement en cours

3. Vérifiez Discord:
   - Vous devriez recevoir: "🚀 Deployment Started"
   - Après quelques minutes: "✅ Deployment Successful" ou "❌ Deployment Failed"

## 📝 Étape 4: Configuration du Workflow GitHub Actions

Le workflow `.github/workflows/deploy-notify.yml`:

### 4.1 Comportement Actuel

Le workflow actuel:
1. Notifie Discord que le déploiement commence
2. Attend 60 secondes (pour que Render commence)
3. Notifie Discord du succès ou échec

### 4.2 Amélioration Optionnelle: Vérification Réelle du Déploiement

Pour une vérification plus robuste, utilisez l'API Render:

```yaml
- name: Check Render Deployment Status
  id: check_deployment
  run: |
    RENDER_API_KEY=${{ secrets.RENDER_API_KEY }}
    SERVICE_ID=${{ secrets.RENDER_SERVICE_ID }}
    
    # Get latest deployment status
    STATUS=$(curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
      "https://api.render.com/v1/services/$SERVICE_ID/deploys" | \
      jq -r '.[0].status')
    
    echo "status=$STATUS" >> $GITHUB_OUTPUT
    
    if [ "$STATUS" != "live" ]; then
      echo "Deployment not live yet"
      exit 1
    fi
```

Pour cette amélioration, vous aurez besoin de:
- `RENDER_API_KEY`: Clé API Render
- `RENDER_SERVICE_ID`: ID du service Render

## 🧪 Étape 5: Test du Flux Complet

### 5.1 Test Local du Workflow

1. Créez une branche de test:
   ```bash
   git checkout -b test-deploy
   ```

2. Faites un petit changement:
   ```bash
   echo "# Test deployment" >> README.md
   git add README.md
   git commit -m "test: deployment notification"
   ```

3. Pushez sur `test-deploy`:
   ```bash
   git push origin test-deploy
   ```

4. Créez une PR et mergez vers `main`

5. Vérifiez:
   - GitHub Actions tab
   - Discord channel "deployments"
   - Render service

### 5.2 Test du Workflow Manuellement

1. Allez sur GitHub Actions tab
2. Sélectionnez "Deploy to Render and Notify Discord"
3. Cliquez "Run workflow"
4. Choisissez la branche `main`
5. Cliquez "Run workflow"

## 🎨 Étape 6: Personnalisation des Messages Discord

### 6.1 Format du Message Actuel

**Début:**
```
🚀 Deployment Started

Branch: main
Repository: nb-bora/Keystone
Commit: abc123
Author: nb-bora
```

**Succès:**
```
✅ Deployment Successful

Branch: main
Repository: nb-bora/Keystone
Commit: abc123
Author: nb-bora

🌐 URL: https://aegis-iam-api.onrender.com/docs
```

**Échec:**
```
❌ Deployment Failed

Branch: main
Repository: nb-bora/Keystone
Commit: abc123
Author: nb-bora

Please check the logs for details.
```

### 6.2 Personnalisation Avancée

Pour des messages plus riches, vous pouvez utiliser des embeds Discord:

```yaml
- name: Notify Discord - Deployment Success
  run: |
    curl -X POST ${{ secrets.DISCORD_WEBHOOK_URL }} \
      -H "Content-Type: application/json" \
      -d '{
        "embeds": [{
          "title": "✅ Deployment Successful",
          "color": 5763719,
          "fields": [
            {"name": "Branch", "value": "main", "inline": true},
            {"name": "Commit", "value": "${{ github.sha }}", "inline": true},
            {"name": "Author", "value": "${{ github.actor }}", "inline": true}
          ],
          "timestamp": "${{ github.event.head_commit.timestamp }}"
        }]
      }'
```

## 🔍 Étape 7: Dépannage

### 7.1 Discord Webhook Ne Fonctionne Pas

**Problème:** Aucun message Discord reçu

**Solutions:**
1. Vérifiez que `DISCORD_WEBHOOK_URL` est correct dans GitHub Secrets
2. Vérifiez que le webhook est actif dans Discord
3. Vérifiez les logs GitHub Actions pour les erreurs curl

### 7.2 Render Ne Déploie Pas Automatiquement

**Problème:** Render ne se déploie pas après push sur main

**Solutions:**
1. Vérifiez que "Auto-Deploy" est activé dans Render
2. Vérifiez que la branche est bien `main`
3. Vérifiez que le webhook GitHub est connecté à Render

### 7.3 Workflow GitHub Actions Échoue

**Problème:** Le workflow échoue immédiatement

**Solutions:**
1. Vérifiez que `DISCORD_WEBHOOK_URL` existe
2. Vérifiez la syntaxe YAML du workflow
3. Vérifiez les permissions du workflow

## 📊 Étape 8: Monitoring

### 8.1 Dashboard GitHub Actions

1. Allez sur "Actions" tab
2. Vous verrez l'historique des déploiements
3. Cliquez sur un workflow pour voir les logs

### 8.2 Channel Discord

1. Allez sur votre channel "deployments"
2. Vous verrez l'historique des notifications
3. Utilisez les messages pour le suivi rapide

### 8.3 Dashboard Render

1. Allez sur votre service Render
2. Cliquez sur "Deploys"
3. Vous verrez l'historique des déploiements avec timestamps

## 🎯 Checklist de Configuration

- [ ] Serveur Discord créé
- [ ] Channel "deployments" créé
- [ ] Discord Webhook créé et copié
- [ ] Webhook ajouté aux GitHub Secrets
- [ ] Workflow `.github/workflows/deploy-notify.yml` créé
- [ ] Render Auto-Deploy activé sur main
- [ ] `render.yaml` configuré
- [ ] Variables d'environnement Render configurées
- [ ] Test du flux complet effectué
- [ ] Notifications Discord testées
- [ ] Monitoring configuré

## 🚀 Déploiement Automatique Configuré!

Votre système est maintenant configuré pour:

1. ✅ Déploiement automatique sur Render lors du merge vers `main`
2. ✅ Notifications Discord en temps réel
3. ✅ Messages de succès avec URL de l'application
4. ✅ Messages d'erreur pour debugging rapide
5. ✅ Historique complet dans GitHub Actions et Discord

**Prochaine étape:** Mergez votre PR sur `main` et regardez le déploiement automatique en action! 🎉
