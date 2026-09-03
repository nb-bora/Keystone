#!/usr/bin/env bash
# ==============================================================================
# Script de Restauration Automatisée PostgreSQL 16 pour Aegis IAM
# ==============================================================================
set -euo pipefail

# Configuration
BACKUP_FILE="${1:-./backups/aegis_postgres_latest.sql.gz}"
DB_NAME="aegis_iam_db"
DB_USER="aegisuser"
DB_CONTAINER="aegis-postgres-db"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_backup_file.sql.gz>"
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Erreur: Le fichier '${BACKUP_FILE}' n'existe pas."
    exit 1
fi

echo "[+] Restauration de la base de données depuis '${BACKUP_FILE}'..."
echo "[+] Base de données cible: ${DB_NAME}"

# Confirmation de sécurité
read -p "[WARNING] Cela va remplacer toutes les données existantes. Continuer? (oui/non): " confirmation
if [ "$confirmation" != "oui" ]; then
    echo "[] Restauration annulée"
    exit 0
fi

# Arrêter l'application pour éviter les conflits
echo "[+] Arrêt de l'application Aegis..."
docker-compose stop aegis-api

# Restaurer la base de données
gunzip -c "${BACKUP_FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" "${DB_NAME}"

# Vérifier que la restauration a réussi
if [ $? -eq 0 ]; then
    echo "[+] Restauration terminée avec succès"
else
    echo "[ERREUR] La restauration a échoué"
    exit 1
fi

# Redémarrer l'application
echo "[+] Redémarrage de l'application Aegis..."
docker-compose start aegis-api

echo "[+] Restauration complète terminée"
