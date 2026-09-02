#!/usr/bin/env bash
# ==============================================================================
# Script de Sauvegarde Automatisée PostgreSQL 16 pour Aegis IAM
# ==============================================================================
set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aegis_postgres_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[+] Démarrage de la sauvegarde PostgreSQL..."
docker exec -t aegis-postgres-db pg_dumpall -U aegisuser | gzip > "${BACKUP_FILE}"

echo "[+] Sauvegarde réussie: ${BACKUP_FILE}"
echo "[+] Taille du fichier: $(du -h "${BACKUP_FILE}" | cut -f1)"
