#!/usr/bin/env bash
# ==============================================================================
# Script d'Automatisation de Sauvegardes Planifiées pour Aegis IAM
# ==============================================================================
set -euo pipefail

# Configuration
BACKUP_SCRIPT="./scripts/backup_postgres.sh"
SCHEDULE_HOURS=2  # Intervalle en heures entre les sauvegardes
MAX_BACKUPS=48    # Nombre maximum de sauvegardes à conserver

echo "[+] Configuration de l'automatisation de sauvegardes"
echo "[+] Intervalle: ${SCHEDULE_HOURS} heures"
echo "[+] Maximum de sauvegardes: ${MAX_BACKUPS}"

# Vérifier que le script de sauvegarde existe
if [ ! -f "${BACKUP_SCRIPT}" ]; then
    echo "[ERREUR] Script de sauvegarde introuvable: ${BACKUP_SCRIPT}"
    exit 1
fi

# Rendre le script exécutable
chmod +x "${BACKUP_SCRIPT}"

# Ajouter au crontab pour une exécution planifiée
echo "[+] Configuration de crontab pour sauvegardes planifiées..."
CRON_JOB="0 */${SCHEDULE_HOURS} * * * cd $(pwd) && ${BACKUP_SCRIPT} >> $(pwd)/backups/backup.log 2>&1"

# Vérifier si le job existe déjà
if crontab -l 2>/dev/null | grep -q "backup_postgres.sh"; then
    echo "[+] Job crontab existe déjà"
else
    # Ajouter le job au crontab
    (crontab -l 2>/dev/null; echo "${CRON_JOB}") | crontab -
    echo "[+] Job crontab ajouté: ${CRON_JOB}"
fi

# Créer le fichier de log
mkdir -p ./backups
touch ./backups/backup.log

echo "[+] Automatisation de sauvegardes configurée avec succès"
echo "[+] Les sauvegardes seront exécutées toutes les ${SCHEDULE_HOURS} heures"
echo "[+] Logs disponibles dans: ./backups/backup.log"

# Exécuter une sauvegarde immédiate pour tester
echo "[+] Exécution d'une sauvegarde de test..."
"${BACKUP_SCRIPT}"

echo "[+] Configuration terminée"