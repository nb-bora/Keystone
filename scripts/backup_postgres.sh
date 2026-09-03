#!/usr/bin/env bash
# ==============================================================================
# Script de Sauvegarde Automatisée PostgreSQL 16 pour Aegis IAM
# ==============================================================================
set -euo pipefail

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aegis_postgres_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30
DB_NAME="aegis_iam_db"
DB_USER="aegisuser"
DB_CONTAINER="aegis-postgres-db"

# Créer le répertoire de sauvegarde
mkdir -p "${BACKUP_DIR}"

echo "[+] Démarrage de la sauvegarde PostgreSQL..."
echo "[+] Base de données: ${DB_NAME}"
echo "[+] Fichier de sauvegarde: ${BACKUP_FILE}"

# Sauvegarde de la base de données
docker exec -t "${DB_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"

# Vérifier que la sauvegarde a réussi
if [ ! -f "${BACKUP_FILE}" ] || [ ! -s "${BACKUP_FILE}" ]; then
    echo "[ERREUR] La sauvegarde a échoué"
    exit 1
fi

echo "[+] Sauvegarde réussie: ${BACKUP_FILE}"
echo "[+] Taille du fichier: $(du -h "${BACKUP_FILE}" | cut -f1)"

# Nettoyer les anciennes sauvegardes
echo "[+] Nettoyage des sauvegardes antérieures à ${RETENTION_DAYS} jours..."
find "${BACKUP_DIR}" -name "aegis_postgres_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
echo "[+] Nettoyage terminé"

# Sauvegarder également les données Redis si configuré
if docker ps | grep -q "redis"; then
    echo "[+] Sauvegarde des données Redis..."
    REDIS_BACKUP_FILE="${BACKUP_DIR}/aegis_redis_${TIMESTAMP}.rdb"
    docker exec aegis-redis redis-cli BGSAVE
    docker cp aegis-redis:/data/dump.rdb "${REDIS_BACKUP_FILE}"
    echo "[+] Sauvegarde Redis réussie: ${REDIS_BACKUP_FILE}"
fi

echo "[+] Sauvegarde terminée avec succès"
