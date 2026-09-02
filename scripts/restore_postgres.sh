#!/usr/bin/env bash
# ==============================================================================
# Script de Restauration Automatisée PostgreSQL 16 pour Aegis IAM
# ==============================================================================
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Erreur: Le fichier '${BACKUP_FILE}' n'existe pas."
    exit 1
fi

echo "[+] Restauration de la base de données depuis '${BACKUP_FILE}'..."
gunzip -c "${BACKUP_FILE}" | docker exec -i aegis-postgres-db psql -U aegisuser -d aegis_iam_db

echo "[+] Restauration achevée avec succès."
