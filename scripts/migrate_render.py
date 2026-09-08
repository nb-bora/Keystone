"""
Script de migration pour Render.com.

Exécute les migrations de base de données pour l'environnement Render.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Utiliser la variable d'environnement DATABASE_URL de Render
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required")
    sys.exit(1)


def run_migrations():
    """Exécute les migrations de base de données."""
    print(f"Connecting to database: {DATABASE_URL[:20]}...")

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        print("Running migrations...")

        # Créer la table subjects
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS subjects (
                id VARCHAR(255) PRIMARY KEY,
                subject_type VARCHAR(50) NOT NULL,
                tenant_id VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )

        # Créer la table permissions
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                subject_id VARCHAR(255) REFERENCES subjects(id) ON DELETE CASCADE,
                permission_code VARCHAR(255) NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """
            )
        )

        # Créer la table oauth_credentials
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS oauth_credentials (
                id VARCHAR(255) PRIMARY KEY,
                subject_id VARCHAR(255) REFERENCES subjects(id) ON DELETE CASCADE,
                provider VARCHAR(50) NOT NULL,
                provider_user_id VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TIMESTAMP,
                scopes TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, provider_user_id)
            )
        """
            )
        )

        # Créer la table sessions
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(255) PRIMARY KEY,
                subject_id VARCHAR(255) REFERENCES subjects(id) ON DELETE CASCADE,
                session_token VARCHAR(255) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )

        # Créer des indexes pour optimiser les requêtes
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_subjects_tenant ON subjects(tenant_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_permissions_subject ON permissions(subject_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth_credentials(provider)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_oauth_subject ON oauth_credentials(subject_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_sessions_subject ON sessions(subject_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)")
        )

        conn.commit()

    print("✅ Migrations completed successfully!")
    print("✅ Database schema is ready for Aegis IAM")


if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
