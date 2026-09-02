"""
Gestionnaire de Configuration & Variables d'Environnement d'Aegis.

Charge et valide les variables d'environnement (.env) de manière sécurisée avec
typabilité et zéro dépendance externe obligatoire.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List, Optional


def load_env_file(env_path: Optional[Path] = None) -> None:
    """Charge manuellement le fichier .env dans os.environ si présent."""
    target_path = env_path or Path(".env")
    if not target_path.exists():
        return

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


# Charger le fichier .env au premier import
load_env_file()


@dataclass(frozen=True, slots=True)
class Settings:
    """Paramètres de configuration centraux de l'application Aegis."""

    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "aegis-dev-default-secret-key-32-chars-min!!")
    )

    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./aegis.db"))

    audit_outbox_batch_size: int = field(default_factory=lambda: int(os.getenv("AUDIT_OUTBOX_BATCH_SIZE", "50")))
    password_hash_iterations: int = field(
        default_factory=lambda: int(os.getenv("PASSWORD_HASH_ITERATIONS", "100000"))
    )

    cors_origins: List[str] = field(
        default_factory=lambda: [s.strip() for s in os.getenv("CORS_ORIGINS", "*").split(",") if s.strip()]
    )


# Instance globale de configuration
settings = Settings()
